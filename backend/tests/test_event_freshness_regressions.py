"""Regression tests for Event Freshness and Date Handling (Phase 2 - Section 2).

Verifies:
- Current article about an active disruption (kept)
- Article older than 7 days (dropped by default)
- Recent article describing an older incident (kept by recency, evaluated by active impact)
- Undated article with default settings (dropped)
- Undated article with override enabled (kept)
- Invalid publication date (parsed as None, dropped by default)
- Time-zone differences (normalized and accurately filtered against UTC cutoff)
- Future-dated article (dropped as future-dated anomaly beyond 24h timezone buffer)
- Missing event date but known publication date (kept and analyzed)
- Non-interchangeability of publication date and incident date
"""

from datetime import datetime, timedelta, timezone
import pytest

from app.core.config import Settings
from app.models.events import RawSearchResult
from app.services.analysis_service import AnalysisService
from app.services.research_service import (
    _parse_published_date,
    filter_by_recency,
    sort_by_recency,
)


def _make_raw(
    url: str,
    published_at: datetime | None = None,
    title: str = "Disruption Alert",
    snippet: str = "Active strike halts factory operations today.",
) -> RawSearchResult:
    return RawSearchResult(
        url=url,
        title=title,
        snippet=snippet,
        queried_entity_id="entity-test",
        query_used="test query",
        published_at=published_at,
    )


class TestEventFreshnessRegressions:
    def setup_method(self):
        from app.core.llm_client import LLMClientWrapper
        self.analysis_svc = AnalysisService(client=LLMClientWrapper(gemini_api_key="", llm_api_key=""))

    def test_current_article_about_active_disruption_is_kept(self):
        """Current article (<7 days old) about active disruption is preserved and marked relevant."""
        now = datetime.now(timezone.utc)
        raw = _make_raw(
            "https://news.example.com/active-now",
            published_at=now - timedelta(hours=6),
            title="Active strike paralyzes port terminals today",
            snippet="Over 1,000 workers began an active strike this morning, halting all port activities.",
        )
        filtered = filter_by_recency([raw], max_age_days=7)
        assert len(filtered) == 1
        assert filtered[0].url == "https://news.example.com/active-now"

        event = self.analysis_svc.analyze_search_result(filtered[0], entity_name="Port Terminal")
        assert event.is_relevant is True
        assert event.event_type == "strike"
        assert event.published_at == raw.published_at

    def test_article_older_than_seven_days_is_dropped(self):
        """Article older than 7 days is discarded under standard 7-day window."""
        now = datetime.now(timezone.utc)
        raw_stale = _make_raw(
            "https://news.example.com/stale-strike",
            published_at=now - timedelta(days=8),
        )
        filtered = filter_by_recency([raw_stale], max_age_days=7)
        assert len(filtered) == 0

    def test_recent_article_describing_older_incident_evaluated_by_active_status(self):
        """Recent publication describing an older ongoing incident is kept, not dropped for incident age."""
        now = datetime.now(timezone.utc)
        # Article published today (<7d), but incident began 3 weeks ago and is ongoing
        raw_ongoing = _make_raw(
            "https://news.example.com/week-three-strike",
            published_at=now - timedelta(hours=12),
            title="Week 3 of port strike continues as cargo backlog mounts",
            snippet="Entering its third week, the dock strike that began 20 days ago continues to paralyze port operations today.",
        )
        filtered = filter_by_recency([raw_ongoing], max_age_days=7)
        assert len(filtered) == 1

        event = self.analysis_svc.analyze_search_result(filtered[0], entity_name="Harbor Terminal")
        # Event remains active and relevant because disruption is ongoing
        assert event.is_relevant is True
        assert event.event_type == "strike"

    def test_recent_article_describing_historical_incident_marked_not_relevant(self):
        """Recent article reminiscing about an old historical incident without ongoing impact is rejected."""
        now = datetime.now(timezone.utc)
        raw_history = _make_raw(
            "https://news.example.com/history-retrospective",
            published_at=now - timedelta(hours=2),
            title="Looking back at the historical outage from 2019",
            snippet="Five years ago, a massive power failure halted industrial operations across the region.",
        )
        filtered = filter_by_recency([raw_history], max_age_days=7)
        assert len(filtered) == 1  # Article itself is recent, passes recency filter

        event = self.analysis_svc.analyze_search_result(filtered[0], entity_name="Power Grid")
        # Historical event without active disruption is marked not relevant
        assert event.is_relevant is False

    def test_undated_article_dropped_with_default_settings(self):
        """Undated article is rejected when SEARCH_KEEP_UNDATED_RESULTS is False."""
        raw_undated = _make_raw("https://news.example.com/undated", published_at=None)
        filtered = filter_by_recency([raw_undated], max_age_days=7, keep_undated=False)
        assert len(filtered) == 0

    def test_undated_article_retained_with_override_enabled(self):
        """Undated article is preserved when keep_undated=True override is enabled."""
        raw_undated = _make_raw("https://news.example.com/undated-override", published_at=None)
        filtered = filter_by_recency([raw_undated], max_age_days=7, keep_undated=True)
        assert len(filtered) == 1
        assert filtered[0].url == "https://news.example.com/undated-override"

    def test_invalid_publication_date_parsed_as_none_and_dropped(self):
        """Malformed or nonsensical publication date strings parse to None and drop under default filter."""
        assert _parse_published_date("invalid-date-string") is None
        assert _parse_published_date("9999-99-99T99:99:99") is None
        assert _parse_published_date("not_a_timestamp") is None

        raw = _make_raw(
            "https://news.example.com/bad-date",
            published_at=_parse_published_date("garbage-date"),
        )
        filtered = filter_by_recency([raw], max_age_days=7, keep_undated=False)
        assert len(filtered) == 0

    def test_timezone_differences_normalized_correctly(self):
        """Articles published across different time zones are normalized to UTC for comparison."""
        now_utc = datetime.now(timezone.utc)
        # Article published in India (UTC+05:30) 2 days ago
        tz_india = timezone(timedelta(hours=5, minutes=30))
        pub_india = (now_utc - timedelta(days=2)).astimezone(tz_india)
        iso_india = pub_india.isoformat()
        parsed_india = _parse_published_date(iso_india)
        assert parsed_india is not None
        assert parsed_india.tzinfo is not None

        raw_india = _make_raw("https://news.in/strike", published_at=parsed_india)
        filtered = filter_by_recency([raw_india], max_age_days=7)
        assert len(filtered) == 1

        # Article published in New York (UTC-05:00) 10 days ago (should be dropped under 7d window)
        tz_ny = timezone(timedelta(hours=-5))
        pub_ny = (now_utc - timedelta(days=10)).astimezone(tz_ny)
        parsed_ny = _parse_published_date(pub_ny.isoformat())
        raw_ny = _make_raw("https://news.us/old-strike", published_at=parsed_ny)
        filtered_ny = filter_by_recency([raw_ny], max_age_days=7)
        assert len(filtered_ny) == 0

    def test_future_dated_article_dropped_as_anomaly(self):
        """Articles with publication dates far in the future (>24h grace) are dropped as anomalies."""
        now = datetime.now(timezone.utc)
        raw_future = _make_raw(
            "https://news.example.com/future",
            published_at=now + timedelta(days=10),
            title="Future news report from 2030",
        )
        filtered = filter_by_recency([raw_future], max_age_days=7)
        assert len(filtered) == 0

    def test_missing_event_date_in_text_with_known_publication_date(self):
        """Snippet lacking an explicit calendar date string still extracts successfully via publication date."""
        now = datetime.now(timezone.utc)
        raw = _make_raw(
            "https://news.example.com/no-calendar-date",
            published_at=now - timedelta(days=1),
            title="Factory shutdown after flash flood",
            snippet="Industrial park submerged; emergency crews working on drainage. Production halted.",
        )
        filtered = filter_by_recency([raw], max_age_days=7)
        assert len(filtered) == 1

        event = self.analysis_svc.analyze_search_result(filtered[0], entity_name="Industrial Park")
        assert event.is_relevant is True
        assert event.event_type == "flood"
        assert event.published_at == raw.published_at
