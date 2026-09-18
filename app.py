import os
import sys
import json
import csv
import time
import random
import logging
import threading
from datetime import datetime, timedelta
from collections import deque

import numpy as np
from flask import Flask, render_template, jsonify, request, send_file

import config

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
os.makedirs(config.LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(config.LOG_DIR, "aeris.log")),
    ],
)
log = logging.getLogger("aeris")

# ---------------------------------------------------------------------------
# Flask
# ---------------------------------------------------------------------------
app = Flask(__name__)

# ---------------------------------------------------------------------------
# Global State
# ---------------------------------------------------------------------------
state = {
    "mode": "simulation",  # "simulation" | "live"
    "esp32_connected": False,
    "serial_port": config.SERIAL_PORT,
    "baud_rate": config.BAUD_RATE,
    "packet_count": 0,
    "invalid_packet_count": 0,
    "last_packet_time": None,
    "last_sensor_update": None,
    "sensors": {
        "temperature": 31.0,
        "humidity": 75.0,
        "pressure": 1005.0,
        "rain_sensor": 0.0,
    },
    "rain_calibrated": 0.0,
    "prediction": {
        "class": "NO_RAIN",
        "probability": 0.0,
        "model_status": "not_trained",
        "model_version": None,
    },
    "data_quality": "GOOD",
}

sensor_history = deque(maxlen=config.MAX_HISTORY)
prediction_history = deque(maxlen=config.MAX_HISTORY)

# Simulation drift values
sim_values = {
    "temperature": 31.0,
    "humidity": 75.0,
    "pressure": 1005.0,
    "rain_sensor": 20.0,
}

# Serial reader thread handle
serial_thread = None
serial_stop = threading.Event()

# ---------------------------------------------------------------------------
# Serial Reader
# ---------------------------------------------------------------------------
def _open_serial():
    try:
        import serial
        ser = serial.Serial(
            config.SERIAL_PORT,
            config.BAUD_RATE,
            timeout=config.SERIAL_TIMEOUT,
        )
        time.sleep(2)  # wait for ESP32 reset
        log.info("Serial opened on %s @ %d", config.SERIAL_PORT, config.BAUD_RATE)
        state["esp32_connected"] = True
        return ser
    except Exception as e:
        log.warning("Serial open failed: %s", e)
        state["esp32_connected"] = False
        return None


def _parse_csv_line(line: str):
    """Parse 'temp,humidity,pressure,rain_sensor'."""
    parts = [p.strip() for p in line.split(",")]
    if len(parts) != 4:
        return None
    try:
        vals = [float(p) for p in parts]
    except ValueError:
        return None
    keys = ["temperature", "humidity", "pressure", "rain_sensor"]
    return dict(zip(keys, vals))


def _validate_reading(d: dict) -> bool:
    for k, v in d.items():
        r = config.VALIDATION.get(k)
        if r and not (r["min"] <= v <= r["max"]):
            log.warning("Validation failed: %s = %s not in [%s,%s]", k, v, r["min"], r["max"])
            return False
    return True


def _serial_reader():
    """Background thread: reads serial, updates state."""
    ser = None
    while not serial_stop.is_set():
        if ser is None:
            ser = _open_serial()
            if ser is None:
                serial_stop.wait(config.RECONNECT_INTERVAL)
                continue
        try:
            raw = ser.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            state["packet_count"] += 1
            state["last_packet_time"] = datetime.now().isoformat()

            if config.DATA_FORMAT == "csv":
                data = _parse_csv_line(line)
            else:
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    data = None

            if data is None:
                state["invalid_packet_count"] += 1
                continue
            if not _validate_reading(data):
                state["invalid_packet_count"] += 1
                continue

            state["sensors"].update(data)
            state["last_sensor_update"] = datetime.now().isoformat()
            _update_rain_calibrated()
            _run_inference()
            _log_observation("live")

        except Exception as e:
            log.error("Serial read error: %s", e)
            state["esp32_connected"] = False
            ser = None
            serial_stop.wait(config.RECONNECT_INTERVAL)


def start_serial():
    global serial_thread
    if serial_thread and serial_thread.is_alive():
        return
    serial_stop.clear()
    serial_thread = threading.Thread(target=_serial_reader, daemon=True)
    serial_thread.start()


def stop_serial():
    serial_stop.set()


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------
def _sim_tick():
    """Advance simulation values by bounded random drift."""
    for key in ["temperature", "humidity", "pressure", "rain_sensor"]:
        cfg = config.SIMULATION[key]
        drift = random.uniform(-cfg["drift"], cfg["drift"])
        sim_values[key] = max(cfg["min"], min(cfg["max"], sim_values[key] + drift))
        sim_values[key] = round(sim_values[key], 2)
    state["sensors"].update(sim_values)
    state["last_sensor_update"] = datetime.now().isoformat()
    _update_rain_calibrated()
    _run_inference()
    _log_observation("simulation")


# ---------------------------------------------------------------------------
# Rain Calibration
# ---------------------------------------------------------------------------
def _update_rain_calibrated():
    raw = state["sensors"]["rain_sensor"]
    cal = config.RAIN_CALIBRATION
    if cal["normalize"]:
        dry = cal["dry_value"]
        wet = cal["wet_value"]
        if wet == dry:
            norm = 0.0
        elif cal["invert"]:
            norm = max(0.0, min(1.0, (dry - raw) / (dry - wet)))
        else:
            norm = max(0.0, min(1.0, (raw - dry) / (wet - dry)))
        state["rain_calibrated"] = round(norm * 100, 1)
    else:
        state["rain_calibrated"] = round(raw, 1)


# ---------------------------------------------------------------------------
# ML Inference
# ---------------------------------------------------------------------------
_model = None
_model_meta = None


def _load_model():
    global _model, _model_meta
    if not os.path.exists(config.MODEL_PATH):
        state["prediction"]["model_status"] = "not_trained"
        return False
    try:
        import joblib
        _model = joblib.load(config.MODEL_PATH)
        if os.path.exists(config.METADATA_PATH):
            with open(config.METADATA_PATH, "r") as f:
                _model_meta = json.load(f)
        state["prediction"]["model_status"] = "trained"
        state["prediction"]["model_version"] = _model_meta.get("version", "unknown") if _model_meta else "unknown"
        log.info("Model loaded: %s", config.MODEL_PATH)
        return True
    except Exception as e:
        log.error("Model load failed: %s", e)
        state["prediction"]["model_status"] = "error"
        return False


def _run_inference():
    if _model is None:
        _demo_prediction()
        return
    try:
        features = [
            state["sensors"]["temperature"],
            state["sensors"]["humidity"],
            state["sensors"]["pressure"],
            state["rain_calibrated"],
        ]
        X = np.array([features])
        pred_class = _model.predict(X)[0]
        proba = _model.predict_proba(X)[0]
        class_idx = list(_model.classes_).index(pred_class)
        state["prediction"]["class"] = str(pred_class)
        state["prediction"]["probability"] = round(float(proba[class_idx]), 4)
        state["prediction"]["model_status"] = "trained"
        if _model_meta:
            state["prediction"]["model_version"] = _model_meta.get("version", "unknown")
    except Exception as e:
        log.error("Inference error: %s", e)
        _demo_prediction()


def _demo_prediction():
    """Deterministic demo probability based on sensor readings."""
    h = state["sensors"]["humidity"]
    r = state["rain_calibrated"]
    p = state["sensors"]["pressure"]
    score = (h / 100.0) * 0.4 + (r / 100.0) * 0.35 + max(0, (1013 - p) / 50) * 0.25
    prob = max(0.0, min(1.0, score))
    state["prediction"]["class"] = "RAIN" if prob > 0.5 else "NO_RAIN"
    state["prediction"]["probability"] = round(prob, 4)
    state["prediction"]["model_status"] = "demo" if state["prediction"]["model_status"] not in ("trained",) else state["prediction"]["model_status"]


# ---------------------------------------------------------------------------
# Data Quality
# ---------------------------------------------------------------------------
def _compute_quality():
    now = datetime.now()
    last = state.get("last_packet_time") if state["mode"] == "live" else state.get("last_sensor_update")
    if last is None:
        return "FAULT"
    try:
        dt = (now - datetime.fromisoformat(last)).total_seconds()
    except Exception:
        return "FAULT"
    if state["mode"] == "live":
        if not state["esp32_connected"]:
            return "FAULT"
        if dt > 30:
            return "DEGRADED"
        if state["invalid_packet_count"] > state["packet_count"] * 0.2 and state["packet_count"] > 10:
            return "DEGRADED"
    else:
        if dt > 10:
            return "DEGRADED"
    return "GOOD"


# ---------------------------------------------------------------------------
# History Logging
# ---------------------------------------------------------------------------
def _log_observation(mode):
    row = {
        "timestamp": datetime.now().isoformat(),
        "mode": mode,
        "temperature": state["sensors"]["temperature"],
        "humidity": state["sensors"]["humidity"],
        "pressure": state["sensors"]["pressure"],
        "rain_sensor": state["sensors"]["rain_sensor"],
        "rain_calibrated": state["rain_calibrated"],
        "prediction_class": state["prediction"]["class"],
        "prediction_probability": state["prediction"]["probability"],
        "model_status": state["prediction"]["model_status"],
        "model_version": state["prediction"].get("model_version", ""),
    }
    sensor_history.append(row)
    prediction_history.append(row)


def _save_history_csv():
    if not sensor_history:
        return
    path = config.HISTORY_CSV
    os.makedirs(os.path.dirname(path), exist_ok=True)
    keys = list(sensor_history[0].keys())
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(sensor_history)


# ---------------------------------------------------------------------------
# Routes — Pages
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# Routes — API
# ---------------------------------------------------------------------------
@app.route("/api/status")
def api_status():
    state["data_quality"] = _compute_quality()
    return jsonify({
        "mode": state["mode"],
        "esp32_connected": state["esp32_connected"],
        "serial_port": state["serial_port"],
        "baud_rate": state["baud_rate"],
        "packet_count": state["packet_count"],
        "invalid_packet_count": state["invalid_packet_count"],
        "last_packet_time": state["last_packet_time"],
        "last_sensor_update": state["last_sensor_update"],
        "data_quality": state["data_quality"],
        "model_status": state["prediction"]["model_status"],
        "timestamp": datetime.now().isoformat(),
    })


@app.route("/api/sensors")
def api_sensors():
    state["data_quality"] = _compute_quality()
    return jsonify({
        "temperature": state["sensors"]["temperature"],
        "humidity": state["sensors"]["humidity"],
        "pressure": state["sensors"]["pressure"],
        "rain_sensor_raw": state["sensors"]["rain_sensor"],
        "rain_sensor_calibrated": state["rain_calibrated"],
        "mode": state["mode"],
        "data_quality": state["data_quality"],
        "last_update": state["last_sensor_update"],
        "timestamp": datetime.now().isoformat(),
    })


@app.route("/api/prediction")
def api_prediction():
    return jsonify({
        "class": state["prediction"]["class"],
        "probability": state["prediction"]["probability"],
        "model": "RandomForest",
        "model_status": state["prediction"]["model_status"],
        "model_version": state["prediction"].get("model_version"),
        "features": {
            "temperature": state["sensors"]["temperature"],
            "humidity": state["sensors"]["humidity"],
            "pressure": state["sensors"]["pressure"],
            "rain_sensor": state["rain_calibrated"],
        },
        "timestamp": datetime.now().isoformat(),
    })


@app.route("/api/history")
def api_history():
    n = request.args.get("limit", 30, type=int)
    data = list(sensor_history)[-n:]
    return jsonify({"history": data, "total": len(sensor_history)})


@app.route("/api/history/download")
def api_history_download():
    _save_history_csv()
    if os.path.exists(config.HISTORY_CSV):
        return send_file(config.HISTORY_CSV, as_attachment=True, download_name="aeris_history.csv")
    return jsonify({"error": "No history available"}), 404


@app.route("/api/model")
def api_model():
    meta = {}
    if os.path.exists(config.METADATA_PATH):
        with open(config.METADATA_PATH, "r") as f:
            meta = json.load(f)
    return jsonify({
        "model_status": state["prediction"]["model_status"],
        "model_version": state["prediction"].get("model_version"),
        "model_path": config.MODEL_PATH,
        "metadata": meta,
    })


@app.route("/api/model/metrics")
def api_model_metrics():
    if os.path.exists(config.METADATA_PATH):
        with open(config.METADATA_PATH, "r") as f:
            meta = json.load(f)
        return jsonify(meta.get("metrics", {}))
    return jsonify({})


@app.route("/api/model/feature_importance")
def api_model_feature_importance():
    if _model is not None and hasattr(_model, "feature_importances_"):
        importances = _model.feature_importances_
        cols = _model_meta.get("feature_columns", config.FEATURE_COLUMNS) if _model_meta else config.FEATURE_COLUMNS
        return jsonify(dict(zip(cols, [round(float(x), 4) for x in importances])))
    return jsonify({})


@app.route("/api/mode", methods=["POST"])
def api_set_mode():
    data = request.get_json(force=True)
    mode = data.get("mode", "simulation")
    if mode not in ("simulation", "live"):
        return jsonify({"error": "Invalid mode"}), 400
    state["mode"] = mode
    log.info("Mode changed to %s", mode)
    if mode == "live":
        start_serial()
    return jsonify({"mode": state["mode"]})


@app.route("/api/calibration", methods=["POST"])
def api_set_calibration():
    data = request.get_json(force=True)
    cal = config.RAIN_CALIBRATION
    if "dry_value" in data:
        cal["dry_value"] = float(data["dry_value"])
    if "wet_value" in data:
        cal["wet_value"] = float(data["wet_value"])
    if "invert" in data:
        cal["invert"] = bool(data["invert"])
    if "smoothing" in data:
        cal["smoothing"] = float(data["smoothing"])
    if "normalize" in data:
        cal["normalize"] = bool(data["normalize"])
    _update_rain_calibrated()
    log.info("Calibration updated: %s", cal)
    return jsonify(cal)


@app.route("/api/calibration", methods=["GET"])
def api_get_calibration():
    return jsonify(config.RAIN_CALIBRATION)


@app.route("/api/train", methods=["POST"])
def api_train():
    data = request.get_json(force=True) if request.data else {}
    dataset_path = data.get("dataset_path", "")
    if not dataset_path:
        dataset_path = os.path.join(config.DATA_RAW, "dataset.csv")
    if not os.path.exists(dataset_path):
        return jsonify({"error": f"Dataset not found: {dataset_path}"}), 400
    try:
        from model.train_model import train
        result = train(dataset_path)
        _load_model()
        return jsonify(result)
    except Exception as e:
        log.error("Training error: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/settings", methods=["GET"])
def api_get_settings():
    return jsonify({
        "serial_port": config.SERIAL_PORT,
        "baud_rate": config.BAUD_RATE,
        "update_interval": config.UPDATE_INTERVAL,
        "rain_calibration": config.RAIN_CALIBRATION,
        "validation": config.VALIDATION,
        "location": config.LOCATION,
        "simulation": config.SIMULATION,
    })


@app.route("/api/settings", methods=["POST"])
def api_set_settings():
    data = request.get_json(force=True)
    if "serial_port" in data:
        config.SERIAL_PORT = data["serial_port"]
        state["serial_port"] = data["serial_port"]
    if "baud_rate" in data:
        config.BAUD_RATE = int(data["baud_rate"])
        state["baud_rate"] = int(data["baud_rate"])
    if "update_interval" in data:
        config.UPDATE_INTERVAL = float(data["update_interval"])
    if "rain_calibration" in data:
        config.RAIN_CALIBRATION.update(data["rain_calibration"])
    if "location" in data:
        config.LOCATION.update(data["location"])
    log.info("Settings updated")
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# Background tick (simulation or keep-alive)
# ---------------------------------------------------------------------------
def _background_tick():
    while True:
        try:
            if state["mode"] == "simulation":
                _sim_tick()
            time.sleep(config.UPDATE_INTERVAL)
        except Exception as e:
            log.error("Tick error: %s", e)
            time.sleep(1)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
_load_model()

# Attempt serial connection at startup if configured
if state["mode"] == "live":
    start_serial()

tick_thread = threading.Thread(target=_background_tick, daemon=True)
tick_thread.start()


if __name__ == "__main__":
    config.load_config()
    log.info("Starting AERIS AI on %s:%s", config.HOST, config.PORT)
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG, use_reloader=False)
