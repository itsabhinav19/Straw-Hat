"""
train.py — Train the BugPredictor ML model.

Expected CSV format (any of these work):
    code,label                         → label: 0=clean, 1=buggy
    code,language,label
    code,language,label,risk_score     → risk_score: 0-100 (used for regression)

Usage:
    python train.py --dataset path/to/dataset.csv
    python train.py --dataset data.csv --model-dir models/ --task classification
    python train.py --dataset data.csv --task regression   # predicts 0-100 score
"""

import argparse
import os
import json
import time
import warnings
import pandas as pd
import numpy as np
import joblib
from pathlib import Path

from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    mean_absolute_error,
    r2_score,
    roc_auc_score,
)

from feature_extractor import FeatureExtractor
from analyzer import StaticAnalyzer

warnings.filterwarnings("ignore")


# ------------------------------------------------------------------ #
#  Config
# ------------------------------------------------------------------ #

CONFIDENCE_THRESHOLD = 0.65     # below this → fall back to AI
MODEL_VERSION = "1.0.0"


# ------------------------------------------------------------------ #
#  Data loading
# ------------------------------------------------------------------ #

def load_dataset(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    required = {"code", "label"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Dataset missing required columns: {missing}. Got: {list(df.columns)}")

    before = len(df)
    df = df.dropna(subset=["code", "label"])
    df["code"] = df["code"].astype(str)
    df["label"] = pd.to_numeric(df["label"], errors="coerce")
    df = df.dropna(subset=["label"])

    if "language" not in df.columns:
        df["language"] = "python"

    print(f"  Loaded {before} rows → {len(df)} usable after cleaning")
    return df


# ------------------------------------------------------------------ #
#  Feature extraction
# ------------------------------------------------------------------ #

def build_feature_matrix(df: pd.DataFrame) -> np.ndarray:
    extractor = FeatureExtractor()
    analyzer = StaticAnalyzer()

    X = []
    failed = 0
    total = len(df)

    for i, (_, row) in enumerate(df.iterrows()):
        if i % 100 == 0:
            print(f"  Extracting features... {i}/{total}", end="\r")
        try:
            static = analyzer.analyze(str(row["code"]), str(row.get("language", "python")))
            feats = extractor.extract(str(row["code"]), str(row.get("language", "python")), static)
            X.append(feats)
        except Exception:
            X.append([0.0] * FeatureExtractor.N_FEATURES)
            failed += 1

    print(f"  Feature extraction complete. Failed rows: {failed}/{total}   ")
    return np.array(X, dtype=np.float32)


# ------------------------------------------------------------------ #
#  Training
# ------------------------------------------------------------------ #

def train_classification(X_train, X_test, y_train, y_test):
    """Binary or multi-class classification (label = 0 or 1)."""

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("model", GradientBoostingClassifier(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            min_samples_leaf=5,
            random_state=42,
        )),
    ])

    print("\n  Training GradientBoostingClassifier...")
    t0 = time.time()
    pipeline.fit(X_train, y_train)
    print(f"  Done in {time.time() - t0:.1f}s")

    # Evaluate
    y_pred = pipeline.predict(X_test)
    y_prob = pipeline.predict_proba(X_test)[:, 1]

    print("\n  Classification Report:")
    print(classification_report(y_test, y_pred, target_names=["Clean", "Buggy"]))
    print("  Confusion Matrix:")
    print(confusion_matrix(y_test, y_pred))

    try:
        auc = roc_auc_score(y_test, y_prob)
        print(f"  ROC-AUC: {auc:.4f}")
    except Exception:
        auc = None

    # Cross-validation
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(pipeline, X_train, y_train, cv=cv, scoring="f1")
    print(f"  5-fold CV F1: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")

    metrics = {
        "task": "classification",
        "auc_roc": round(float(auc), 4) if auc else None,
        "cv_f1_mean": round(float(cv_scores.mean()), 4),
        "cv_f1_std": round(float(cv_scores.std()), 4),
        "confidence_threshold": CONFIDENCE_THRESHOLD,
    }

    return pipeline, metrics


def train_regression(X_train, X_test, y_train, y_test):
    """Predict continuous risk score (0–100)."""

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("model", GradientBoostingRegressor(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            random_state=42,
        )),
    ])

    print("\n  Training GradientBoostingRegressor...")
    t0 = time.time()
    pipeline.fit(X_train, y_train)
    print(f"  Done in {time.time() - t0:.1f}s")

    y_pred = pipeline.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    print(f"  MAE: {mae:.2f}  |  R²: {r2:.4f}")

    metrics = {
        "task": "regression",
        "mae": round(float(mae), 4),
        "r2": round(float(r2), 4),
    }

    return pipeline, metrics


# ------------------------------------------------------------------ #
#  Feature importance
# ------------------------------------------------------------------ #

def feature_importance(pipeline) -> dict:
    model = pipeline.named_steps["model"]
    if not hasattr(model, "feature_importances_"):
        return {}
    importances = model.feature_importances_
    names = FeatureExtractor.FEATURE_NAMES
    pairs = sorted(zip(names, importances), key=lambda x: x[1], reverse=True)
    return {name: round(float(imp), 5) for name, imp in pairs}


# ------------------------------------------------------------------ #
#  Save artifacts
# ------------------------------------------------------------------ #

def save_artifacts(pipeline, metrics, feature_imp, model_dir: str, task: str):
    Path(model_dir).mkdir(parents=True, exist_ok=True)

    model_path = os.path.join(model_dir, "bugpredictor_model.joblib")
    joblib.dump(pipeline, model_path)
    print(f"\n  Model saved → {model_path}")

    meta = {
        "version": MODEL_VERSION,
        "task": task,
        "n_features": FeatureExtractor.N_FEATURES,
        "feature_names": FeatureExtractor.FEATURE_NAMES,
        "metrics": metrics,
        "top_features": dict(list(feature_imp.items())[:15]),
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    meta_path = os.path.join(model_dir, "model_meta.json")
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"  Metadata saved → {meta_path}")


# ------------------------------------------------------------------ #
#  Main
# ------------------------------------------------------------------ #

def main():
    parser = argparse.ArgumentParser(description="Train BugPredictor ML model")
    parser.add_argument("--dataset", required=True, help="Path to dataset CSV")
    parser.add_argument("--model-dir", default="models/", help="Where to save model artifacts")
    parser.add_argument("--task", choices=["classification", "regression"],
                        default="classification",
                        help="classification=buggy/clean, regression=risk_score 0-100")
    parser.add_argument("--test-size", type=float, default=0.2)
    args = parser.parse_args()

    print(f"\n{'='*55}")
    print(f"  BugPredictor Training Pipeline  (task: {args.task})")
    print(f"{'='*55}\n")

    # 1. Load
    print("[1/4] Loading dataset...")
    df = load_dataset(args.dataset)
    print(f"  Label distribution:\n{df['label'].value_counts().to_string()}")

    # 2. Features
    print("\n[2/4] Extracting features...")
    X = build_feature_matrix(df)

    if args.task == "classification":
        y = df["label"].astype(int).values
    else:
        if "risk_score" not in df.columns:
            raise ValueError("Regression task requires a 'risk_score' column (0-100).")
        y = df["risk_score"].astype(float).values

    print(f"  Feature matrix: {X.shape}")
    print(f"  NaN in features: {np.isnan(X).sum()}")
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    # 3. Train/test split
    print("\n[3/4] Training...")
    stratify = y if args.task == "classification" else None
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=args.test_size, random_state=42, stratify=stratify
    )
    print(f"  Train: {len(X_train)} | Test: {len(X_test)}")

    if args.task == "classification":
        pipeline, metrics = train_classification(X_train, X_test, y_train, y_test)
    else:
        pipeline, metrics = train_regression(X_train, X_test, y_train, y_test)

    # 4. Save
    print("\n[4/4] Saving artifacts...")
    feat_imp = feature_importance(pipeline)
    save_artifacts(pipeline, metrics, feat_imp, args.model_dir, args.task)

    print(f"\n{'='*55}")
    print("  Training complete!")
    print(f"  Top-5 features:")
    for name, score in list(feat_imp.items())[:5]:
        bar = "█" * int(score * 300)
        print(f"    {name:<30} {bar} {score:.4f}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
