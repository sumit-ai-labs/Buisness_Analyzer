"""Pytest integration test for Phase 2 Labeled Evaluation Benchmark."""

import pytest
from evaluate_phase2 import run_evaluation


@pytest.mark.asyncio
async def test_phase2_labeled_evaluation_metrics():
    metrics = await run_evaluation()

    assert metrics["total_cases"] >= 16
    assert metrics["relevant_event_precision"] >= 0.90, f"Precision was {metrics['relevant_event_precision']}"
    assert metrics["relevant_event_recall"] >= 0.90, f"Recall was {metrics['relevant_event_recall']}"
    assert metrics["resolved_event_false_positive_rate"] == 0.0, f"Resolved FP rate was {metrics['resolved_event_false_positive_rate']}"
    assert metrics["weather_classification_accuracy"] >= 0.90, f"Weather accuracy was {metrics['weather_classification_accuracy']}"
    assert metrics["geographic_match_accuracy"] >= 0.90, f"Geo accuracy was {metrics['geographic_match_accuracy']}"
    # Human-review rate should be non-zero (routing unconfirmed/ambiguous cases to analyst)
    assert 0.10 <= metrics["human_review_rate"] <= 0.35, f"Review rate was {metrics['human_review_rate']}"
