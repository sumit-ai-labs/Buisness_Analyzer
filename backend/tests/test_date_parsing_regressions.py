"""Deterministic Regression Tests for Date Parsing and Monitoring Recency.

Validates:
- RFC-style dates with GMT (e.g. 'Wed, 07 Oct 2026 21:00:00 GMT', 'Thu, 08 Oct 2026 06:00:00 GMT', 'Mon, 12 Oct 2026 03:02:41 GMT')
- RFC-style dates with numeric timezone offsets ('+0200', '-0500', etc.)
- ISO-8601 timestamps with 'Z' and explicit offsets
- Unix epoch timestamps (integer, float, and numeric strings)
- Recent dates within the 7-day window passing the recency filter
- Dates older than 7 days rejected under fixed reference time
- Dates beyond future tolerance (>24h ahead of reference time) rejected
- Malformed and missing dates follow the keep_undated policy safely
- Mixed batch with valid, invalid, and undated items
- Monitoring batch continues safely when an individual result has an invalid date
- Deterministic reference time injected for zero clock dependency
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import pytest

from app.models.entity import BusinessEntity
from app.models.events import RawSearchResult
from app.services.research_service import (
    ResearchService,
    _parse_published_date,
    filter_by_recency,
    sort_by_recency,
)


# Fixed reference clock: 2026-10-12 12:00:00 UTC
FIXED_NOW = datetime(2026, 10, 12, 12, 0, 0, tzinfo=timezone.utc)


def _make_sr(
    url: str,
    published_at: datetime | None = None,
    title: str = "Disruption Alert",
    snippet: str = "Port operations suspended due to heavy flooding.",
) -> RawSearchResult:
    return RawSearchResult(
        url=url,
        title=title,
        snippet=snippet,
        queried_entity_id="entity-123",
        query_used="test query",
        published_at=published_at,
    )


class TestDateParsingUnits:
    """Deterministic unit tests for _parse_published_date."""

    def test_rfc_style_dates_with_gmt(self):
        """RFC-style dates from Tavily news feeds with GMT timezone."""
        examples = [
            ("Wed, 07 Oct 2026 21:00:00 GMT", datetime(2026, 10, 7, 21, 0, 0, tzinfo=timezone.utc)),
            ("Thu, 08 Oct 2026 06:00:00 GMT", datetime(2026, 10, 8, 6, 0, 0, tzinfo=timezone.utc)),
            ("Mon, 12 Oct 2026 03:02:41 GMT", datetime(2026, 10, 12, 3, 2, 41, tzinfo=timezone.utc)),
        ]
        for raw, expected in examples:
            dt = _parse_published_date(raw)
            assert dt is not None, f"Failed to parse RFC date '{raw}'"
            assert dt == expected
            assert dt.tzinfo == timezone.utc

    def test_rfc_style_dates_with_numeric_offsets(self):
        """RFC-style dates with non-UTC numeric offsets are normalized to UTC."""
        # 07 Oct 2026 21:00:00 +0200 -> 19:00:00 UTC
        dt_plus2 = _parse_published_date("Wed, 07 Oct 2026 21:00:00 +0200")
        assert dt_plus2 is not None
        assert dt_plus2 == datetime(2026, 10, 7, 19, 0, 0, tzinfo=timezone.utc)
        assert dt_plus2.tzinfo == timezone.utc

        # 08 Oct 2026 06:00:00 -0500 -> 11:00:00 UTC
        dt_minus5 = _parse_published_date("Thu, 08 Oct 2026 06:00:00 -0500")
        assert dt_minus5 is not None
        assert dt_minus5 == datetime(2026, 10, 8, 11, 0, 0, tzinfo=timezone.utc)
        assert dt_minus5.tzinfo == timezone.utc

    def test_iso_8601_with_z_and_explicit_offsets(self):
        """ISO-8601 timestamps with Z, +/- offsets, and naive formats normalized to UTC."""
        dt_z = _parse_published_date("2026-10-12T03:02:41Z")
        assert dt_z == datetime(2026, 10, 12, 3, 2, 41, tzinfo=timezone.utc)

        # India offset +05:30 -> 2026-10-12T08:32:41+05:30 -> 03:02:41 UTC
        dt_offset = _parse_published_date("2026-10-12T08:32:41+05:30")
        assert dt_offset == datetime(2026, 10, 12, 3, 2, 41, tzinfo=timezone.utc)

        # Naive ISO date explicitly interpreted as UTC
        dt_naive = _parse_published_date("2026-10-12T03:02:41")
        assert dt_naive == datetime(2026, 10, 12, 3, 2, 41, tzinfo=timezone.utc)

        # Date only
        dt_date = _parse_published_date("2026-10-12")
        assert dt_date == datetime(2026, 10, 12, 0, 0, 0, tzinfo=timezone.utc)

    def test_unix_epoch_timestamps(self):
        """Unix epoch values as int, float, and strings in seconds or milliseconds."""
        # 1791774161 = 2026-10-12 03:02:41 UTC
        expected = datetime(2026, 10, 12, 3, 2, 41, tzinfo=timezone.utc)
        ts_sec = 1791774161
        assert _parse_published_date(ts_sec) == expected
        assert _parse_published_date(float(ts_sec)) == expected
        assert _parse_published_date(str(ts_sec)) == expected
        assert _parse_published_date(f"{ts_sec}.0") == expected

        # Milliseconds (13 digits)
        ts_ms = ts_sec * 1000
        assert _parse_published_date(ts_ms) == expected
        assert _parse_published_date(str(ts_ms)) == expected

    def test_malformed_and_missing_dates(self):
        """Malformed or missing dates return None safely without raising exceptions."""
        assert _parse_published_date(None) is None
        assert _parse_published_date("") is None
        assert _parse_published_date("   ") is None
        assert _parse_published_date("not-a-valid-date") is None
        assert _parse_published_date("9999-99-99T99:99:99") is None
        assert _parse_published_date("undefined") is None
        assert _parse_published_date(object()) is None


class TestRecencyFilterDeterministic:
    """Deterministic tests for filter_by_recency with fixed reference time."""

    def test_recent_rfc_and_iso_dates_pass_filter(self):
        """Recent dates within 7 days pass recency filter."""
        sr_rfc = _make_sr("https://news.com/rfc", _parse_published_date("Thu, 08 Oct 2026 06:00:00 GMT"))
        sr_iso = _make_sr("https://news.com/iso", _parse_published_date("2026-10-11T10:00:00Z"))

        kept = filter_by_recency([sr_rfc, sr_iso], max_age_days=7, reference_time=FIXED_NOW)
        assert len(kept) == 2
        assert {r.url for r in kept} == {"https://news.com/rfc", "https://news.com/iso"}

    def test_dates_older_than_seven_days_rejected(self):
        """Dates published >7 days prior to reference time are dropped."""
        # FIXED_NOW is 2026-10-12 12:00:00 UTC. 7-day cutoff is 2026-10-05 12:00:00 UTC.
        # 2026-10-04 is 8 days old
        sr_old_rfc = _make_sr("https://news.com/old-rfc", _parse_published_date("Sun, 04 Oct 2026 12:00:00 GMT"))
        sr_old_iso = _make_sr("https://news.com/old-iso", _parse_published_date("2026-10-04T12:00:00Z"))

        kept = filter_by_recency([sr_old_rfc, sr_old_iso], max_age_days=7, reference_time=FIXED_NOW)
        assert len(kept) == 0

    def test_dates_beyond_future_tolerance_rejected(self):
        """Dates >24 hours ahead of reference time are dropped as future-dated anomalies."""
        # FIXED_NOW + 12 hours (within 24h skew buffer) -> kept
        sr_near_future = _make_sr("https://news.com/near", FIXED_NOW + timedelta(hours=12))
        # FIXED_NOW + 36 hours (>24h buffer) -> dropped
        sr_far_future = _make_sr("https://news.com/far", FIXED_NOW + timedelta(hours=36))

        kept = filter_by_recency([sr_near_future, sr_far_future], max_age_days=7, reference_time=FIXED_NOW)
        assert len(kept) == 1
        assert kept[0].url == "https://news.com/near"

    def test_undated_policy_enforcement(self):
        """Undated results are dropped by default and kept when keep_undated=True."""
        sr_undated = _make_sr("https://news.com/undated", published_at=None)

        assert filter_by_recency([sr_undated], max_age_days=7, keep_undated=False, reference_time=FIXED_NOW) == []
        retained = filter_by_recency([sr_undated], max_age_days=7, keep_undated=True, reference_time=FIXED_NOW)
        assert len(retained) == 1
        assert retained[0].url == "https://news.com/undated"

    def test_mixed_batch_handling(self):
        """Batch containing valid RFC, valid ISO, stale, future, invalid date, and undated items."""
        r1_fresh_rfc = _make_sr("https://news.com/rfc-fresh", _parse_published_date("Mon, 12 Oct 2026 03:02:41 GMT"))
        r2_fresh_iso = _make_sr("https://news.com/iso-fresh", _parse_published_date("2026-10-10T15:30:00Z"))
        r3_stale = _make_sr("https://news.com/stale", _parse_published_date("Wed, 30 Sep 2026 12:00:00 GMT"))
        r4_future = _make_sr("https://news.com/future", FIXED_NOW + timedelta(days=5))
        r5_invalid = _make_sr("https://news.com/invalid", _parse_published_date("corrupted-date-xyz"))
        r6_undated = _make_sr("https://news.com/undated", None)

        batch = [r1_fresh_rfc, r2_fresh_iso, r3_stale, r4_future, r5_invalid, r6_undated]
        kept = filter_by_recency(batch, max_age_days=7, keep_undated=False, reference_time=FIXED_NOW)

        # Only fresh RFC and fresh ISO should survive
        assert len(kept) == 2
        assert {r.url for r in kept} == {"https://news.com/rfc-fresh", "https://news.com/iso-fresh"}

    def test_sort_by_recency_deterministic(self):
        """sort_by_recency sorts newest first, putting undated at end."""
        dt1 = datetime(2026, 10, 10, tzinfo=timezone.utc)
        dt2 = datetime(2026, 10, 12, tzinfo=timezone.utc)
        sr1 = _make_sr("https://news.com/older", dt1)
        sr2 = _make_sr("https://news.com/newest", dt2)
        sr3 = _make_sr("https://news.com/undated", None)

        sorted_results = sort_by_recency([sr1, sr3, sr2])
        assert [r.url for r in sorted_results] == [
            "https://news.com/newest",
            "https://news.com/older",
            "https://news.com/undated",
        ]


class TestMonitoringBatchContinuity:
    """Verifies that an individual bad/malformed date does not crash research service."""

    def test_research_service_batch_continues_on_bad_date(self):
        """Single bad date does not crash entity search; remaining items are kept."""
        mock_client = MagicMock()
        mock_client.search.return_value = [
            {
                "url": "https://news.com/rfc-good",
                "title": "Strike at terminal",
                "snippet": "Active strike today",
                "published_date": "Thu, 08 Oct 2026 06:00:00 GMT",
            },
            {
                "url": "https://news.com/bad-date",
                "title": "Bad date item",
                "snippet": "Disruption description",
                "published_date": "THIS_IS_TOTALLY_NOT_A_DATE",
            },
            {
                "url": "https://news.com/iso-good",
                "title": "Port closure",
                "snippet": "Flood shuts port",
                "published_date": "2026-10-11T12:00:00Z",
            },
        ]

        svc = ResearchService(client=mock_client)
        entity = BusinessEntity(
            id="ent-1",
            name="Port Terminal",
            type="supplier",
            criticality="high",
            location="Mumbai",
            status="active",
        )

        # Mock datetime.now in research_service so filter uses FIXED_NOW
        with patch("app.services.research_service.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            # Make sure fromisoformat and other methods work normally
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.strptime = datetime.strptime
            mock_dt.fromtimestamp = datetime.fromtimestamp
            mock_dt.min = datetime.min
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            results = svc.search_disruptions_for_entity(entity)

        # Batch did not crash! 2 valid items survived the 7-day recency filter, bad date dropped cleanly
        assert len(results) == 2
        urls = [r.url for r in results]
        assert "https://news.com/rfc-good" in urls
        assert "https://news.com/iso-good" in urls
        assert "https://news.com/bad-date" not in urls


class TestFullMonitoringCycleVerification:
    """Verifies the complete monitoring cycle with mixed RFC/ISO search results."""

    @pytest.mark.asyncio
    async def test_monitoring_cycle_with_rfc_and_iso_results(self):
        """Monitored entity with RFC-style and ISO-style dates reaching extraction, older/undated rejected."""
        from app.services.alert_service import AlertService
        from app.services.analysis_service import AnalysisService, AnalysisBatchResult
        from app.services.matcher_service import MatcherService
        from app.services.network_service import NetworkService
        from app.models.events import DisruptionEvent

        # Set up mock Tavily client returning RFC, ISO, stale, malformed, and missing
        mock_tavily = MagicMock()
        mock_tavily.search.return_value = [
            {
                "url": "https://news.com/rfc-recent",
                "title": "Strike halts terminal",
                "content": "Port workers strike halts operations in Mumbai today.",
                "published_date": "Thu, 08 Oct 2026 06:00:00 GMT",
            },
            {
                "url": "https://news.com/iso-recent",
                "title": "Severe flood in Mumbai",
                "content": "Heavy flood blocks access to container terminal in Mumbai.",
                "published_date": "2026-10-11T12:00:00Z",
            },
            {
                "url": "https://news.com/rfc-stale",
                "title": "Historical strike",
                "content": "Strike ended weeks ago.",
                "published_date": "Sun, 20 Sep 2026 12:00:00 GMT",
            },
            {
                "url": "https://news.com/malformed-date",
                "title": "Accident report",
                "content": "Road blocked.",
                "published_date": "garbage-date-format-xyz",
            },
            {
                "url": "https://news.com/missing-date",
                "title": "Weather notice",
                "content": "Rain advisory.",
                "published_date": None,
            },
        ]

        net_svc = NetworkService()
        entity = BusinessEntity(
            id="e-test-1",
            name="Mumbai Terminal",
            type="supplier",
            criticality="high",
            location="Mumbai",
            status="active",
        )
        net_svc.add_entity(entity)

        # Mock analysis service returning deterministic relevant events for the 2 fresh items
        mock_analysis_svc = MagicMock()
        def _mock_analyze_batch(raw_results, entity_name_map=None):
            events = []
            for sr in raw_results:
                event = DisruptionEvent(
                    source_url=sr.url,
                    source_result_id=sr.id,
                    headline=sr.title,
                    summary=sr.snippet,
                    event_type="strike" if "Strike" in sr.title else "flood",
                    location_mentioned="Mumbai",
                    severity_raw="high",
                    extracted_entities=["Mumbai Terminal"],
                    confidence=0.9,
                    is_relevant=True,
                    published_at=sr.published_at,
                )
                events.append(event)
            return AnalysisBatchResult(
                events=events,
                failures=[],
                processed_count=len(raw_results),
            )
        mock_analysis_svc.analyze_search_results_batch.side_effect = _mock_analyze_batch

        res_svc = ResearchService(client=mock_tavily)
        matcher_svc = MatcherService(network_service=net_svc)
        alert_svc = AlertService(
            network_service=net_svc,
            research_service=res_svc,
            analysis_service=mock_analysis_svc,
            matcher_service=matcher_svc,
        )

        # Mock datetime.now in research_service so filter uses FIXED_NOW (2026-10-12)
        with patch("app.services.research_service.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.strptime = datetime.strptime
            mock_dt.fromtimestamp = datetime.fromtimestamp
            mock_dt.min = datetime.min
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            summary = await alert_svc.run_monitoring_cycle()

        # Check summary schema and counts:
        # Exactly 2 fresh results (RFC and ISO) reached extraction; stale and undated were rejected
        assert summary["raw_results_count"] == 2
        assert summary["processed_results_count"] == 2
        assert summary["extraction_success_count"] == 2
        assert summary["extraction_failed_count"] == 0
        assert summary["extraction_rejected_count"] == 0
        assert summary["relevant_events_count"] == 2
        assert summary["new_alerts_count"] >= 1

    @pytest.mark.asyncio
    async def test_monitoring_cycle_zero_results_honesty(self):
        """When all results are stale or undated, cycle honestly reports 0 across all stages."""
        from app.services.alert_service import AlertService
        from app.services.network_service import NetworkService

        mock_tavily = MagicMock()
        mock_tavily.search.return_value = [
            {
                "url": "https://news.com/old-rfc",
                "title": "Ancient event",
                "content": "Old news from last month",
                "published_date": "Sun, 01 Sep 2026 12:00:00 GMT",
            },
            {
                "url": "https://news.com/no-date",
                "title": "Undated article",
                "content": "No date attached",
                "published_date": None,
            },
        ]

        net_svc = NetworkService()
        entity = BusinessEntity(
            id="e-test-2",
            name="Navi Mumbai Port",
            type="supplier",
            criticality="high",
            location="Mumbai",
            status="active",
        )
        net_svc.add_entity(entity)

        res_svc = ResearchService(client=mock_tavily)
        alert_svc = AlertService(network_service=net_svc, research_service=res_svc)

        with patch("app.services.research_service.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_NOW
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.strptime = datetime.strptime
            mock_dt.fromtimestamp = datetime.fromtimestamp
            mock_dt.min = datetime.min
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            summary = await alert_svc.run_monitoring_cycle()

        # Honest 0 reporting
        assert summary["raw_results_count"] == 0
        assert summary["processed_results_count"] == 0
        assert summary["extraction_success_count"] == 0
        assert summary["extraction_failed_count"] == 0
        assert summary["extraction_rejected_count"] == 0
        assert summary["relevant_events_count"] == 0
        assert summary["new_alerts_count"] == 0

