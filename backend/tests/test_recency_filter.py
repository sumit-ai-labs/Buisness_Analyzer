"""Tests for the stale-news freshness filter (Part A of recency fix).

Covers:
- filter_by_recency with 3-date fixture (today, 10 days, 60 days)
- sort_by_recency ordering
- _parse_published_date edge cases
- published_at propagation from RawSearchResult → DisruptionEvent
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.events import RawSearchResult, DisruptionEvent
from app.services.research_service import (
    filter_by_recency,
    sort_by_recency,
    _parse_published_date,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_raw(url: str, published_at: datetime | None = None) -> RawSearchResult:
    """Create a minimal RawSearchResult for testing."""
    return RawSearchResult(
        url=url,
        title="Test Article",
        snippet="Some disruption happened.",
        queried_entity_id="entity-001",
        query_used="test query",
        published_at=published_at,
    )


# ---------------------------------------------------------------------------
# filter_by_recency — core 3-date fixture
# ---------------------------------------------------------------------------


class TestFilterByRecency:
    """Required testing checkpoint: today, 10-day, and 60-day articles."""

    def test_three_date_fixture(self):
        """60-day-old article is dropped; today and 10-day-old are kept."""
        now = datetime.now(timezone.utc)
        result_today = _make_raw("https://news.example.com/today", now)
        result_10d = _make_raw(
            "https://news.example.com/10days",
            now - timedelta(days=10),
        )
        result_60d = _make_raw(
            "https://news.example.com/60days",
            now - timedelta(days=60),
        )

        filtered = filter_by_recency(
            [result_today, result_10d, result_60d], max_age_days=14
        )

        assert len(filtered) == 2, f"Expected 2 results, got {len(filtered)}"
        urls = {r.url for r in filtered}
        assert "https://news.example.com/today" in urls
        assert "https://news.example.com/10days" in urls
        assert "https://news.example.com/60days" not in urls

    def test_none_published_at_is_dropped_by_default(self):
        """Articles with unknown publication date are dropped by default."""
        result_unknown = _make_raw("https://news.example.com/unknown", None)
        result_old = _make_raw(
            "https://news.example.com/old",
            datetime.now(timezone.utc) - timedelta(days=60),
        )

        filtered = filter_by_recency([result_unknown, result_old], max_age_days=14)

        assert filtered == []

    def test_none_published_at_can_be_kept_by_override(self):
        """Undated articles can be kept only with an explicit override."""
        result_unknown = _make_raw("https://news.example.com/unknown", None)

        filtered = filter_by_recency([result_unknown], max_age_days=14, keep_undated=True)

        assert len(filtered) == 1
        assert filtered[0].url == "https://news.example.com/unknown"

    def test_custom_max_age(self):
        """Respects a custom max_age_days value."""
        now = datetime.now(timezone.utc)
        result_5d = _make_raw("https://a.com/5d", now - timedelta(days=5))
        result_20d = _make_raw("https://a.com/20d", now - timedelta(days=20))

        # With 7-day window, the 20-day result is dropped
        filtered = filter_by_recency([result_5d, result_20d], max_age_days=7)
        assert len(filtered) == 1
        assert filtered[0].url == "https://a.com/5d"

        # With 30-day window, both are kept
        filtered = filter_by_recency([result_5d, result_20d], max_age_days=30)
        assert len(filtered) == 2

    def test_empty_input(self):
        """Empty list in, empty list out."""
        assert filter_by_recency([], max_age_days=14) == []

    def test_boundary_exactly_at_cutoff(self):
        """An article published exactly at the cutoff boundary is kept (uses tiny buffer for timing)."""
        now = datetime.now(timezone.utc)
        # Place the article 13 days 23 hours ago — clearly inside 14-day window
        result_inside = _make_raw(
            "https://a.com/boundary",
            now - timedelta(days=13, hours=23),
        )
        filtered = filter_by_recency([result_inside], max_age_days=14)
        assert len(filtered) == 1

        # Place an article clearly outside the window (15 days)
        result_outside = _make_raw(
            "https://a.com/outside",
            now - timedelta(days=15),
        )
        filtered = filter_by_recency([result_outside], max_age_days=14)
        assert len(filtered) == 0


# ---------------------------------------------------------------------------
# sort_by_recency
# ---------------------------------------------------------------------------


class TestSortByRecency:
    def test_sorts_newest_first(self):
        now = datetime.now(timezone.utc)
        r1 = _make_raw("https://a.com/old", now - timedelta(days=10))
        r2 = _make_raw("https://a.com/new", now - timedelta(days=1))
        r3 = _make_raw("https://a.com/mid", now - timedelta(days=5))

        sorted_results = sort_by_recency([r1, r2, r3])
        assert [r.url for r in sorted_results] == [
            "https://a.com/new",
            "https://a.com/mid",
            "https://a.com/old",
        ]

    def test_none_dates_go_last(self):
        now = datetime.now(timezone.utc)
        r_known = _make_raw("https://a.com/known", now - timedelta(days=1))
        r_unknown = _make_raw("https://a.com/unknown", None)

        sorted_results = sort_by_recency([r_unknown, r_known])
        assert sorted_results[0].url == "https://a.com/known"
        assert sorted_results[1].url == "https://a.com/unknown"


# ---------------------------------------------------------------------------
# _parse_published_date
# ---------------------------------------------------------------------------


class TestParsePublishedDate:
    def test_iso_format(self):
        dt = _parse_published_date("2026-09-25T14:30:00+00:00")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 9
        assert dt.day == 25

    def test_date_only(self):
        dt = _parse_published_date("2026-09-25")
        assert dt is not None
        assert dt.tzinfo == timezone.utc

    def test_none_input(self):
        assert _parse_published_date(None) is None

    def test_empty_string(self):
        assert _parse_published_date("") is None

    def test_garbage_input(self):
        assert _parse_published_date("not-a-date") is None


# ---------------------------------------------------------------------------
# published_at propagation: RawSearchResult → DisruptionEvent
# ---------------------------------------------------------------------------


class TestPublishedAtPropagation:
    def test_raw_result_stores_published_at(self):
        now = datetime.now(timezone.utc)
        r = RawSearchResult(
            url="https://example.com",
            title="Test",
            snippet="Test snippet",
            queried_entity_id="e1",
            query_used="q",
            published_at=now,
        )
        assert r.published_at == now

    def test_disruption_event_stores_published_at(self):
        now = datetime.now(timezone.utc)
        e = DisruptionEvent(
            source_url="https://example.com",
            source_result_id="sr1",
            headline="Flood hits factory",
            summary="Summary text",
            event_type="flood",
            location_mentioned="Chennai",
            severity_raw="high",
            confidence=0.9,
            is_relevant=True,
            published_at=now,
        )
        assert e.published_at == now

    def test_published_at_defaults_to_none(self):
        r = RawSearchResult(
            url="https://example.com",
            title="Test",
            snippet="Test snippet",
            queried_entity_id="e1",
            query_used="q",
        )
        assert r.published_at is None
