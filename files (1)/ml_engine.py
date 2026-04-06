"""
ml_engine.py — Inference with the trained ML model.

Returns a prediction + confidence score.
If confidence < threshold → triggers AI fallback in app.py.
"""

import os
import json
import joblib
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional

from feature_extractor import FeatureExtractor


class MLEngine:
    def __init__(self, model_dir: str = "models/"):
        self.model_dir = model_dir
        self.model = None
        self.meta = {}
        self.feature_extractor = FeatureExtractor()
        self._load()

    def is_ready(self) -> bool:
        return self.model is not None

    def _load(self):
        model_path = os.path.join(self.model_dir, "bugpredictor_model.joblib")
        meta_path = os.path.join(self.model_dir, "model_meta.json")

        if not os.path.exists(model_path):
            print(f"[MLEngine] No model found at {model_path}. "
                  "Run train.py first. Will use AI fallback only.")
            return

        self.model = joblib.load(model_path)

        if os.path.exists(meta_path):
            with open(meta_path) as f:
                self.meta = json.load(f)

        task = self.meta.get("task", "classification")
        version = self.meta.get("version", "?")
        print(f"[MLEngine] Loaded model v{version} (task: {task})")

    def predict(
        self,
        code: str,
        language: str,
        static_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Run ML prediction.

        Returns:
            {
                "ml_risk_score":  int 0-100,
                "confidence":     float 0.0-1.0,
                "needs_ai":       bool,   ← True if confidence is low
                "label":          str,    ← "buggy" | "clean"
                "probabilities":  dict,   ← for classification only
                "model_version":  str,
            }
        """
        if not self.is_ready():
            return self._no_model_response()

        # Extract features
        features = self.feature_extractor.extract(code, language, static_results)
        X = np.array([features], dtype=np.float32)
        X = np.nan_to_num(X, nan=0.0)

        task = self.meta.get("task", "classification")
        threshold = self.meta.get("confidence_threshold", 0.65)

        if task == "classification":
            return self._predict_classification(X, threshold)
        else:
            return self._predict_regression(X)

    def _predict_classification(self, X: np.ndarray, threshold: float) -> Dict:
        proba = self.model.predict_proba(X)[0]   # [p_clean, p_buggy]
        p_buggy = float(proba[1])
        p_clean = float(proba[0])
        confidence = max(p_buggy, p_clean)

        # Convert probability to 0-100 risk score
        ml_risk_score = int(round(p_buggy * 100))

        return {
            "ml_risk_score": ml_risk_score,
            "confidence": round(confidence, 4),
            "needs_ai": confidence < threshold,
            "label": "buggy" if p_buggy >= 0.5 else "clean",
            "probabilities": {
                "buggy": round(p_buggy, 4),
                "clean": round(p_clean, 4),
            },
            "model_version": self.meta.get("version", "unknown"),
        }

    def _predict_regression(self, X: np.ndarray) -> Dict:
        score = float(self.model.predict(X)[0])
        score = max(0.0, min(100.0, score))

        # For regression we don't have a natural confidence measure.
        # Use distance from mid-range as a proxy: scores near 50 are ambiguous.
        confidence = abs(score - 50) / 50

        return {
            "ml_risk_score": int(round(score)),
            "confidence": round(confidence, 4),
            "needs_ai": confidence < 0.3,   # very uncertain near midpoint
            "label": "buggy" if score >= 50 else "clean",
            "probabilities": None,
            "model_version": self.meta.get("version", "unknown"),
        }

    def _no_model_response(self) -> Dict:
        return {
            "ml_risk_score": None,
            "confidence": 0.0,
            "needs_ai": True,
            "label": None,
            "probabilities": None,
            "model_version": None,
            "note": "Model not trained yet. Run train.py to build the ML model.",
        }

    def feature_names(self):
        return FeatureExtractor.FEATURE_NAMES

    def top_features(self, n: int = 10):
        """Return top-N most important features from training metadata."""
        return dict(list(self.meta.get("top_features", {}).items())[:n])
