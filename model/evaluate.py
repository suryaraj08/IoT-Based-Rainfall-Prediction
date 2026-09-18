"""Evaluate the trained AERIS rainfall model."""
import os
import sys
import json

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report,
)
import joblib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def evaluate(dataset_path=None):
    if not os.path.exists(config.MODEL_PATH):
        return {"error": "No trained model found"}

    model = joblib.load(config.MODEL_PATH)
    with open(config.METADATA_PATH, "r") as f:
        meta = json.load(f)

    if dataset_path is None:
        dataset_path = meta.get("dataset", {}).get("path", os.path.join(config.DATA_RAW, "dataset.csv"))

    if not os.path.exists(dataset_path):
        return {"error": f"Dataset not found: {dataset_path}"}

    df = pd.read_csv(dataset_path)
    feature_cols = meta.get("feature_columns", config.FEATURE_COLUMNS)
    target_col = meta.get("target_column", config.TARGET_COLUMN)

    missing = [c for c in feature_cols + [target_col] if c not in df.columns]
    if missing:
        return {"error": f"Missing columns: {missing}"}

    df = df.dropna(subset=feature_cols + [target_col])
    X = df[feature_cols].values
    y = df[target_col].values

    y_pred = model.predict(X)

    result = {
        "accuracy": round(float(accuracy_score(y, y_pred)), 4),
        "precision": round(float(precision_score(y, y_pred, pos_label="RAIN", zero_division=0)), 4),
        "recall": round(float(recall_score(y, y_pred, pos_label="RAIN", zero_division=0)), 4),
        "f1_score": round(float(f1_score(y, y_pred, pos_label="RAIN", zero_division=0)), 4),
        "confusion_matrix": confusion_matrix(y, y_pred, labels=["NO_RAIN", "RAIN"]).tolist(),
        "classification_report": classification_report(y, y_pred, zero_division=0),
        "dataset_rows": len(df),
        "model_version": meta.get("version", "unknown"),
    }
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=str, default=None)
    args = parser.parse_args()
    result = evaluate(args.dataset)
    print(json.dumps(result, indent=2))
