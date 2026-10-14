"""Section B — Detect (Research Agent) Edge-Case Tests.

Tests B1–B7 from the full-system test matrix.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.core.tavily_client import TavilyAPIError
from app.models.entity import BusinessEntity, EntityMetadata
from app.models.events import RawSearchResult
from app.services.research_service import (
    ResearchService,
    filter_by_recency,
    sort_by_recency,
)
from tests.conftest import make_entity, make_raw_result


# ===========================================================================
# B1: Entity with no `location` set — impossible due to Pydantic min_length=1
# We test that the query builder works with a minimal location string
# Type: Unit
# ===========================================================================
class TestB1MinimalLocation:
    def test_query_builder_handles_entity_with_location(self):
        """B1: location is required (min_length=1), so query always has it.
        Confirm the query is well-formed."""
        entity = make_entity(name="Widget Corp", location="Unknown")
        svc = ResearchService.__new__(ResearchService)
        query = svc.generate_entity_query(entity)
        assert '"Widget Corp"' in query
        assert '"Unknown"' in query

    def test_entity_without_location_rejected_by_pydantic(self):
        """B1b: BusinessEntity requires location min_length=1; empty string fails."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            BusinessEntity(
                name="Test",
                type="supplier",
                location="",  # violates min_length=1
                criticality="high",
            )


# ===========================================================================
# B2: Tavily returns zero results
# Type: Integration
# ===========================================================================
class TestB2ZeroResults:
    def test_zero_tavily_results_returns_empty_list(self):
        """B2: When Tavily returns zero results, service returns empty list, no crash."""
        mock_client = MagicMock()
        mock_client.search.return_value = []
        svc = ResearchService(client=mock_client)
        entity = make_entity(name="Ghost Entity", location="Nowhere")
        results = svc.search_disruptions_for_entity(entity)
        assert results == []

    def test_network_search_skips_entity_with_no_results(self):
        """B2b: Zero results for one entity doesn't crash the network scan."""
        mock_client = MagicMock()
        mock_client.search.return_value = []
        svc = ResearchService(client=mock_client)
        entities = [
            make_entity(id="e1", name="Entity A", location="Loc A"),
            make_entity(id="e2", name="Entity B", location="Loc B"),
        ]
        results = svc.search_disruptions_for_network(entities)
        assert results == []
        assert mock_client.search.call_count == 2  # Both called


# ===========================================================================
# B3: Tavily API key invalid
# Type: Resilience
# ===========================================================================
class TestB3InvalidApiKey:
    def test_invalid_api_key_raises_typed_error(self):
        """B3: Invalid Tavily API key surfaces TavilyAPIError, not raw SDK traceback."""
        mock_client = MagicMock()
        mock_client.search.side_effect = TavilyAPIError("TAVILY_API_KEY is not configured")
        svc = ResearchService(client=mock_client)
        entity = make_entity(name="Test", location="Test")
        # ResearchService catches TavilyAPIError and returns []
        results = svc.search_disruptions_for_entity(entity)
        assert results == []

    def test_search_failure_doesnt_crash_other_entities(self):
        """B3b: API failure for one entity doesn't break the batch."""
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TavilyAPIError("Invalid key")
            return [{
                "url": "https://example.com",
                "title": "OK",
                "content": "Fine",
                "published_date": datetime.now(timezone.utc).isoformat(),
            }]

        mock_client = MagicMock()
        mock_client.search.side_effect = side_effect
        svc = ResearchService(client=mock_client)
        entities = [
            make_entity(id="e1", name="Failing", location="Loc A"),
            make_entity(id="e2", name="Working", location="Loc B"),
        ]
        results = svc.search_disruptions_for_network(entities)
        # First entity fails, second succeeds
        assert len(results) >= 1


# ===========================================================================
# B4: Article older than SEARCH_RECENCY_DAYS
# Type: Unit
# ===========================================================================
class TestB4StaleArticle:
    def test_old_article_dropped_by_recency_filter(self):
        """B4: Article older than max_age_days is dropped."""
        now = datetime.now(timezone.utc)
        old = make_raw_result(url="https://old.com/article", published_at=now - timedelta(days=60))
        fresh = make_raw_result(url="https://new.com/article", published_at=now - timedelta(days=1))
        result = filter_by_recency([old, fresh], max_age_days=14)
        assert len(result) == 1
        assert result[0].url == "https://new.com/article"


# ===========================================================================
# B5: Article with missing published_date
# Type: Unit
# ===========================================================================
class TestB5MissingPublishedDate:
    def test_missing_published_date_is_dropped_by_default(self):
        """B5: Articles with no publication date are dropped by default for live accuracy."""
        unknown = make_raw_result(url="https://unknown.com", published_at=None)
        result = filter_by_recency([unknown], max_age_days=14)
        assert result == []

    def test_missing_published_date_can_be_kept_by_override(self):
        """B5b: An explicit override can keep undated articles for analyst review."""
        unknown = make_raw_result(url="https://unknown.com", published_at=None)
        result = filter_by_recency([unknown], max_age_days=14, keep_undated=True)
        assert len(result) == 1


# ===========================================================================
# B6: Network has zero entities
# Type: Integration
# ===========================================================================
class TestB6ZeroEntities:
    def test_zero_entities_is_clean_noop(self):
        """B6: Research cycle with zero entities is a clean no-op, not an error."""
        mock_client = MagicMock()
        svc = ResearchService(client=mock_client)
        results = svc.search_disruptions_for_network([])
        assert results == []
        mock_client.search.assert_not_called()


# ===========================================================================
# B7: Two entities' queries return the same article
# Type: Integration
# ===========================================================================
class TestB7DuplicateArticle:
    def test_same_article_creates_separate_raw_results_per_entity(self):
        """B7: Same URL from two entity queries → two RawSearchResults, one per entity."""
        mock_client = MagicMock()
        mock_client.search.return_value = [
            {
                "url": "https://shared.com/article",
                "title": "Shared News",
                "content": "Same article text",
                "published_date": datetime.now(timezone.utc).isoformat(),
            }
        ]
        svc = ResearchService(client=mock_client)
        entities = [
            make_entity(id="e1", name="Entity A", location="Mumbai, India"),
            make_entity(id="e2", name="Entity B", location="Mumbai, India"),
        ]
        results = svc.search_disruptions_for_network(entities)
        # Should produce 2 RawSearchResults (one per entity query)
        assert len(results) == 2
        entity_ids = {r.queried_entity_id for r in results}
        assert entity_ids == {"e1", "e2"}
        # Both point to same URL
        urls = {r.url for r in results}
        assert urls == {"https://shared.com/article"}
