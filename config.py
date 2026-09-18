import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Server ---
HOST = "0.0.0.0"
PORT = 5000
DEBUG = True

# --- Serial / ESP32 ---
SERIAL_PORT = os.environ.get("AERIS_SERIAL_PORT", "COM9")
BAUD_RATE = int(os.environ.get("AERIS_BAUD_RATE", "115200"))
SERIAL_TIMEOUT = 2  # seconds
RECONNECT_INTERVAL = 5  # seconds

# --- Data Format ---
DATA_FORMAT = "csv"  # "csv" or "json"

# --- Update Interval ---
UPDATE_INTERVAL = 1.5  # seconds (live + simulation tick)

# --- Simulation ---
SIMULATION = {
    "temperature": {"min": 28.0, "max": 35.0, "drift": 0.15},
    "humidity": {"min": 50.0, "max": 90.0, "drift": 0.25},
    "pressure": {"min": 995.0, "max": 1020.0, "drift": 0.3},
    "rain_sensor": {"min": 0.0, "max": 100.0, "drift": 1.5},
}

# --- Validation Ranges ---
VALIDATION = {
    "temperature": {"min": -20.0, "max": 60.0, "unit": "C"},
    "humidity": {"min": 0.0, "max": 100.0, "unit": "%"},
    "pressure": {"min": 850.0, "max": 1100.0, "unit": "hPa"},
    "rain_sensor": {"min": 0, "max": 4095, "unit": "raw"},
}

# --- Rain Calibration ---
RAIN_CALIBRATION = {
    "dry_value": 0,
    "wet_value": 100,
    "invert": False,
    "smoothing": 0.3,
    "normalize": True,
}

# --- ML / Model ---
MODEL_DIR = os.path.join(BASE_DIR, "model")
MODEL_PATH = os.path.join(MODEL_DIR, "rain_model.pkl")
METADATA_PATH = os.path.join(MODEL_DIR, "metadata.json")
FEATURE_COLUMNS = ["temperature", "humidity", "pressure", "rain_sensor"]
TARGET_COLUMN = "rain"

RF_PARAMS = {
    "n_estimators": 200,
    "random_state": 42,
    "class_weight": "balanced",
    "max_depth": None,
    "min_samples_split": 2,
}

# --- History ---
MAX_HISTORY = 500
HISTORY_CSV = os.path.join(BASE_DIR, "data", "history.csv")

# --- Location ---
LOCATION = {
    "city": "Chennai",
    "country": "India",
    "lat": 13.08,
    "lon": 80.27,
}

# --- Data Paths ---
DATA_RAW = os.path.join(BASE_DIR, "data", "raw")
DATA_PROCESSED = os.path.join(BASE_DIR, "data", "processed")
LOG_DIR = os.path.join(BASE_DIR, "logs")


def load_config(path=None):
    """Load overrides from a JSON config file if present."""
    if path is None:
        path = os.path.join(BASE_DIR, "aeris_config.json")
    if os.path.exists(path):
        with open(path, "r") as f:
            overrides = json.load(f)
        _apply(overrides)
    return {
        "serial_port": SERIAL_PORT,
        "baud_rate": BAUD_RATE,
        "update_interval": UPDATE_INTERVAL,
    }


def _apply(d, prefix=""):
    global SERIAL_PORT, BAUD_RATE, UPDATE_INTERVAL
    for k, v in d.items():
        key = k.upper()
        if key == "SERIAL_PORT":
            SERIAL_PORT = v
        elif key == "BAUD_RATE":
            BAUD_RATE = int(v)
        elif key == "UPDATE_INTERVAL":
            UPDATE_INTERVAL = float(v)
