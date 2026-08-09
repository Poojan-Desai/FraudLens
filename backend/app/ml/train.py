from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .synthetic import time_split


TARGET = "is_fraud"
EXCLUDED = {TARGET, "dataset_source", "timestamp"}
CATEGORICAL = ["merchant_category", "country"]


def _preprocessor(feature_columns: list[str]) -> ColumnTransformer:
    numerical = [column for column in feature_columns if column not in CATEGORICAL]
    return ColumnTransformer([
        ("numeric", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), numerical),
        ("categorical", Pipeline([("impute", SimpleImputer(strategy="most_frequent")), ("encode", OneHotEncoder(handle_unknown="ignore"))]), CATEGORICAL),
    ])


def train_logistic(frame: pd.DataFrame, artifact_dir: Path) -> dict[str, Any]:
    """Train the transparent baseline using a strict chronological holdout."""
    train, validation, test = time_split(frame)
    feature_columns = [column for column in frame.columns if column not in EXCLUDED]
    if TARGET in feature_columns:
        raise RuntimeError("target leakage detected")

    pipeline = Pipeline([
        ("preprocess", _preprocessor(feature_columns)),
        ("model", LogisticRegression(max_iter=800, class_weight="balanced", random_state=42)),
    ])
    started = time.perf_counter()
    pipeline.fit(train[feature_columns], train[TARGET])
    training_seconds = time.perf_counter() - started
    validation_probability = pipeline.predict_proba(validation[feature_columns])[:, 1]
    test_probability = pipeline.predict_proba(test[feature_columns])[:, 1]
    threshold = float(max((index / 100 for index in range(1, 100)), key=lambda cut: f1_score(validation[TARGET], validation_probability >= cut)))
    predicted = test_probability >= threshold
    metrics = {
        "model": "logistic_regression",
        "version": "1.0.0",
        "threshold": threshold,
        "precision": precision_score(test[TARGET], predicted, zero_division=0),
        "recall": recall_score(test[TARGET], predicted, zero_division=0),
        "f1": f1_score(test[TARGET], predicted, zero_division=0),
        "pr_auc": average_precision_score(test[TARGET], test_probability),
        "training_seconds": training_seconds,
        "train_rows": len(train),
        "validation_rows": len(validation),
        "test_rows": len(test),
    }
    artifact_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, artifact_dir / "logistic_regression.joblib")
    (artifact_dir / "logistic_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


def train_xgboost(frame: pd.DataFrame, artifact_dir: Path) -> dict[str, Any]:
    """Train and calibrate the performance model on separate time windows."""
    from xgboost import XGBClassifier

    train, validation, test = time_split(frame)
    feature_columns = [column for column in frame.columns if column not in EXCLUDED]
    if TARGET in feature_columns:
        raise RuntimeError("target leakage detected")

    preprocessor = _preprocessor(feature_columns)
    x_train = preprocessor.fit_transform(train[feature_columns])
    x_validation = preprocessor.transform(validation[feature_columns])
    x_test = preprocessor.transform(test[feature_columns])
    positives = int(train[TARGET].sum())
    negatives = len(train) - positives
    model = XGBClassifier(
        n_estimators=300,
        max_depth=3,
        learning_rate=0.05,
        subsample=0.85,
        colsample_bytree=0.85,
        objective="binary:logistic",
        eval_metric="aucpr",
        scale_pos_weight=negatives / max(positives, 1),
        random_state=42,
        n_jobs=-1,
    )
    started = time.perf_counter()
    model.fit(x_train, train[TARGET], eval_set=[(x_validation, validation[TARGET])], verbose=False)
    training_seconds = time.perf_counter() - started

    # Fit the probability calibrator only on validation observations. The test
    # set remains untouched until final evaluation.
    calibrated = CalibratedClassifierCV(FrozenEstimator(model), method="sigmoid")
    calibrated.fit(x_validation, validation[TARGET])
    validation_probability = calibrated.predict_proba(x_validation)[:, 1]
    test_probability = calibrated.predict_proba(x_test)[:, 1]
    threshold = float(max((index / 100 for index in range(1, 100)), key=lambda cut: f1_score(validation[TARGET], validation_probability >= cut)))
    predicted = test_probability >= threshold
    metrics = {
        "model": "xgboost_calibrated",
        "version": "1.0.0",
        "threshold": threshold,
        "precision": precision_score(test[TARGET], predicted, zero_division=0),
        "recall": recall_score(test[TARGET], predicted, zero_division=0),
        "f1": f1_score(test[TARGET], predicted, zero_division=0),
        "pr_auc": average_precision_score(test[TARGET], test_probability),
        "training_seconds": training_seconds,
        "train_rows": len(train),
        "validation_rows": len(validation),
        "test_rows": len(test),
    }
    artifact_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        "preprocessor": preprocessor,
        "raw_model": model,
        "calibrated_model": calibrated,
        "feature_columns": feature_columns,
    }, artifact_dir / "xgboost_calibrated.joblib")
    (artifact_dir / "xgboost_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics
