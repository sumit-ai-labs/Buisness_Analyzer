"""Verification script for full live monitoring path with deterministic dates.

Tests:
1. Controlled monitoring cycle with RFC-style and ISO-style publication dates.
2. Confirm recent dated results reach extraction and older results are rejected.
3. Confirm malformed and missing dates do not crash the batch.
4. Verify batch summary reports accurately.
5. Confirm zero results are reported honestly when no usable results remain.
6. Verify no unexpected date-parse warnings or unhandled exceptions occur.
"""

import asyncio
from datetime import datetime, timezone
import io
import logging
import sys
from unittest.mock import MagicMock, patch

from app.models.entity import BusinessEntity
from app.models.events import DisruptionEvent
from app.services.alert_service import AlertService
from app.services.analysis_service import AnalysisService, AnalysisBatchResult
from app.services.matcher_service import MatcherService
from app.services.network_service import NetworkService
from app.services.research_service import ResearchService

FIXED_NOW = datetime(2026, 10, 12, 12, 0, 0, tzinfo=timezone.utc)


async def main():
    print("=" * 70)
    print("VERIFYING CONTROLLED MONITORING PATH WITH DETERMINISTIC DATES")
    print("=" * 70)

    # Capture logs to verify warnings
    warning_lines = []
    class WarningHandler(logging.Handler):
        def emit(self, record):
            if record.levelno >= logging.WARNING:
                warning_lines.append(record.getMessage())

    handler = WarningHandler()
    app_logger = logging.getLogger("business_disruption")
    app_logger.addHandler(handler)

    net_svc = NetworkService()
    entity = BusinessEntity(
        id="ent-mumbai",
        name="Mumbai Port Terminal",
        type="supplier",
        criticality="high",
        location="Mumbai",
        status="active",
    )
    net_svc.add_entity(entity)

    # 1. Test batch containing RFC, ISO, stale, future, malformed, and missing
    mock_search_results = [
        # Fresh RFC GMT
        {
            "url": "https://news.com/rfc-gmt",
            "title": "Dockworkers strike at Mumbai terminal",
            "snippet": "Active strike halts operations in Mumbai today.",
            "published_date": "Thu, 08 Oct 2026 06:00:00 GMT",
        },
        # Fresh RFC numeric offset
        {
            "url": "https://news.com/rfc-offset",
            "title": "Severe flooding submerges port access road",
            "snippet": "Flash flood blocks container traffic in Mumbai.",
            "published_date": "Wed, 07 Oct 2026 21:00:00 +0200",
        },
        # Fresh ISO with Z
        {
            "url": "https://news.com/iso-z",
            "title": "Power failure shuts cooling systems",
            "snippet": "Grid failure at Mumbai logistics hub.",
            "published_date": "2026-10-11T12:00:00Z",
        },
        # Stale RFC (>7 days)
        {
            "url": "https://news.com/rfc-stale",
            "title": "Last month strike update",
            "snippet": "Strike resolved three weeks ago.",
            "published_date": "Sun, 20 Sep 2026 12:00:00 GMT",
        },
        # Stale ISO (>7 days)
        {
            "url": "https://news.com/iso-stale",
            "title": "Historical weather report",
            "snippet": "Past rainfall figures.",
            "published_date": "2026-09-15T08:00:00Z",
        },
        # Future-dated (>24h tolerance)
        {
            "url": "https://news.com/future",
            "title": "Predictions for November",
            "snippet": "Upcoming schedule.",
            "published_date": "2026-10-25T12:00:00Z",
        },
        # Malformed date
        {
            "url": "https://news.com/malformed",
            "title": "Malformed date article",
            "snippet": "Article snippet.",
            "published_date": "Thu, 99 BadMonth 2026 99:99:99",
        },
        # Missing date
        {
            "url": "https://news.com/missing",
            "title": "Undated advisory",
            "snippet": "Advisory snippet.",
            "published_date": None,
        },
    ]

    mock_client = MagicMock()
    mock_client.search.return_value = mock_search_results

    mock_analysis_svc = MagicMock()
    def _mock_analyze_batch(raw_results, entity_name_map=None):
        events = []
        for sr in raw_results:
            event = DisruptionEvent(
                source_url=sr.url,
                source_result_id=sr.id,
                headline=sr.title,
                summary=sr.snippet,
                event_type="strike" if "strike" in sr.title.lower() else "flood",
                location_mentioned="Mumbai",
                severity_raw="high",
                extracted_entities=["Mumbai Port Terminal"],
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

    res_svc = ResearchService(client=mock_client)
    matcher_svc = MatcherService(network_service=net_svc)
    alert_svc = AlertService(
        network_service=net_svc,
        research_service=res_svc,
        analysis_service=mock_analysis_svc,
        matcher_service=matcher_svc,
    )

    print("\n[STEP 1] Running monitoring cycle with mixed dates...")
    with patch("app.services.research_service.datetime") as mock_dt:
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.fromisoformat = datetime.fromisoformat
        mock_dt.strptime = datetime.strptime
        mock_dt.fromtimestamp = datetime.fromtimestamp
        mock_dt.min = datetime.min
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        summary = await alert_svc.run_monitoring_cycle()

    print("\nCycle Summary 1:")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    # Assertions for run 1
    assert summary["raw_results_count"] == 3, f"Expected 3 raw results, got {summary['raw_results_count']}"
    assert summary["processed_results_count"] == 3, f"Expected 3 processed, got {summary['processed_results_count']}"
    assert summary["extraction_success_count"] == 3, f"Expected 3 successes, got {summary['extraction_success_count']}"
    assert summary["extraction_failed_count"] == 0, f"Expected 0 failures, got {summary['extraction_failed_count']}"
    assert summary["extraction_rejected_count"] == 0, f"Expected 0 rejected, got {summary['extraction_rejected_count']}"
    assert summary["relevant_events_count"] == 3, f"Expected 3 relevant, got {summary['relevant_events_count']}"
    assert summary["new_alerts_count"] >= 1, f"Expected >=1 alert, got {summary['new_alerts_count']}"

    print("\n--> PASSED: 3 fresh results reached extraction, older (2), future (1), malformed (1), and undated (1) rejected correctly!")

    # 2. Test zero-results honesty run
    print("\n[STEP 2] Running cycle with only stale and undated results...")
    mock_client.search.return_value = [
        {
            "url": "https://news.com/old-news",
            "title": "Old event",
            "snippet": "Past event",
            "published_date": "Sun, 01 Sep 2026 12:00:00 GMT",
        },
        {
            "url": "https://news.com/undated-news",
            "title": "Undated",
            "snippet": "Undated snippet",
            "published_date": None,
        },
    ]

    with patch("app.services.research_service.datetime") as mock_dt:
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.fromisoformat = datetime.fromisoformat
        mock_dt.strptime = datetime.strptime
        mock_dt.fromtimestamp = datetime.fromtimestamp
        mock_dt.min = datetime.min
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        summary_zero = await alert_svc.run_monitoring_cycle()

    print("\nCycle Summary 2 (Zero Results Honesty):")
    for k, v in summary_zero.items():
        print(f"  {k}: {v}")

    assert summary_zero["raw_results_count"] == 0
    assert summary_zero["processed_results_count"] == 0
    assert summary_zero["extraction_success_count"] == 0
    assert summary_zero["extraction_failed_count"] == 0
    assert summary_zero["extraction_rejected_count"] == 0
    assert summary_zero["relevant_events_count"] == 0
    assert summary_zero["new_alerts_count"] == 0

    print("\n--> PASSED: Honest zero reporting verified across all batch summary fields!")

    # 3. Check logs for warnings
    print("\n[STEP 3] Verifying captured warnings:")
    for w in warning_lines:
        print(f"  Captured: {w}")

    # Ensure malformed date was logged as expected
    assert any("Could not parse published_date 'Thu, 99 BadMonth 2026 99:99:99'" in l for l in warning_lines), \
        "Expected malformed date warning in logs"

    # Ensure no unexpected warnings for valid RFC or ISO dates
    unexpected = [
        l for l in warning_lines
        if "Thu, 08 Oct 2026" in l
        or "Wed, 07 Oct 2026" in l
        or "2026-10-11" in l
    ]
    assert len(unexpected) == 0, f"Unexpected date parse warnings: {unexpected}"

    print("\n--> PASSED: No unexpected date parse warnings for valid RFC or ISO dates!")
    print("\n" + "=" * 70)
    print("ALL MONITORING PATH VERIFICATIONS SUCCESSFUL!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
