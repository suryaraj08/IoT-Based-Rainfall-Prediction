"""Train a RandomForestClassifier for rainfall prediction."""
import os
import sys
import json
import logging
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report,
)
import joblib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

log = logging.getLogger("aeris.train")


def validate_dataset(df):
    """Validate and clean the dataset. Returns (df, report)."""
    report = {"original_rows": len(df), "issues": []}

    # Check required columns
    required = config.FEATURE_COLUMNS + [config.TARGET_COLUMN]
    missing = [c for c in required if c not in df.columns]
    if missing:
        report["issues"].append(f"Missing columns: {missing}")
        raise ValueError(f"Missing columns: {missing}. Found: {list(df.columns)}")

    # Drop completely empty rows
    empty_count = df.isnull().all(axis=1).sum()
    if empty_count > 0:
        df = df.dropna(how="all")
        report["issues"].append(f"Dropped {empty_count} completely empty rows")

    # Check for duplicates
    dup_count = df.duplicated().sum()
    if dup_count > 0:
        df = df.drop_duplicates()
        report["issues"].append(f"Dropped {dup_count} duplicate rows")

    # Numeric validation
    for col in config.FEATURE_COLUMNS:
        non_numeric = pd.to_numeric(df[col], errors="coerce").isnull().sum()
        if non_numeric > 0:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            report["issues"].append(f"Converted {non_numeric} non-numeric values in '{col}' to NaN")

    # Fill missing with median
    missing_count = df[config.FEATURE_COLUMNS].isnull().sum().sum()
    if missing_count > 0:
        for col in config.FEATURE_COLUMNS:
            if df[col].isnull().any():
                median_val = df[col].median()
                df[col] = df[col].fillna(median_val)
        report["issues"].append(f"Filled {missing_count} missing values with median")

    # Drop rows where target is missing
    target_missing = df[config.TARGET_COLUMN].isnull().sum()
    if target_missing > 0:
        df = df.dropna(subset=[config.TARGET_COLUMN])
        report["issues"].append(f"Dropped {target_missing} rows with missing target")

    # Validate ranges
    vr = config.VALIDATION
    for col in config.FEATURE_COLUMNS:
        if col in vr:
            lo, hi = vr[col]["min"], vr[col]["max"]
            oob = ((df[col] < lo) | (df[col] > hi)).sum()
            if oob > 0:
                report["issues"].append(f"{oob} values in '{col}' outside [{lo}, {hi}] (kept as-is)")

    # Encode target
    target_unique = df[config.TARGET_COLUMN].unique()
    target_map = {}
    for v in target_unique:
        v_str = str(v).strip().upper()
        if v_str in ("1", "YES", "TRUE", "RAIN", "R"):
            target_map[v] = "RAIN"
        elif v_str in ("0", "NO", "FALSE", "NO_RAIN", "N"):
            target_map[v] = "NO_RAIN"
        else:
            target_map[v] = v_str
    df[config.TARGET_COLUMN] = df[config.TARGET_COLUMN].map(target_map)

    report["cleaned_rows"] = len(df)
    report["class_distribution"] = df[config.TARGET_COLUMN].value_counts().to_dict()
    return df, report


def train(dataset_path=None):
    """Train the model. Returns a result dict."""
    if dataset_path is None:
        dataset_path = os.path.join(config.DATA_RAW, "dataset.csv")

    log.info("Loading dataset: %s", dataset_path)
    df = pd.read_csv(dataset_path)

    df, report = validate_dataset(df)
    log.info("Dataset validated. Rows: %d -> %d", report["original_rows"], report["cleaned_rows"])

    X = np.array(df[config.FEATURE_COLUMNS].values, dtype=np.float64)
    y = np.array(df[config.TARGET_COLUMN].values)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y if len(np.unique(y)) > 1 else None,
    )

    log.info("Training RandomForest with params: %s", config.RF_PARAMS)
    clf = RandomForestClassifier(**config.RF_PARAMS)
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, pos_label="RAIN", zero_division=0)
    rec = recall_score(y_test, y_pred, pos_label="RAIN", zero_division=0)
    f1 = f1_score(y_test, y_pred, pos_label="RAIN", zero_division=0)
    cm = confusion_matrix(y_test, y_pred, labels=["NO_RAIN", "RAIN"]).tolist()
    report_text = classification_report(y_test, y_pred, zero_division=0)

    feature_importance = dict(zip(config.FEATURE_COLUMNS, [round(float(x), 4) for x in clf.feature_importances_]))

    version = f"rf-v{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    metrics = {
        "accuracy": round(float(acc), 4),
        "precision": round(float(prec), 4),
        "recall": round(float(rec), 4),
        "f1_score": round(float(f1), 4),
        "confusion_matrix": cm,
        "classification_report": report_text,
        "train_rows": len(X_train),
        "test_rows": len(X_test),
    }

    metadata = {
        "model_name": "RandomForestClassifier",
        "version": version,
        "training_timestamp": datetime.now().isoformat(),
        "feature_columns": config.FEATURE_COLUMNS,
        "target_column": config.TARGET_COLUMN,
        "hyperparameters": config.RF_PARAMS,
        "dataset": {
            "path": dataset_path,
            "original_rows": report["original_rows"],
            "cleaned_rows": report["cleaned_rows"],
            "class_distribution": report["class_distribution"],
        },
        "validation_report": report["issues"],
        "metrics": metrics,
        "feature_importance": feature_importance,
    }

    os.makedirs(config.MODEL_DIR, exist_ok=True)
    joblib.dump(clf, config.MODEL_PATH)
    with open(config.METADATA_PATH, "w") as f:
        json.dump(metadata, f, indent=2)

    log.info("Model saved: %s (version %s)", config.MODEL_PATH, version)
    log.info("Accuracy: %.4f  F1: %.4f", acc, f1)

    return {
        "status": "success",
        "version": version,
        "metrics": metrics,
        "feature_importance": feature_importance,
        "validation_report": report["issues"],
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Train AERIS rainfall model")
    parser.add_argument("--dataset", type=str, default=None, help="Path to CSV dataset")
    args = parser.parse_args()
    result = train(args.dataset)
    print(json.dumps(result, indent=2))
