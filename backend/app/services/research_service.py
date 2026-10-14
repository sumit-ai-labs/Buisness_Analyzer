from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import List, Optional, Union

from app.core.config import settings
from app.core.logging import logger
from app.core.tavily_client import TavilyAPIError, TavilyClientWrapper, tavily_client
from app.models.entity import BusinessEntity
from app.models.events import RawSearchResult


# ---------------------------------------------------------------------------
# Freshness utilities
# ---------------------------------------------------------------------------


def _parse_published_date(raw: Optional[Union[str, int, float]]) -> Optional[datetime]:
    """Best-effort parse of Tavily's ``published_date`` string or timestamp.

    Supports:
    - ISO-8601 timestamps (with/without 'Z', with +/- timezone offsets, naive)
    - RFC 2822 / RFC-style dates (e.g. 'Wed, 07 Oct 2026 21:00:00 GMT', numeric tz offsets)
    - Unix epoch timestamps (numeric or string digits, in seconds or milliseconds)
    - Common strptime formats

    All timezone-aware timestamps are normalized to UTC.
    Naive timestamps are explicitly interpreted as UTC (not local timezone).
    Malformed, unparseable, or missing dates safely return None.
    """
    if raw is None:
        return None

    # Handle numeric epoch values (int or float)
    if isinstance(raw, (int, float)):
        try:
            val = float(raw)
            if val > 1e11:  # Milliseconds
                val = val / 1000.0
            return datetime.fromtimestamp(val, tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            logger.warning(f"Could not parse numeric published_date '{raw}', treating as None")
            return None

    if not isinstance(raw, str):
        logger.warning(f"Unexpected published_date type {type(raw)}, treating as None")
        return None

    raw_str = raw.strip()
    if not raw_str:
        return None

    # Handle numeric epoch string (e.g. "1728345600", "1728345600.0", "1728345600000")
    # Must look like a timestamp (not a date like "20261012" - 8 digits)
    cleaned_num = raw_str.replace(".", "", 1)
    if cleaned_num.isdigit() and len(raw_str.split(".")[0]) >= 10:
        try:
            val = float(raw_str)
            if val > 1e11:
                val = val / 1000.0
            return datetime.fromtimestamp(val, tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            pass

    # 1. ISO-8601 parsing (Python 3.11+ fromisoformat handles 'Z', offsets, etc.)
    try:
        dt = datetime.fromisoformat(raw_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt
    except (ValueError, TypeError):
        pass

    # 2. RFC 2822 / RFC-style dates via email.utils.parsedate_to_datetime
    # Handles: 'Wed, 07 Oct 2026 21:00:00 GMT', '07 Oct 2026 21:00:00 +0200', etc.
    try:
        dt = parsedate_to_datetime(raw_str)
        if dt is not None:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            return dt
    except (ValueError, TypeError, IndexError, OverflowError):
        pass

    # 3. Fallback: try common formats Tavily or feeds have used historically
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d %b %Y %H:%M:%S %Z",
        "%d %b %Y %H:%M:%S",
        "%a, %d %b %Y %H:%M:%S",
    ):
        try:
            dt = datetime.strptime(raw_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            return dt
        except (ValueError, TypeError):
            continue

    logger.warning(f"Could not parse published_date '{raw}', treating as None")
    return None


def filter_by_recency(
    results: list[RawSearchResult],
    max_age_days: int = 14,
    keep_undated: bool | None = None,
    reference_time: Optional[datetime] = None,
) -> list[RawSearchResult]:
    """Drop search results older than ``max_age_days`` relative to reference_time or UTC now.

    Articles with no known publication date are dropped by default because live
    monitoring should not alert on stale articles that lack reliable dates.
    """
    if keep_undated is None:
        keep_undated = settings.SEARCH_KEEP_UNDATED_RESULTS

    if reference_time is not None:
        if reference_time.tzinfo is None:
            now = reference_time.replace(tzinfo=timezone.utc)
        else:
            now = reference_time.astimezone(timezone.utc)
    else:
        now = datetime.now(timezone.utc)

    cutoff = now - timedelta(days=max_age_days)
    future_limit = now + timedelta(days=1)  # 24h timezone and clock skew buffer
    kept: list[RawSearchResult] = []
    for r in results:
        pub_at = r.published_at
        if pub_at is not None:
            if pub_at.tzinfo is None:
                pub_at = pub_at.replace(tzinfo=timezone.utc)
            else:
                pub_at = pub_at.astimezone(timezone.utc)

        if pub_at is None:
            if keep_undated:
                kept.append(r)
                logger.warning(
                    f"No published date for result {r.url}, keeping because SEARCH_KEEP_UNDATED_RESULTS=true"
                )
            else:
                logger.info(f"Dropped undated result: {r.url}")
        elif pub_at > future_limit:
            logger.info(
                f"Dropped future-dated result ({pub_at.isoformat()}): {r.url}"
            )
        elif pub_at >= cutoff:
            kept.append(r)
        else:
            logger.info(
                f"Dropped stale result ({pub_at.isoformat()}): {r.url}"
            )
    return kept


def sort_by_recency(results: list[RawSearchResult]) -> list[RawSearchResult]:
    """Sort results by ``published_at`` descending (most recent first).

    Results with ``published_at=None`` are placed at the end.
    """
    def _sort_key(r: RawSearchResult) -> datetime:
        if r.published_at is not None:
            dt = r.published_at
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        return datetime.min.replace(tzinfo=timezone.utc)

    return sorted(results, key=_sort_key, reverse=True)


# ---------------------------------------------------------------------------
# Research Service
# ---------------------------------------------------------------------------


class ResearchService:
    """Research Agent service generating targeted web search queries and gathering raw snippets."""

    def __init__(self, client: TavilyClientWrapper = tavily_client):
        self.client = client

    def generate_entity_query(self, entity: BusinessEntity) -> str:
        """Generates targeted disruption search query for a given entity and location."""
        terms = "active OR ongoing OR today OR current"
        disruptions = "flood OR strike OR closure OR failure OR disruption OR port OR explosion OR bankruptcy OR severe weather"
        resolved = '"averted" "called off" "resumed" "agreement reached" "resolved"'
        return f'"{entity.name}" "{entity.location}" ({terms}) ({disruptions}) -({resolved})'

    def search_disruptions_for_entity(
        self, entity: BusinessEntity, max_results: int = 3
    ) -> List[RawSearchResult]:
        """Dispatches search query for a single entity and returns attributed RawSearchResult items.

        Every Tavily call passes ``topic="news"`` and ``days=SEARCH_RECENCY_DAYS``
        to restrict to recent news articles.  Results are then freshness-filtered
        and sorted most-recent-first before being returned.

        If Tavily API key is unconfigured or fails, returns an empty list gracefully with log warning.
        """
        query = self.generate_entity_query(entity)
        logger.info(f"Research Agent querying web for entity '{entity.name}' (query: '{query}')")

        try:
            results = self.client.search(
                query=query,
                max_results=max_results,
                topic="news",
                days=settings.SEARCH_RECENCY_DAYS,
            )
        except TavilyAPIError as err:
            logger.warning(f"Tavily search skipped or failed for '{entity.name}': {err}")
            return []

        raw_results = []
        for item in results:
            try:
                published_at = _parse_published_date(item.get("published_date"))
            except Exception as err:
                logger.warning(
                    f"Unexpected error parsing published_date '{item.get('published_date')}': {err}"
                )
                published_at = None
            raw_result = RawSearchResult(
                url=item.get("url", "https://example.com/source"),
                title=item.get("title", "News Article"),
                snippet=item.get("content", item.get("snippet", "")),
                queried_entity_id=entity.id,
                query_used=query,
                published_at=published_at,
            )
            raw_results.append(raw_result)

        # Hard freshness filter — drop articles older than max_age_days
        raw_results = filter_by_recency(
            raw_results,
            max_age_days=settings.SEARCH_RECENCY_DAYS,
            keep_undated=settings.SEARCH_KEEP_UNDATED_RESULTS,
        )

        # Sort by recency — freshest first
        raw_results = sort_by_recency(raw_results)

        logger.info(
            f"Research Agent fetched {len(raw_results)} results for entity '{entity.name}' "
            f"(after recency filter, days={settings.SEARCH_RECENCY_DAYS})"
        )
        return raw_results

    def search_disruptions_for_network(
        self, entities: List[BusinessEntity]
    ) -> List[RawSearchResult]:
        """Runs disruption search across all active network entities."""
        all_raw_results = []
        active_entities = [e for e in entities if e.status == "active"]
        logger.info(f"Research Agent scanning network with {len(active_entities)} active entities.")

        for entity in active_entities:
            entity_results = self.search_disruptions_for_entity(entity)
            all_raw_results.extend(entity_results)

        return all_raw_results


# Module instance singleton
research_service_instance = ResearchService()


def get_research_service() -> ResearchService:
    return research_service_instance
