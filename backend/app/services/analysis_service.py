from dataclasses import dataclass, field
from typing import List, Optional
from app.core.llm_client import LLMClientWrapper, llm_client
from app.core.logging import logger
from app.models.events import DisruptionEvent, RawSearchResult


@dataclass
class ExtractionFailure:
    source_result_id: str
    queried_entity_id: str
    source_url: str
    error_type: str
    error_summary: str


@dataclass
class AnalysisBatchResult:
    events: List[DisruptionEvent] = field(default_factory=list)
    failures: List[ExtractionFailure] = field(default_factory=list)
    processed_count: int = 0

    @property
    def successful_count(self) -> int:
        return len(self.events)

    @property
    def failed_count(self) -> int:
        return len(self.failures)

    @property
    def rejected_count(self) -> int:
        return sum(1 for event in self.events if not event.is_relevant)

    @property
    def relevant_count(self) -> int:
        return sum(1 for event in self.events if event.is_relevant)

    def summary(self) -> dict:
        return {
            "processed": self.processed_count,
            "successful": self.successful_count,
            "failed": self.failed_count,
            "rejected": self.rejected_count,
            "relevant": self.relevant_count,
        }


class AnalysisService:
    """Analysis Agent service executing LLM extraction and false-positive relevance filtering."""

    def __init__(self, client: LLMClientWrapper = llm_client):
        self.client = client

    def analyze_search_result(
        self, search_result: RawSearchResult, entity_name: str = "Business Entity"
    ) -> DisruptionEvent:
        """Processes a single RawSearchResult into a structured Pydantic DisruptionEvent."""
        extracted = self.client.extract_disruption_event(
            title=search_result.title,
            snippet=search_result.snippet,
            entity_name=entity_name,
        )

        event = DisruptionEvent(
            source_url=search_result.url,
            source_result_id=search_result.id,
            headline=extracted.get("headline", search_result.title),
            summary=extracted.get("summary", search_result.snippet[:300]),
            event_type=extracted.get("event_type", "other"),
            location_mentioned=extracted.get("location_mentioned", entity_name),
            severity_raw=extracted.get("severity_raw", "medium"),
            extracted_entities=extracted.get("extracted_entities", [entity_name]),
            confidence=float(extracted.get("confidence", 0.5)),
            is_relevant=bool(extracted.get("is_relevant", True)),
            published_at=search_result.published_at,
        )

        logger.info(
            f"Analysis Agent processed '{event.headline}' -> is_relevant={event.is_relevant}, severity={event.severity_raw}"
        )
        return event

    def analyze_search_results(
        self, search_results: List[RawSearchResult], entity_name_map: dict = None
    ) -> List[DisruptionEvent]:
        """Processes a batch of search results into structured DisruptionEvents.

        Per-article extraction failures are logged and skipped so one provider
        failure does not abort the whole batch.
        """
        return self.analyze_search_results_batch(search_results, entity_name_map).events

    def analyze_search_results_batch(
        self, search_results: List[RawSearchResult], entity_name_map: Optional[dict] = None
    ) -> AnalysisBatchResult:
        """Processes a batch and returns events plus extraction failure counts."""
        name_map = entity_name_map or {}
        result = AnalysisBatchResult(processed_count=len(search_results))
        for sr in search_results:
            entity_name = name_map.get(sr.queried_entity_id, "Business Entity")
            try:
                event = self.analyze_search_result(sr, entity_name=entity_name)
            except Exception as exc:
                failure = ExtractionFailure(
                    source_result_id=sr.id,
                    queried_entity_id=sr.queried_entity_id,
                    source_url=sr.url,
                    error_type=exc.__class__.__name__,
                    error_summary=str(exc)[:200],
                )
                result.failures.append(failure)
                logger.warning(
                    "Analysis extraction failed for source_result_id=%s queried_entity_id=%s error_type=%s error=%s",
                    failure.source_result_id,
                    failure.queried_entity_id,
                    failure.error_type,
                    failure.error_summary,
                )
                continue
            result.events.append(event)
        logger.info("Analysis batch summary: %s", result.summary())
        return result


# Module instance singleton
analysis_service_instance = AnalysisService()


def get_analysis_service() -> AnalysisService:
    return analysis_service_instance
