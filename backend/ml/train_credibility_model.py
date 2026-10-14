# -*- coding: utf-8 -*-
"""ML Training Script -- Phase C of Credibility Verification Engine.

Trains a TF-IDF + Logistic Regression binary classifier that estimates whether
article text resembles the "real news" class in its training data.

IMPORTANT CLARIFICATION:
    This model does NOT determine whether a news article is objectively true.
    Its output (content_style_score) captures stylistic similarity to the
    "real news" class of the training dataset. It is one imperfect signal
    among four used in the final credibility formula.

Dataset priority:
    1. ISOT Fake and Real News Dataset (local copy if available)
    2. ISOT download from a public mirror
    3. Built-in demonstration fallback dataset (clearly labelled)

Usage:
    python backend/ml/train_credibility_model.py

Output:
    backend/ml/credibility_clf_v1.joblib
    backend/ml/tfidf_vectorizer_v1.joblib
    backend/ml/metrics.json
"""

from __future__ import annotations

import json
import os
import sys
import re
import warnings
from datetime import datetime, timezone

# Ensure the 'backend' directory is on the path so 'app' imports work
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ML_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_VERSION = "credibility-clf-v1-2026-09"
CLF_PATH = os.path.join(ML_DIR, "credibility_clf_v1.joblib")
VEC_PATH = os.path.join(ML_DIR, "tfidf_vectorizer_v1.joblib")
METRICS_PATH = os.path.join(ML_DIR, "metrics.json")

RANDOM_STATE = 42
TEST_SIZE = 0.20
MAX_FEATURES = 8000


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------
def clean_text(text: str) -> str:
    """Basic text cleaning: strip HTML tags, lowercase, normalise whitespace."""
    if not isinstance(text, str):
        return ""
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Remove non-alphanumeric characters except spaces
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text)
    # Lowercase and compress whitespace
    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# Dataset loading — priority order
# ---------------------------------------------------------------------------
def _try_load_isot_local() -> pd.DataFrame | None:
    """Attempt to load a local copy of the ISOT dataset."""
    candidates = [
        os.path.join(ML_DIR, "True.csv"),
        os.path.join(ML_DIR, "Fake.csv"),
        os.path.join(ML_DIR, "isot", "True.csv"),
        os.path.join(ML_DIR, "isot", "Fake.csv"),
        os.path.join(_BACKEND_DIR, "data", "True.csv"),
        os.path.join(_BACKEND_DIR, "data", "Fake.csv"),
    ]
    true_path = next((p for p in candidates if "True" in p and os.path.exists(p)), None)
    fake_path = next((p for p in candidates if "Fake" in p and os.path.exists(p)), None)

    if true_path and fake_path:
        print(f"[DATASET] Loading local ISOT: {true_path} + {fake_path}")
        df_true = pd.read_csv(true_path)
        df_fake = pd.read_csv(fake_path)
        df_true["label"] = 1  # real
        df_fake["label"] = 0  # fake
        df = pd.concat([df_true, df_fake], ignore_index=True)
        return df
    return None


def _try_download_isot() -> pd.DataFrame | None:
    """Attempt to download the ISOT dataset from a public mirror."""
    try:
        import urllib.request
        import io

        urls = {
            "true": "https://raw.githubusercontent.com/joolsa/fake_real_news_dataset/master/True.csv",
            "fake": "https://raw.githubusercontent.com/joolsa/fake_real_news_dataset/master/Fake.csv",
        }

        print("[DATASET] Attempting ISOT download …")
        frames = []
        for label_str, url in urls.items():
            req = urllib.request.urlopen(url, timeout=30)
            df_part = pd.read_csv(io.StringIO(req.read().decode("utf-8")))
            df_part["label"] = 1 if label_str == "true" else 0
            frames.append(df_part)
            print(f"[DATASET]   downloaded {label_str}: {len(df_part):,} rows")

        df = pd.concat(frames, ignore_index=True)
        print(f"[DATASET] ISOT download successful: {len(df):,} total rows")
        return df
    except Exception as e:
        print(f"[DATASET] ISOT download failed: {e}")
        return None


def _build_fallback_dataset() -> tuple[pd.DataFrame, bool]:
    """Build a small, clearly-labelled demonstration dataset.

    ⚠️  DEMO FALLBACK DATASET — metrics are NOT representative of
    real-world performance. This dataset exists only to demonstrate
    the pipeline when ISOT is unavailable.
    """
    print("[DATASET] [WARNING] Using DEMO FALLBACK DATASET -- not ISOT.")
    print("[DATASET] [WARNING] Metrics will NOT be representative of real-world performance.")

    real_headlines = [
        "Floods in Gujarat disrupt supply chain for auto manufacturers",
        "Port workers strike causes shipping delays across major terminals",
        "Earthquake damages roads in major industrial corridor",
        "Factory fire in Pune halts production for electronics supplier",
        "Typhoon shuts down key semiconductor manufacturing plants",
        "Drought conditions threaten agricultural supply chains in Maharashtra",
        "Road accident blocks major highway causing logistics delays",
        "Labor union negotiating for wage increase at manufacturing plant",
        "Storm damages infrastructure at major port facility",
        "Regulatory shutdown of chemical plant affects downstream producers",
        "Rail disruption forces freight to switch to road transport",
        "Bridge closure forces traffic detour adding hours to delivery routes",
        "Power outage affects major distribution center operations",
        "Wildfire threatens supply routes in western region",
        "Cyclone warning issued for coastal industrial areas",
        "Oil spill closes major shipping lane for emergency cleanup",
        "Snow storm halts operations at international airport cargo hub",
        "Trade union announces strike action at logistics company",
        "Supplier bankruptcy leaves manufacturers scrambling for alternatives",
        "Water contamination forces closure of food processing plant",
        "Flooding blocks access to key warehouse district",
        "Customs clearance delays affect import shipments at port",
        "Fire at storage facility destroys inventory worth millions",
        "Heatwave triggers power rationing affecting factory production",
        "Riot near industrial zone disrupts worker commutes",
        "Border closure delays cross-border freight shipments",
        "Mining operation suspended after safety inspection finds violations",
        "New trade tariffs disrupt established supply chain flows",
        "Unexpected equipment failure halts assembly line production",
        "Container ship stuck in canal blocks traffic for days",
    ]

    fake_headlines = [
        "Secret underground factory produces unlimited goods without workers!!",
        "Government HIDING massive supply chain collapse to protect big corporations",
        "Miracle solution eliminates all logistics problems OVERNIGHT — they don't want you to know",
        "Exposed: Supply chain 'disruptions' are FAKE staged by globalist elites",
        "Anonymous source reveals entire shipping industry is controlled by shadow group",
        "SHOCKING: Robots already running all factories, humans kept as front",
        "Whistleblower leaks documents proving floods were artificially created",
        "Big media SUPPRESSING truth about fake strike orchestrated by government",
        "Scientists PROVE supply disruptions are chemtrail weather warfare",
        "Insider reveals all port delays are intentional sabotage plan",
        "BANNED VIDEO: The truth about why factories are really closing",
        "They're lying about the earthquake — here's the real hidden agenda",
        "Globalists orchestrating food shortage using fake natural disasters",
        "Deep state controlling all major shipping companies exposed",
        "URGENT: Share before deleted — truth about port closure revealed",
        "You won't believe what they're putting in supply chain disruption reports",
        "MASSIVE cover-up: Floods were engineered to destroy small businesses",
        "Alternative media ONLY: The real reason factories are shutting down",
        "Secret documents reveal strikes are staged to hide true economic collapse",
        "Wake up sheeple! All supply chain news is manufactured propaganda",
        "Exclusive: Shadow network controls all commodity prices worldwide",
        "They want you DISTRACTED while they engineer the real supply chain crisis",
        "PROOF: Every major disruption event is coordinated false flag operation",
        "Mainstream media IGNORES: Real disruptions are bioweapon tests",
        "ALERT: Global supply chain being deliberately collapsed for great reset",
        "Independent report: All port strikes orchestrated by foreign actors",
        "Truth they're hiding: Factories closing due to secret government orders",
        "BOMBSHELL: Supply chain breakdown is pre-planned population control",
        "Leaked emails show disaster events are pre-scheduled by elite group",
        "WARNING: Economic warfare using fake supply disruptions is happening now",
    ]

    data = (
        [{"text": h, "label": 1} for h in real_headlines]
        + [{"text": h, "label": 0} for h in fake_headlines]
    )
    df = pd.DataFrame(data)
    df.columns = ["text", "label"]
    return df, True  # is_fallback=True


def load_dataset() -> tuple[pd.DataFrame, str, bool]:
    """Load training data in priority order.

    Returns
    -------
    (dataframe, dataset_name, is_fallback)
    """
    # Priority 1: local ISOT
    df = _try_load_isot_local()
    if df is not None:
        return df, "ISOT (local)", False

    # Priority 2: download ISOT
    df = _try_download_isot()
    if df is not None:
        return df, "ISOT (downloaded)", False

    # Priority 3: fallback
    df, is_fallback = _build_fallback_dataset()
    return df, "DEMO_FALLBACK", True


# ---------------------------------------------------------------------------
# Feature preparation
# ---------------------------------------------------------------------------
def prepare_text_column(df: pd.DataFrame) -> pd.Series:
    """Combine title/headline + body text into a single feature string."""
    # Handle ISOT column names (title, text) or our fallback (text)
    parts = []
    if "title" in df.columns:
        parts.append(df["title"].fillna("").astype(str))
    if "text" in df.columns:
        parts.append(df["text"].fillna("").astype(str))
    elif "headline" in df.columns:
        parts.append(df["headline"].fillna("").astype(str))

    if not parts:
        raise ValueError("Dataset has no recognisable text column (title/text/headline).")

    combined = parts[0]
    for part in parts[1:]:
        combined = combined + " " + part

    return combined.apply(clean_text)


# ---------------------------------------------------------------------------
# Main training routine
# ---------------------------------------------------------------------------
def train_and_evaluate():
    print("=" * 60)
    print("CREDIBILITY CLASSIFIER — TRAINING")
    print(f"Model version: {MODEL_VERSION}")
    print("=" * 60)

    # Load data
    df, dataset_name, is_fallback = load_dataset()
    print(f"\n[TRAIN] Dataset: {dataset_name}")
    print(f"[TRAIN] Total samples: {len(df):,}")
    print(f"[TRAIN] Label distribution:\n{df['label'].value_counts().to_string()}")

    # Prepare features
    X_text = prepare_text_column(df)
    y = df["label"].values

    # Train/test split — stratified
    X_train_text, X_test_text, y_train, y_test = train_test_split(
        X_text, y,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=y,
    )
    print(f"\n[TRAIN] Train: {len(X_train_text):,}  |  Test: {len(X_test_text):,}")

    # TF-IDF vectoriser
    print("[TRAIN] Fitting TF-IDF vectoriser …")
    vectorizer = TfidfVectorizer(
        max_features=MAX_FEATURES,
        ngram_range=(1, 2),
        sublinear_tf=True,
        lowercase=True,
        strip_accents="unicode",
        min_df=2 if len(X_train_text) > 100 else 1,
    )
    X_train = vectorizer.fit_transform(X_train_text)
    X_test = vectorizer.transform(X_test_text)

    # Logistic Regression classifier
    print("[TRAIN] Training Logistic Regression …")
    clf = LogisticRegression(
        C=1.0,
        max_iter=1000,
        random_state=RANDOM_STATE,
        class_weight="balanced",
        solver="lbfgs",
    )
    clf.fit(X_train, y_train)

    # Evaluation
    y_pred = clf.predict(X_test)
    y_prob = clf.predict_proba(X_test)

    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, average="binary", zero_division=0)
    recall = recall_score(y_test, y_pred, average="binary", zero_division=0)
    f1 = f1_score(y_test, y_pred, average="binary", zero_division=0)
    cm = confusion_matrix(y_test, y_pred).tolist()

    print("\n" + "=" * 60)
    print("EVALUATION RESULTS")
    print("=" * 60)
    if is_fallback:
        print("[WARNING] DEMO FALLBACK DATASET -- metrics are NOT representative of real-world performance.")
    print(f"Accuracy  : {accuracy:.4f}")
    print(f"Precision : {precision:.4f}")
    print(f"Recall    : {recall:.4f}")
    print(f"F1 Score  : {f1:.4f}")
    print(f"Confusion Matrix:\n{np.array(cm)}")
    print("\nFull Classification Report:")
    print(classification_report(y_test, y_pred, target_names=["fake/suspicious", "real/credible"], zero_division=0))

    # Verify class mapping
    real_class_index = list(clf.classes_).index(1)
    print(f"[TRAIN] Model classes: {clf.classes_} | Real-class index: {real_class_index}")

    # Save artifacts
    os.makedirs(ML_DIR, exist_ok=True)
    joblib.dump(clf, CLF_PATH)
    joblib.dump(vectorizer, VEC_PATH)
    print(f"\n[TRAIN] Saved classifier → {CLF_PATH}")
    print(f"[TRAIN] Saved vectoriser  → {VEC_PATH}")

    # Save metrics.json — NEVER invent values; always use measured results
    metrics = {
        "model_version": MODEL_VERSION,
        "dataset": dataset_name,
        "is_fallback_dataset": is_fallback,
        "fallback_warning": (
            "DEMO FALLBACK DATASET — metrics are NOT representative of real-world performance."
            if is_fallback else None
        ),
        "train_samples": int(len(X_train_text)),
        "test_samples": int(len(X_test_text)),
        "random_state": RANDOM_STATE,
        "test_size": TEST_SIZE,
        "max_features": MAX_FEATURES,
        "accuracy": round(float(accuracy), 4),
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1": round(float(f1), 4),
        "confusion_matrix": cm,
        "model_classes": clf.classes_.tolist(),
        "real_class_index": int(real_class_index),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "limitations": [
            "Model trained on general news-style dataset, not supply-chain-specific text.",
            "Text style is one signal among four in the credibility formula.",
            "This model does not establish whether a news event actually occurred.",
            "Deepfake/multimedia detection is out of scope.",
        ],
    }

    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print(f"[TRAIN] Saved metrics    → {METRICS_PATH}")

    print("\n[TRAIN] Training complete.")
    return clf, vectorizer, metrics


if __name__ == "__main__":
    train_and_evaluate()
