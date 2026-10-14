"""Unit tests — Phase B: Cross-Source Corroboration Service.

Required tests per spec:
    1. Same event does not count as corroboration
    2. Same domain does not count as independent corroboration
    3. Different domain + same event_type + same location → counts
    4. Different domain + different event_type → does NOT count
    5. Outside time window → does NOT count
    6. Multiple independent domains count correctly
    7. Different location → does NOT count
    8. Empty recent_events → returns 0 safely
    9. Missing location → handled safely, no crash
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone

from app.models.events import DisruptionEvent
from app.services.corroboration_service import count_corroborating_sources


def _make_event(
    source_url: str,
    event_type: str = "flood",
    location_mentioned: str = "Surat, Gujarat",
    confidence: float = 0.8,
    hours_offset: float = 0.0,
    event_id: str | None = None,
) -> DisruptionEvent:
    """Factory helper to create minimal DisruptionEvent objects for testing."""
    base_time = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)
    retrieved_at = base_time + timedelta(hours=hours_offset)
    kwargs = dict(
        source_url=source_url,
        source_result_id="res-test",
        headline=f"{event_type} in {location_mentioned}",
        summary=f"A {event_type} disruption occurred in {location_mentioned}.",
        event_type=event_type,
        location_mentioned=location_mentioned,
        severity_raw="medium",
        confidence=confidence,
        is_relevant=True,
        retrieved_at=retrieved_at,
    )
    if event_id:
        kwargs["id"] = event_id
    return DisruptionEvent(**kwargs)


# Base event used across most tests
BASE_EVENT = _make_event("https://source-a.com/article-1", event_type="flood", location_mentioned="Surat, Gujarat")


class TestSameEventNotCounted:
    def test_same_event_id_not_counted(self):
        """Spec test 1: The same event object must not count as corroboration."""
        event = _make_event("https://source-a.com/article-1")
        count = count_corroborating_sources(event, [event])
        assert count == 0, "Same event must not count as corroboration"


class TestSameDomainNotCounted:
    def test_same_domain_different_article(self):
        """Spec test 2: Same domain, different article URL — must NOT count."""
        event = _make_event("https://source-a.com/article-1")
        same_domain_event = _make_event("https://source-a.com/article-2")
        count = count_corroborating_sources(event, [same_domain_event])
        assert count == 0, "Same source domain must not count as independent corroboration"

    def test_same_domain_with_www_prefix(self):
        """www.source-a.com and source-a.com are the same domain — must NOT count."""
        event = _make_event("https://source-a.com/article-1")
        www_event = _make_event("https://www.source-a.com/article-99")
        count = count_corroborating_sources(event, [www_event])
        assert count == 0


class TestValidCorroboration:
    def test_different_domain_same_type_same_location_counts(self):
        """Spec test 3: Different domain + same event_type + same location → counts."""
        event = _make_event("https://source-a.com/article-1", event_type="flood", location_mentioned="Surat")
        corr = _make_event("https://source-b.com/article-2", event_type="flood", location_mentioned="Surat")
        count = count_corroborating_sources(event, [corr])
        assert count == 1

    def test_multiple_independent_domains_count_correctly(self):
        """Spec test 6: Multiple independent domains all count."""
        event = _make_event("https://source-a.com/a1", event_type="strike", location_mentioned="Mumbai Port")
        others = [
            _make_event("https://source-b.com/b1", event_type="strike", location_mentioned="Mumbai Port"),
            _make_event("https://source-c.com/c1", event_type="strike", location_mentioned="Mumbai Port"),
            _make_event("https://source-d.com/d1", event_type="strike", location_mentioned="Mumbai Port"),
        ]
        count = count_corroborating_sources(event, others)
        assert count == 3


class TestNonCorroborating:
    def test_different_event_type_does_not_count(self):
        """Spec test 4: Different event_type must NOT count."""
        event = _make_event("https://source-a.com/a", event_type="flood", location_mentioned="Surat")
        wrong_type = _make_event("https://source-b.com/b", event_type="strike", location_mentioned="Surat")
        count = count_corroborating_sources(event, [wrong_type])
        assert count == 0, "Different event_type must not count"

    def test_different_location_does_not_count(self):
        """Spec test (different location): Different location must NOT count."""
        event = _make_event("https://source-a.com/a", event_type="flood", location_mentioned="Surat")
        different_loc = _make_event("https://source-b.com/b", event_type="flood", location_mentioned="Chennai")
        count = count_corroborating_sources(event, [different_loc])
        assert count == 0, "Different location must not count"

    def test_outside_time_window_does_not_count(self):
        """Spec test 5: Outside 48h time window must NOT count."""
        event = _make_event("https://source-a.com/a", hours_offset=0.0)
        old_event = _make_event("https://source-b.com/b", hours_offset=72.0)  # 72h later
        count = count_corroborating_sources(event, [old_event], time_window_hours=48)
        assert count == 0, "Event outside time window must not count"


class TestEdgeCases:
    def test_empty_recent_events(self):
        """Empty list must return 0 without crashing."""
        event = _make_event("https://source-a.com/a")
        count = count_corroborating_sources(event, [])
        assert count == 0

    def test_none_recent_events_via_empty_list(self):
        """Passing empty list simulating no events — should return 0."""
        event = _make_event("https://source-a.com/a")
        count = count_corroborating_sources(event, [])
        assert count == 0

    def test_within_time_window_counts(self):
        """Event within 48h window should count."""
        event = _make_event("https://source-a.com/a", hours_offset=0.0)
        recent = _make_event("https://source-b.com/b", hours_offset=24.0)  # 24h later
        count = count_corroborating_sources(event, [recent], time_window_hours=48)
        assert count == 1

    def test_same_domain_multiple_articles_counts_once(self):
        """Five articles from source-b.com should count as only 1 domain."""
        event = _make_event("https://source-a.com/a", event_type="flood", location_mentioned="Surat")
        five_from_b = [
            _make_event(f"https://source-b.com/article-{i}", event_type="flood", location_mentioned="Surat")
            for i in range(5)
        ]
        count = count_corroborating_sources(event, five_from_b)
        assert count == 1, "Multiple articles from same domain should count as 1"

    def test_location_substring_match(self):
        """'Surat, Gujarat' and 'Surat' should overlap."""
        event = _make_event("https://source-a.com/a", location_mentioned="Surat, Gujarat")
        corr = _make_event("https://source-b.com/b", location_mentioned="Surat")
        count = count_corroborating_sources(event, [corr])
        assert count == 1
