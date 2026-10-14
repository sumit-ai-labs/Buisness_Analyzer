import pytest
from app.models.events import RawSearchResult
from app.services.analysis_service import AnalysisService


def test_analysis_agent_active_strike():
    service = AnalysisService()
    search_result = RawSearchResult(
        url="https://news.example.com/strike-rotterdam",
        title="Dockworkers launch strike at Rotterdam port facility",
        snippet="Over 2,000 workers have walked out on strike at the container terminal in Rotterdam, halting all cargo operations.",
        queried_entity_id="entity-101",
        query_used="Rotterdam Port strike",
    )

    event = service.analyze_search_result(search_result, entity_name="Rotterdam Logistics Port")
    assert event.is_relevant is True
    assert event.event_type == "strike"
    assert event.severity_raw in ["high", "medium"]


def test_analysis_agent_averted_strike_false_positive():
    service = AnalysisService()
    search_result = RawSearchResult(
        url="https://news.example.com/strike-averted",
        title="Port strike averted after union reaches last-minute agreement",
        snippet="Labor union representatives reached a contract agreement late Sunday, calling off the scheduled walkout and resuming normal port operations.",
        queried_entity_id="entity-101",
        query_used="Rotterdam Port strike",
    )

    event = service.analyze_search_result(search_result, entity_name="Rotterdam Logistics Port")
    assert event.is_relevant is False


def test_analysis_agent_flooding():
    service = AnalysisService()
    search_result = RawSearchResult(
        url="https://news.example.com/flood-santiago",
        title="Severe flooding causes plant shutdown in Santiago industrial zone",
        snippet="Heavy torrential rains caused river banks to overflow, forcing multiple manufacturing facilities in Santiago to shut down operations.",
        queried_entity_id="entity-102",
        query_used="Santiago flood closure",
    )

    event = service.analyze_search_result(search_result, entity_name="Santiago Manufacturing Plant")
    assert event.is_relevant is True
    assert event.event_type == "flood"
