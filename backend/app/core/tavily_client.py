from typing import Any, Dict, List, Optional
import httpx

from app.core.config import settings
from app.core.logging import logger


class TavilyAPIError(Exception):
    """Custom exception raised when Tavily API returns an error or fails."""

    pass


class TavilyClientWrapper:
    """Wrapper around Tavily search API with robust fallback handling and typed exceptions."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.TAVILY_API_KEY

    def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "advanced",
        topic: str = "news",
        days: int | None = None,
    ) -> List[Dict[str, Any]]:
        """Executes search via Tavily SDK or HTTP REST API.

        Parameters
        ----------
        topic:
            Search index to use. "news" restricts to news articles; "general"
            for the full web index.  Default is "news" so we get recency metadata.
        days:
            Maximum age of results in days.  When None, falls back to
            ``settings.SEARCH_RECENCY_DAYS``.

        Raises TavilyAPIError if API key is missing or request fails.
        """
        if not self.api_key or not self.api_key.strip():
            logger.warning("Tavily API key is missing. Skipping live web search.")
            raise TavilyAPIError("TAVILY_API_KEY is not configured in settings or environment.")

        if days is None:
            days = settings.SEARCH_RECENCY_DAYS

        url = "https://api.tavily.com/search"
        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "topic": topic,
            "days": days,
            "include_answer": False,
            "include_raw_content": False,
        }

        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.post(url, json=payload)
                if response.status_code == 401 or response.status_code == 403:
                    raise TavilyAPIError(f"Invalid Tavily API key (HTTP {response.status_code})")
                response.raise_for_status()
                data = response.json()
                return data.get("results", [])
        except httpx.HTTPError as exc:
            logger.error(f"Tavily API HTTP error for query '{query}': {exc}")
            raise TavilyAPIError(f"Tavily search request failed: {str(exc)}") from exc
        except Exception as exc:
            logger.error(f"Unexpected Tavily search error: {exc}")
            raise TavilyAPIError(f"Tavily search failed: {str(exc)}") from exc


# Module-level client instance
tavily_client = TavilyClientWrapper()
