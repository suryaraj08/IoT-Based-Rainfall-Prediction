"""Load model and run inference for AERIS AI."""
import os
import sys
import json
from datetime import datetime

import numpy as np
import joblib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


class RainPredictor:
    def __init__(self):
        self.model = None
        self.metadata = None
        self.loaded = False

    def load(self):
        if not os.path.exists(config.MODEL_PATH):
            self.loaded = False
            return False
        self.model = joblib.load(config.MODEL_PATH)
        if os.path.exists(config.METADATA_PATH):
            with open(config.METADATA_PATH, "r") as f:
                self.metadata = json.load(f)
        self.loaded = True
        return True

    def predict(self, temperature, humidity, pressure, rain_sensor):
        if not self.loaded:
            return self._demo_prediction(temperature, humidity, pressure, rain_sensor)

        features = np.array([[temperature, humidity, pressure, rain_sensor]])
        pred_class = self.model.predict(features)[0]
        proba = self.model.predict_proba(features)[0]
        class_idx = list(self.model.classes_).index(pred_class)

        return {
            "class": str(pred_class),
            "probability": round(float(proba[class_idx]), 4),
            "model_status": "trained",
            "model_version": self.metadata.get("version", "unknown") if self.metadata else "unknown",
            "features": {
                "temperature": temperature,
                "humidity": humidity,
                "pressure": pressure,
                "rain_sensor": rain_sensor,
            },
            "timestamp": datetime.now().isoformat(),
        }

    def _demo_prediction(self, temperature, humidity, pressure, rain_sensor):
        h = humidity / 100.0
        r = rain_sensor / 100.0
        p_factor = max(0, (1013 - pressure) / 50) * 0.25
        score = h * 0.4 + r * 0.35 + p_factor
        prob = max(0.0, min(1.0, score))
        return {
            "class": "RAIN" if prob > 0.5 else "NO_RAIN",
            "probability": round(prob, 4),
            "model_status": "demo",
            "model_version": None,
            "features": {
                "temperature": temperature,
                "humidity": humidity,
                "pressure": pressure,
                "rain_sensor": rain_sensor,
            },
            "timestamp": datetime.now().isoformat(),
        }


if __name__ == "__main__":
    predictor = RainPredictor()
    predictor.load()
    result = predictor.predict(
        temperature=31.4,
        humidity=79.2,
        pressure=1005.8,
        rain_sensor=23.0,
    )
    print(json.dumps(result, indent=2))
