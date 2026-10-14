"""Regression tests for Resolved-Event Filtering (Phase 2 - Section 3).

Verifies:
- Strike called off (marked not relevant)
- Agreement reached (marked not relevant)
- Operations resumed (marked not relevant)
- Temporary disruption resolved (marked not relevant)
- Historical outage without ongoing impact (marked not relevant)
- Resolved incident with continuing production impact (marked relevant, not blanket rejected)
- Article mentioning both a resolved incident and a new active disruption (marked relevant)
- Negative phrases used in unrelated contexts ('no agreement reached', 'not resolved' -> marked relevant)
- Ambiguous / unconfirmed active status routed to review status
"""

import pytest
from app.models.events import RawSearchResult
from app.services.analysis_service import AnalysisService


def _raw(title: str, snippet: str, url: str = "https://news.example.com/test") -> RawSearchResult:
    return RawSearchResult(
        url=url,
        title=title,
        snippet=snippet,
        queried_entity_id="entity-test",
        query_used="test query",
    )


class TestResolvedEventFilteringRegressions:
    def setup_method(self):
        from app.core.llm_client import LLMClientWrapper
        self.svc = AnalysisService(client=LLMClientWrapper(gemini_api_key="", llm_api_key=""))

    def test_strike_called_off_is_filtered(self):
        """A strike that has been called off is marked not relevant."""
        sr = _raw(
            title="Harbor workers strike called off after eleventh-hour talks",
            snippet="Port union leaders officially announced the strike called off following an agreement. Workers will return to normal shifts.",
        )
        event = self.svc.analyze_search_result(sr, entity_name="Rotterdam Port")
        assert event.is_relevant is False

    def test_agreement_reached_is_filtered(self):
        """An agreement reached between parties prevents false-positive disruption alert."""
        sr = _raw(
            title="Rail operators and union reach agreement on labor contract",
            snippet="Agreement reached on wage conditions, averting potential walkouts across rail freight network.",
        )
        event = self.svc.analyze_search_result(sr, entity_name="Freight Rail")
        assert event.is_relevant is False

    def test_operations_resumed_is_filtered(self):
        """Operations resumed without lingering disruption is marked not relevant."""
        sr = _raw(
            title="Assembly plant operations resumed after weekend power maintenance",
            snippet="Manufacturing lines are fully functional as operations resumed normal schedules with no delays.",
        )
        event = self.svc.analyze_search_result(sr, entity_name="Assembly Plant")
        assert event.is_relevant is False

    def test_temporary_disruption_resolved_is_filtered(self):
        """A temporary disruption resolved cleanly is marked not relevant."""
        sr = _raw(
            title="Logistics hub temporary disruption resolved",
            snippet="IT glitch resolved at distribution center; temporary disruption resolved and dispatch running smoothly.",
        )
        event = self.svc.analyze_search_result(sr, entity_name="Logistics Hub")
        assert event.is_relevant is False

    def test_historical_outage_is_filtered(self):
        """Historical outage from past years without ongoing disruption is marked not relevant."""
        sr = _raw(
            title="Remembering the 2018 historical outage that shut down the chemical plant",
            snippet="Six years ago, a massive explosion caused an outage that halted regional operations. Today safety standards were commemorated.",
        )
        event = self.svc.analyze_search_result(sr, entity_name="Chemical Plant")
        assert event.is_relevant is False

    def test_resolved_incident_with_continuing_production_impact_is_retained(self):
        """When an incident is resolved but continuing production impact persists, it is NOT rejected."""
        sr = _raw(
            title="Terminal dispute resolved yesterday, but continuing production impact delays cargo",
            snippet="Although union agreement reached settled the walkout, continuing production impact, supply backlog, and severe delivery delays persist across supply chains.",
        )
        event = self.svc.analyze_search_result(sr, entity_name="Container Terminal")
        # Must NOT be blanket-rejected because context indicates ongoing operational consequence
        assert event.is_relevant is True
        assert event.severity_raw in ["medium", "high"]

    def test_dual_incident_resolved_and_new_active_disruption_is_retained(self):
        """Article mentioning both an averted event and a new active disruption recognizes the disruption."""
        sr = _raw(
            title="Strike called off at rail hub, but severe flood shuts down battery facility today",
            snippet="While rail strike was called off this morning, torrential rain and flash flood have shut down the battery manufacturing center today.",
        )
        event = self.svc.analyze_search_result(sr, entity_name="Battery Facility")
        # The new active disruption must be captured
        assert event.is_relevant is True
        assert event.event_type == "flood"
        assert event.severity_raw == "high"

    def test_negative_phrases_in_unrelated_contexts_do_not_falsely_reject(self):
        """Negations like 'no agreement reached' or 'not resolved' describe active disputes, not averted ones."""
        sr = _raw(
            title="No agreement reached as dock strike enters fourth day",
            snippet="Talks broke down with no agreement reached; dispute remains unresolved and active strike continues to halt container loading.",
        )
        event = self.svc.analyze_search_result(sr, entity_name="Dock Terminal")
        # Must NOT trigger averted rejection on substring 'agreement reached' or 'resolved'
        assert event.is_relevant is True
        assert event.event_type == "strike"
        assert event.severity_raw == "high"

    def test_unclear_active_status_routes_to_review_status(self):
        """When active status cannot be confidently determined, status is marked unclear with lower confidence."""
        sr = _raw(
            title="Chemical plant incident: status unconfirmed following reported leak",
            snippet="Conflicting reports emerge from industrial zone; unclear whether leak cleanup is complete or if operations remain shut down.",
        )
        event = self.svc.analyze_search_result(sr, entity_name="Chemical Plant")
        # The system marks severity as unclear and lowers confidence rather than inventing certainty
        assert event.is_relevant is True
        assert event.severity_raw == "unclear"
        assert event.confidence <= 0.50
