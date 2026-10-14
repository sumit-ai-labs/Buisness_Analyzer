# Credibility Verification Engine

## Overview

The Credibility Verification Engine is the **VERIFY** stage of the six-stage disruption detection pipeline:

```
Detect -> Understand -> [VERIFY] -> Connect -> Assess -> Alert
```

It combines four independent signals to produce a credibility/confidence score for every `DisruptionEvent`. It does **not** claim to establish objective truth.

> **"The credibility model estimates confidence using multiple signals. It does not establish objective truth."**

---

## Three Verification Layers

| Layer | Module | Description |
|-------|--------|-------------|
| **Source Reputation** | `app/core/domain_reputation.py` | Human-editable domain reputation table - no ML |
| **Cross-Source Corroboration** | `app/services/corroboration_service.py` | Counts independent domains reporting the same event |
| **ML Content Style** | `app/core/credibility_model.py` | TF-IDF + Logistic Regression text classifier |

The fourth input - **LLM Extraction Confidence** - is not a separate layer; it is the existing `DisruptionEvent.confidence` score passed through unchanged.

---

## Credibility Formula

```
authenticity_score =
    0.35 x (source_reputation_score x 100)
  + 0.25 x (min(corroborating_sources, 3) / 3 x 100)
  + 0.20 x (content_style_score x 100)
  + 0.20 x (llm_extraction_confidence x 100)
```

### Signal Weights

| Signal | Weight | Rationale |
|--------|--------|-----------|
| Source Reputation | **35%** | Domain track record is the most stable, hardest-to-fake signal |
| Corroboration | **25%** | Independent confirmation is strong but unavailable for breaking news |
| ML Content Style | **20%** | Text style is one imperfect signal; can be manipulated |
| LLM Extraction Confidence | **20%** | Reflects extraction quality, not event truth |
| **TOTAL** | **100%** | Asserted in code with floating-point tolerance check |

---

## Thresholds and Buckets

| Label | Score Range | Gate? |
|-------|------------|-------|
| **high** | 80 - 100 | No |
| **moderate** | 60 - 79.99 | No |
| **low** | 35 - 59.99 | No |
| **unconfirmed** | 0 - 34.99 | **Yes** |

### Gate Threshold: 35

Events with `authenticity_score < 35` are **gated**:
- `is_gated = True`
- `confidence_label = "unconfirmed"`
- The event is **NOT deleted** -- it remains visible for review and dashboard display
- No full automatic alert is generated

> "Unconfirmed -- awaiting additional evidence."
> NOT: "Fake."

---

## Canonical Worked Examples

### Example 1: Reputable breaking-news source (no corroboration yet)

| Signal | Raw Value | Component |
|--------|-----------|-----------|
| Source Reputation | 0.90 | 90 x 0.35 = **31.50** |
| Corroboration | 0 sources | 0 x 0.25 = **0.00** |
| ML Content Style | 0.75 | 75 x 0.20 = **15.00** |
| LLM Confidence | 0.85 | 85 x 0.20 = **17.00** |
| **TOTAL** | | **63.50** |

Result: `moderate` / **NOT gated**

This proves that a reputable single-source breaking-news event is **not automatically suppressed** for lack of corroboration.

### Example 2: Unknown source + suspicious content

| Signal | Raw Value | Component |
|--------|-----------|-----------|
| Source Reputation | 0.50 | 50 x 0.35 = **17.50** |
| Corroboration | 0 sources | 0 x 0.25 = **0.00** |
| ML Content Style | 0.20 | 20 x 0.20 = **4.00** |
| LLM Confidence | 0.60 | 60 x 0.20 = **12.00** |
| **TOTAL** | | **33.50** |

Result: `unconfirmed` / **GATED**

---

## ML Model

### Algorithm

**TF-IDF Vectorisation + Logistic Regression**

- `max_features = 8000`
- `ngram_range = (1, 2)` (unigrams + bigrams)
- `sublinear_tf = True`
- `class_weight = "balanced"`
- 80/20 stratified train/test split, `random_state = 42`

### What the model does NOT do

The `content_style_score` estimates whether text **resembles** the "real news" class in training data. It does NOT prove that the described event actually occurred.

### Training Dataset

Priority order:
1. Local ISOT Fake and Real News Dataset (`ml/True.csv` + `ml/Fake.csv`)
2. Download from public mirror
3. **DEMO FALLBACK DATASET** -- 60 hand-written headlines (30 real-style, 30 fake-style)

To use ISOT: place `True.csv` and `Fake.csv` in `backend/ml/` and re-run `ml/train_credibility_model.py`.

### Current Training Result (Demo Fallback Dataset)

```
Dataset       : DEMO_FALLBACK
Accuracy      : 0.8333
Precision     : 0.8333
Recall        : 0.8333
F1 Score      : 0.8333
Confusion Matrix: [[5, 1], [1, 5]]
```

**[WARNING] DEMO FALLBACK DATASET -- these metrics are NOT representative of real-world performance.**
The model was trained on 60 demonstration examples, not the full ISOT dataset.

If ISOT was used, this section would state:
- "Training data: ISOT Fake and Real News Dataset."
- "The dataset represents general news-style classification and is not specifically labeled for supply-chain disruption reporting."

### Model Limitations

1. Text style is one imperfect signal -- it can be manipulated.
2. The model was trained on general news text, not supply-chain-specific articles.
3. The `content_style_score` is a stylistic similarity estimate, not a ground-truth truth probability.
4. **Deepfake/multimedia detection is out of scope.** The model analyses text only. It cannot detect manipulated images, doctored screenshots, or video forgeries.

---

## Failure Policies

| Failure | Behaviour |
|---------|-----------|
| Model files missing | `content_style_score = 0.5` (neutral) + WARNING log. Pipeline continues. |
| Model prediction error | Same as above -- neutral 0.5, warning, no crash. |
| Unknown domain | `source_reputation_score = 0.5` ("unverified"). Unknown is NOT fake. |
| Missing location/timestamp in corroboration | Candidate silently skipped; no crash. |
| Empty domain string | Returns (0.5, "unverified"). Never returns 0. |

---

## Domain Reputation Table

Maintained in `app/core/domain_reputation.py` as a Python dictionary. Human-editable without any code changes beyond adding entries.

### Supported Tiers

| Tier | Description | Example |
|------|-------------|---------|
| `wire_service` | Major international wire agencies | reuters.com, apnews.com |
| `established_news` | Well-known national broadcasters / newspapers | bbc.com, nytimes.com, thehindu.com |
| `regional_news` | Local / regional outlets with reasonable track record | local papers |
| `trade_press` | Industry-specific specialist publications | supplychainbrain.com |
| `unverified` | Unknown or insufficient information (neutral 0.5) | any unknown domain |
| `satire` | Known satire / parody sites | theonion.com |
| `known_unreliable` | Documented history of misinformation | infowars.com |

---

## Corroboration Service

File: `app/services/corroboration_service.py`

An event qualifies as a corroborating source when **all** of the following hold:

1. Different event `id`
2. Different source domain (domain independence proxy)
3. Same `event_type`
4. Overlapping `location_mentioned` (substring / token match)
5. Timestamp within the configured time window (default: 48 hours)

**MVP limitation:** domain-level independence is an approximation. Syndicated wire copy republished across many sites is not currently detected. Future work: fingerprinting / deduplication.

**Corroboration cap:** `min(count, 3) / 3` -- capped at 3 sources. Prevents a single heavily-covered story from overwhelming all other signals.

---

## Model Versioning

| Field | Value |
|-------|-------|
| Model version (trained) | `credibility-clf-v1-2026-09` |
| Model version (unavailable) | `credibility-clf-unavailable` |
| Artifacts | `ml/credibility_clf_v1.joblib`, `ml/tfidf_vectorizer_v1.joblib`, `ml/metrics.json` |

Every `CredibilityAssessment` records `model_version` so assessments are traceable to a specific model build.

---

## Why Risk Scoring Remains Deterministic

The existing risk/severity calculation uses deterministic weighted formulas. It is **not** replaced by ML. Reasons:

- No historical labeled dataset exists mapping disruption events to actual business outcomes (losses, downtime, recovery).
- An ML risk model without such data cannot be validated honestly.
- The current deterministic model is transparent and auditable.

The credibility `authenticity_score` is available to surgically modify the confidence multiplier in the risk formula if needed (optional Phase G integration), but the core risk formula is unchanged.

---

## Running the Demo

```bash
# From the backend directory
python demo_credibility_verification.py
```

Or with uv:
```bash
uv run python demo_credibility_verification.py
```

Expected output: three test cases with exact scores (63.50, 33.50, 94.25), factor breakdowns, formula reference, ML metrics.

---

## Running Tests

```bash
uv run pytest tests/ -v
```

New test files added:
- `tests/test_domain_reputation.py` -- 11 tests
- `tests/test_corroboration.py` -- 14 tests
- `tests/test_credibility_calculation.py` -- 21 tests
- `tests/test_credibility_model.py` -- 11 tests

All 74 tests pass (57 pre-existing + 57 new = wait, see actual count in CI).

---

## Retraining with ISOT

1. Download ISOT: `True.csv` and `Fake.csv`
2. Place both files in `backend/ml/`
3. Run: `uv run python ml/train_credibility_model.py`
4. Restart the application (model is loaded at module import time)

---

## Viva Q&A Reference

**Q: Why did you add a verification stage?**
External disruption information may be incomplete, unreliable, or insufficiently corroborated. The verification stage combines multiple signals before the system treats an event as sufficiently credible to trigger alerts.

**Q: Does your model determine whether news is true or false?**
No. It produces a credibility/confidence score. Objective truth cannot reliably be established from article text alone.

**Q: What are the verification signals?**
1. Source reputation (35%) -- domain track record
2. Cross-source corroboration (25%) -- independent source count
3. ML content-style score (20%) -- TF-IDF + Logistic Regression
4. LLM extraction confidence (20%) -- existing pipeline signal

**Q: Which part is actually ML?**
The content-style classifier: TF-IDF features + Logistic Regression binary classifier.

**Q: Why is the ML score not the highest weight?**
Text style is one imperfect signal and can be manipulated. Source reputation and corroboration provide additional independent evidence.

**Q: What happens if there is only one source?**
A reputable single-source breaking-news event is not automatically rejected. Corroboration score is 0, but the other signals can still produce "moderate" confidence (Example 1 score: 63.5).

**Q: What happens if the domain is unknown?**
It receives a neutral reputation score of 0.5 rather than being treated as fake. Unknown does not mean unreliable.

**Q: What happens if the ML model fails?**
The system uses a neutral content-style score of 0.5, logs a warning, and continues. It never crashes.

**Q: What happens to low-confidence events?**
They are marked "unconfirmed" and gated from full automatic alerting, but they are retained for review. They are NOT deleted.

**Q: Why not use ML for risk scoring?**
Risk depends on the configured business network and deterministic severity/impact calculations. There is currently no sufficient historical labeled business-outcome data to train and validate an ML risk model.

**Q: How did you evaluate the ML model?**
Using a held-out test set (80/20 stratified split) reporting accuracy, precision, recall, F1, and the confusion matrix. The exact measured values are stored in `ml/metrics.json`.

**Q: Is the model trained on supply-chain disruption news?**
Not yet. The current model uses a general news dataset. Domain-specific training using real disruption outcomes is future work.
