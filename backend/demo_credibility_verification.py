#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Credibility Verification Engine Demo — Phase F.

Demonstrates the complete verification workflow using the two canonical worked examples
defined in the verification engine design.

Usage:
    python backend/demo_credibility_verification.py

Or from inside the backend directory:
    python demo_credibility_verification.py

This demo uses the SAME verification functions as the production application.
The calculation logic is NOT duplicated here.

DISCLAIMER:
    The credibility scores produced here are estimates based on multiple imperfect
    signals (source reputation, corroboration, ML content style, LLM confidence).
    This system does NOT claim to determine whether a news event is objectively true.
"""

from __future__ import annotations

import os
import sys
import json

# Ensure backend/ is in path regardless of where script is run from
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

# Suppress logging output during demo for clean console display
import logging
logging.getLogger("business_disruption").setLevel(logging.WARNING)

from app.models.events import DisruptionEvent
from app.services.verification_service import VerificationService
from app.models.credibility import CredibilityAssessment


def _print_separator(char: str = "=", width: int = 54):
    print(char * width)


def _print_assessment(case_title: str, description: str, assessment: CredibilityAssessment,
                      source_reputation: float, corroboration: int,
                      content_style_score: float, llm_confidence: float):
    """Print a formatted assessment result block."""
    _print_separator()
    print(f"CASE: {case_title}")
    print(f"      {description}")
    _print_separator("-", 54)
    print()
    print(f"  Source Reputation Score : {source_reputation:.2f}")
    print(f"  Corroborating Sources   : {corroboration}")
    print(f"  ML Content-Style Score  : {content_style_score:.2f}")
    print(f"  LLM Extraction Conf.    : {llm_confidence:.2f}")
    print()
    _print_separator("-", 54)
    print(f"  Authenticity Score      : {assessment.authenticity_score:.2f} / 100")
    print(f"  Confidence              : {assessment.confidence_label.upper()}")
    print(f"  Verification Status     : {'GATED (Unconfirmed)' if assessment.is_gated else 'NOT GATED'}")
    _print_separator("-", 54)
    print()
    print("  Factor Contributions (weighted):")
    f = assessment.factors
    print(f"    Source Reputation      : {f['source_reputation']:.2f}")
    print(f"    Corroboration          : {f['corroboration']:.2f}")
    print(f"    Content Style (ML)     : {f['content_style']:.2f}")
    print(f"    LLM Extraction Conf.   : {f['llm_extraction_confidence']:.2f}")
    print(f"                             ------")
    total = sum(f.values())
    print(f"    TOTAL                  : {total:.2f}")
    print()
    print(f"  Source Domain           : {assessment.source_domain}")
    print(f"  Source Tier             : {assessment.source_tier}")
    print(f"  ML Model Version        : {assessment.model_version}")
    print()


def _print_model_metrics():
    """Load and display the actual ML metrics from metrics.json."""
    ml_dir = os.path.join(_SCRIPT_DIR, "ml")
    metrics_path = os.path.join(ml_dir, "metrics.json")
    if not os.path.exists(metrics_path):
        print("  [metrics.json not found — run ml/train_credibility_model.py first]")
        return

    with open(metrics_path, "r", encoding="utf-8") as f:
        m = json.load(f)

    print("  ML Classifier Evaluation Metrics:")
    print(f"    Model Version : {m.get('model_version', 'N/A')}")
    print(f"    Dataset       : {m.get('dataset', 'N/A')}")
    if m.get("is_fallback_dataset"):
        print("    [WARNING] DEMO FALLBACK DATASET -- metrics are NOT")
        print("    representative of real-world performance.")
    print(f"    Train samples : {m.get('train_samples', 'N/A')}")
    print(f"    Test samples  : {m.get('test_samples', 'N/A')}")
    print(f"    Accuracy      : {m.get('accuracy', 'N/A')}")
    print(f"    Precision     : {m.get('precision', 'N/A')}")
    print(f"    Recall        : {m.get('recall', 'N/A')}")
    print(f"    F1 Score      : {m.get('f1', 'N/A')}")
    cm = m.get("confusion_matrix", [])
    if cm:
        print(f"    Confusion Matrix:")
        for row in cm:
            print(f"      {row}")


def main():
    service = VerificationService()

    # -----------------------------------------------------------------------
    print()
    _print_separator("=", 54)
    print("   CREDIBILITY VERIFICATION ENGINE DEMO")
    print("   Business Disruption Early-Warning System")
    _print_separator("=", 54)
    print()
    print("  DISCLAIMER:")
    print("  This system produces credibility/confidence scores.")
    print("  It does NOT determine whether news is objectively true.")
    print("  Multiple imperfect signals are combined, not claimed")
    print("  to produce ground-truth verification.")
    print()

    # -----------------------------------------------------------------------
    # CASE 1: Reputable single-source breaking news
    # Expected: score=63.5, label=moderate, not gated
    # -----------------------------------------------------------------------
    event_1 = DisruptionEvent(
        source_url="https://reuters.com/supply-chain/port-strike-2026",
        source_result_id="res-demo-001",
        headline="Major port strike halts container shipping",
        summary="Dock workers at key port have begun an indefinite strike, halting container operations.",
        event_type="strike",
        location_mentioned="Mumbai Port, India",
        severity_raw="high",
        confidence=0.85,
        is_relevant=True,
    )

    assessment_1 = service.verify(
        event_1,
        recent_events=[],
        override_source_reputation=0.90,
        override_corroboration_count=0,
        override_content_style_score=0.75,
    )

    _print_assessment(
        case_title="1 — Reputable Single-Source Breaking News",
        description="Reuters report on port strike; no corroboration yet (breaking news)",
        assessment=assessment_1,
        source_reputation=0.90,
        corroboration=0,
        content_style_score=0.75,
        llm_confidence=0.85,
    )

    # -----------------------------------------------------------------------
    # CASE 2: Unknown source + suspicious content
    # Expected: score=33.5, label=unconfirmed, gated
    # -----------------------------------------------------------------------
    event_2 = DisruptionEvent(
        source_url="https://unknown-source-xyz.com/supply-shock",
        source_result_id="res-demo-002",
        headline="GLOBALISTS hiding MASSIVE supply chain COLLAPSE!!!",
        summary="Anonymous insider claims secret shutdown of all ports engineered by shadow group.",
        event_type="closure",
        location_mentioned="Chennai Port, India",
        severity_raw="high",
        confidence=0.60,
        is_relevant=True,
    )

    assessment_2 = service.verify(
        event_2,
        recent_events=[],
        override_source_reputation=0.50,
        override_corroboration_count=0,
        override_content_style_score=0.20,
    )

    _print_assessment(
        case_title="2 — Unknown Source + Suspicious Content",
        description="Unknown domain, no corroboration, sensationalist headline",
        assessment=assessment_2,
        source_reputation=0.50,
        corroboration=0,
        content_style_score=0.20,
        llm_confidence=0.60,
    )

    # -----------------------------------------------------------------------
    # CASE 3: Well-corroborated event (bonus demo case)
    # -----------------------------------------------------------------------
    event_3 = DisruptionEvent(
        source_url="https://apnews.com/flood-gujarat-2026",
        source_result_id="res-demo-003",
        headline="Severe flooding forces factory closures across Gujarat",
        summary="Widespread flooding has shut down multiple manufacturing facilities in the Gujarat industrial belt.",
        event_type="flood",
        location_mentioned="Gujarat, India",
        severity_raw="high",
        confidence=0.92,
        is_relevant=True,
    )

    assessment_3 = service.verify(
        event_3,
        recent_events=[],
        override_source_reputation=0.95,
        override_corroboration_count=3,
        override_content_style_score=0.88,
    )

    _print_assessment(
        case_title="3 — Well-Corroborated Event (AP News + 3 sources)",
        description="Wire service report, corroborated by 3 independent sources",
        assessment=assessment_3,
        source_reputation=0.95,
        corroboration=3,
        content_style_score=0.88,
        llm_confidence=0.92,
    )

    # -----------------------------------------------------------------------
    # Verification formula summary
    # -----------------------------------------------------------------------
    _print_separator("=", 54)
    print("  VERIFICATION FORMULA REFERENCE")
    _print_separator("-", 54)
    print("  Signal              Weight")
    print("  Source Reputation   35%")
    print("  Corroboration       25%  (capped at 3 sources)")
    print("  ML Content Style    20%  (TF-IDF + Logistic Regression)")
    print("  LLM Confidence      20%  (pass-through from extraction)")
    print()
    print("  Thresholds:")
    print("    >= 80  -> HIGH")
    print("    >= 60  -> MODERATE")
    print("    >= 35  -> LOW")
    print("    <  35  -> UNCONFIRMED (gated from auto-alert)")
    print()
    print("  Gate policy: gated events are NOT deleted.")
    print("  They are retained for review and dashboard display.")
    print()

    # -----------------------------------------------------------------------
    # ML metrics
    # -----------------------------------------------------------------------
    _print_separator("=", 54)
    print("  ML MODEL METRICS (from training)")
    _print_separator("-", 54)
    _print_model_metrics()
    print()

    # -----------------------------------------------------------------------
    # Results summary table
    # -----------------------------------------------------------------------
    _print_separator("=", 54)
    print("  RESULTS SUMMARY")
    _print_separator("-", 54)
    print(f"  {'Case':<40} {'Score':>7}  {'Label':<12}  {'Gated'}")
    _print_separator("-", 54)
    cases = [
        ("Reputable breaking news (Case 1)", assessment_1),
        ("Unknown source + suspicious (Case 2)", assessment_2),
        ("Well-corroborated wire service (Case 3)", assessment_3),
    ]
    for title, a in cases:
        gated_str = "YES" if a.is_gated else "NO"
        print(f"  {title:<40} {a.authenticity_score:>6.2f}  {a.confidence_label.upper():<12}  {gated_str}")
    print()

    _print_separator("=", 54)
    print("  DEMO COMPLETE")
    _print_separator("=", 54)
    print()


if __name__ == "__main__":
    main()
