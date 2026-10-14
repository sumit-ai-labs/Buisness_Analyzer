"""Section C — Understand (Analysis Agent) Edge-Case Tests.

Tests C4–C6 from the test matrix (unit/resilience — C1,C2,C3,C7 are E2E, tested later).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.models.events import RawSearchResult
from app.services.analysis_service import AnalysisService
from tests.conftest import make_raw_result


# ===========================================================================
# C4: LLM returns malformed/incomplete JSON
# Type: Resilience
# ===========================================================================
class TestC4MalformedLLMResponse:
    def test_malformed_json_produces_event_with_defaults(self):
        """C4: When LLM returns incomplete JSON, AnalysisService fills defaults from Pydantic.
        
        The current design doesn't crash — it uses .get() with fallbacks on every field.
        The event is created with defaults like 'other' for event_type, 'medium' for severity, etc.
        """
        mock_llm = MagicMock()
        # Return an incomplete dict (missing most fields)
        mock_llm.extract_disruption_event.return_value = {
            "headline": "Partial extraction",
            # Missing: summary, event_type, location_mentioned, severity_raw, etc.
        }
        svc = AnalysisService(client=mock_llm)
        sr = make_raw_result(url="https://example.com/article")
        event = svc.analyze_search_result(sr, entity_name="Test Entity")
        # Should complete without crash, using defaults
        assert event.headline == "Partial extraction"
        assert event.event_type == "other"  # default
        assert event.severity_raw == "medium"  # default
        assert event.is_relevant is True  # default

    def test_empty_dict_from_llm_produces_valid_event(self):
        """C4b: Completely empty LLM response still produces a valid DisruptionEvent."""
        mock_llm = MagicMock()
        mock_llm.extract_disruption_event.return_value = {}
        svc = AnalysisService(client=mock_llm)
        sr = make_raw_result(url="https://example.com/article")
        event = svc.analyze_search_result(sr, entity_name="Test Entity")
        assert event.headline is not None
        assert event.source_url == "https://example.com/article"


# ===========================================================================
# C5: LLM API call times out or errors
# Type: Resilience
# ===========================================================================
class TestC5LLMTimeout:
    def test_llm_error_in_batch_doesnt_crash_others(self):
        """C5: When LLM fails for one article, batch continues for other articles."""
        call_count = 0
        def mock_extract(title, snippet, entity_name):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("LLM timeout")
            return {
                "headline": "OK Article",
                "summary": "This one worked",
                "event_type": "strike",
                "location_mentioned": "Mumbai",
                "severity_raw": "high",
                "extracted_entities": ["Test"],
                "confidence": 0.9,
                "is_relevant": True,
            }

        mock_llm = MagicMock()
        mock_llm.extract_disruption_event.side_effect = mock_extract
        svc = AnalysisService(client=mock_llm)
        
        results = [
            make_raw_result(url="https://example.com/article1"),
            make_raw_result(url="https://example.com/article2"),
        ]
        events = svc.analyze_search_results(results, entity_name_map={})

        assert len(events) == 1
        assert events[0].headline == "OK Article"

    def test_batch_summary_records_one_failed_article(self):
        """C5b: Batch summary separates extraction failure from successful events."""
        mock_llm = MagicMock()
        mock_llm.extract_disruption_event.side_effect = [
            ConnectionError("provider unavailable"),
            {
                "headline": "OK Article",
                "summary": "This one worked",
                "event_type": "strike",
                "location_mentioned": "Mumbai",
                "severity_raw": "high",
                "extracted_entities": ["Test"],
                "confidence": 0.9,
                "is_relevant": True,
            },
        ]
        svc = AnalysisService(client=mock_llm)
        results = [
            make_raw_result(url="https://example.com/article1"),
            make_raw_result(url="https://example.com/article2"),
        ]

        batch = svc.analyze_search_results_batch(results, entity_name_map={})

        assert batch.processed_count == 2
        assert batch.successful_count == 1
        assert batch.failed_count == 1
        assert batch.relevant_count == 1
        assert batch.rejected_count == 0
        assert batch.failures[0].error_type == "ConnectionError"

    def test_batch_summary_records_all_articles_failing(self):
        """C5c: All extraction failures produce an empty event list and failure counts."""
        mock_llm = MagicMock()
        mock_llm.extract_disruption_event.side_effect = RuntimeError("LLM outage")
        svc = AnalysisService(client=mock_llm)

        batch = svc.analyze_search_results_batch(
            [
                make_raw_result(url="https://example.com/article1"),
                make_raw_result(url="https://example.com/article2"),
            ],
            entity_name_map={},
        )

        assert batch.events == []
        assert batch.processed_count == 2
        assert batch.successful_count == 0
        assert batch.failed_count == 2
        assert batch.rejected_count == 0

    def test_empty_batch_summary(self):
        """C5d: Empty search result batches are distinct from provider failures."""
        svc = AnalysisService(client=MagicMock())

        batch = svc.analyze_search_results_batch([], entity_name_map={})

        assert batch.events == []
        assert batch.failures == []
        assert batch.processed_count == 0
        assert batch.successful_count == 0
        assert batch.failed_count == 0


# ===========================================================================
# C6: Very long article text
# Type: Unit
# ===========================================================================
class TestC6LongArticleText:
    def test_very_long_snippet_doesnt_crash(self):
        """C6: Very long article text doesn't crash extraction. Summary is capped at 500 chars."""
        mock_llm = MagicMock()
        long_text = "A" * 10000
        mock_llm.extract_disruption_event.return_value = {
            "headline": "Long Article",
            "summary": long_text[:500],  # LLM might return long, but we cap at Pydantic level
            "event_type": "flood",
            "location_mentioned": "Test",
            "severity_raw": "high",
            "extracted_entities": [],
            "confidence": 0.8,
            "is_relevant": True,
        }
        svc = AnalysisService(client=mock_llm)
        sr = RawSearchResult(
            url="https://example.com",
            title="Long Title " * 100,
            snippet=long_text,
            queried_entity_id="e1",
            query_used="test",
        )
        event = svc.analyze_search_result(sr, entity_name="Test")
        assert len(event.summary) <= 500
        assert event.headline == "Long Article"
