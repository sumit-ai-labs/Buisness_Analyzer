"""Credibility ML Model Serving — Phase C (serving) of Credibility Verification Engine.

Loads the trained TF-IDF + Logistic Regression classifier ONCE at module import
time and exposes a single ``predict_style_score(text)`` function.

IMPORTANT:
    content_style_score estimates whether text *resembles* the "real news" class
    in the training data. It does NOT prove that the reported event actually occurred.

Failure policy:
    If the model files are missing or corrupt, ``predict_style_score`` returns 0.5
    (neutral) and logs a WARNING. It never raises and never returns 0 or 1.
"""

from __future__ import annotations

import logging
import os
import re

logger = logging.getLogger("business_disruption")

# ---------------------------------------------------------------------------
# Model paths
# ---------------------------------------------------------------------------
_ML_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "ml")
_CLF_PATH = os.path.join(_ML_DIR, "credibility_clf_v1.joblib")
_VEC_PATH = os.path.join(_ML_DIR, "tfidf_vectorizer_v1.joblib")
_METRICS_PATH = os.path.join(_ML_DIR, "metrics.json")

# Neutral fallback when model is unavailable
_NEUTRAL_SCORE: float = 0.5
_MODEL_VERSION_UNAVAILABLE = "credibility-clf-unavailable"

# ---------------------------------------------------------------------------
# Module-level singletons — loaded once
# ---------------------------------------------------------------------------
_clf = None
_vectorizer = None
_model_version: str = _MODEL_VERSION_UNAVAILABLE
_real_class_index: int = 1  # will be corrected after loading
_last_error: Optional[str] = None
_error_count: int = 0


def _clean_text(text: str) -> str:
    """Mirror of training-time text cleaning."""
    if not isinstance(text, str):
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text)
    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def load_model() -> bool:
    """Attempt to load the classifier and vectoriser from disk.

    Returns True if loading succeeded, False otherwise.
    Call this explicitly during application startup if desired;
    the module will also auto-load on first call to predict_style_score.
    """
    global _clf, _vectorizer, _model_version, _real_class_index

    try:
        import joblib
        import json

        if not os.path.exists(_CLF_PATH) or not os.path.exists(_VEC_PATH):
            logger.warning(
                f"[VERIFY][WARNING] Credibility model files not found at {_ML_DIR}. "
                "Run ml/train_credibility_model.py first. Using neutral content_style_score=0.5."
            )
            return False

        _clf = joblib.load(_CLF_PATH)
        _vectorizer = joblib.load(_VEC_PATH)

        # Determine which class index corresponds to label=1 (real)
        if hasattr(_clf, "classes_"):
            classes = list(_clf.classes_)
            if 1 in classes:
                _real_class_index = classes.index(1)
            else:
                _real_class_index = 1  # safe default

        # Load version from metrics.json if available
        if os.path.exists(_METRICS_PATH):
            with open(_METRICS_PATH, "r", encoding="utf-8") as f:
                metrics = json.load(f)
            _model_version = metrics.get("model_version", "credibility-clf-v1")

        logger.info(
            f"[CREDIBILITY MODEL] Loaded: {_model_version} | "
            f"Real class index: {_real_class_index}"
        )
        return True

    except Exception as exc:
        logger.warning(
            f"[VERIFY][WARNING] Failed to load credibility model: {exc}. "
            "Using neutral content_style_score=0.5."
        )
        _last_error = f"Failed to load: {exc}"
        _clf = None
        _vectorizer = None
        return False


def get_model_version() -> str:
    """Return the current model version string."""
    return _model_version


def is_loaded() -> bool:
    """Check if model and vectorizer are successfully loaded."""
    return _clf is not None and _vectorizer is not None


def get_last_error() -> Optional[str]:
    """Return last error encountered during loading or inference."""
    return _last_error


def get_error_count() -> int:
    """Return total count of inference errors encountered."""
    return _error_count


def get_model_status() -> dict:
    """Return comprehensive model health for observability."""
    return {
        "loaded": is_loaded(),
        "version": _model_version,
        "last_error": _last_error,
        "error_count": _error_count,
    }


def predict_style_score(text: str) -> float:
    """Predict the content-style score for a text string.

    The score estimates how closely the text resembles the "real news" class
    in the training data.  It is NOT a ground-truth verification.

    Parameters
    ----------
    text:
        Headline and/or body text from the news source.

    Returns
    -------
    float in [0.0, 1.0]
        Higher → more similar to "real news" style.
        Lower  → more similar to "fake/suspicious news" style.
        0.5    → neutral (returned when model is unavailable or on error).

    Failure policy:
        Any exception → log error with stack trace → record last_error → return 0.5.
        Never crashes the pipeline.
    """
    global _clf, _vectorizer, _last_error, _error_count

    # Auto-load on first call
    if _clf is None or _vectorizer is None:
        load_model()

    if _clf is None or _vectorizer is None:
        _last_error = "Credibility model artifacts unavailable"
        logger.warning(
            "[VERIFY][WARNING] Credibility model unavailable. "
            "Using neutral content_style_score=0.5."
        )
        return _NEUTRAL_SCORE

    try:
        cleaned = _clean_text(text)
        if not cleaned:
            return _NEUTRAL_SCORE

        X = _vectorizer.transform([cleaned])
        proba = _clf.predict_proba(X)
        score = float(proba[0, _real_class_index])
        # Clamp to [0, 1] for safety
        return max(0.0, min(1.0, score))

    except Exception as exc:
        _last_error = f"Inference failure: {exc}"
        _error_count += 1
        logger.error(
            f"[VERIFY][INFERENCE_ERROR] Error during credibility prediction: {exc}. "
            "Returning neutral content_style_score=0.5.",
            exc_info=True,
        )
        return _NEUTRAL_SCORE


# ---------------------------------------------------------------------------
# Attempt to load at import time (non-fatal)
# ---------------------------------------------------------------------------
load_model()
