from typing import List, Optional
from rapidfuzz import fuzz

from app.core.logging import logger
from app.models.entity import BusinessEntity
from app.models.events import DisruptionEvent, MatchedImpact
from app.models.geo import GeoVerificationResult
from app.services.geo_matching_service import GeoMatchingService, get_geo_matching_service
from app.services.network_service import NetworkService, get_network_service


class MatcherService:
    """Entity Matcher service linking extracted DisruptionEvents to network graph nodes

    using multi-factor Geographic Verification and Disambiguation.
    """

    def __init__(
        self,
        network_service: Optional[NetworkService] = None,
        geo_matching_service: Optional[GeoMatchingService] = None,
    ):
        self.network_service = network_service or get_network_service()
        self.geo_matching_service = geo_matching_service or get_geo_matching_service()

    def match_event_to_network(
        self,
        event: DisruptionEvent,
        threshold_score: float = 60.0,
        geo_result: Optional[GeoVerificationResult] = None,
    ) -> Optional[MatchedImpact]:
        """Matches event locations and extracted entities against network entities using geographic evidence.

        Ensures ambiguous locations or uncertain entity mappings are not guessed or propagated.
        """
        entities = self.network_service.list_entities()
        if not entities:
            logger.info("Network contains zero entities. Entity Matcher skipping.")
            return None

        # 1. Geographic Verification & Disambiguation
        geo_res = geo_result or self.geo_matching_service.verify_and_match(event, entities)

        # Failure-safe principle: If location/entity is ambiguous or unresolved, DO NOT guess or attach to network!
        if geo_res.status == "LOCATION_AMBIGUOUS":
            logger.warning(
                f"[GEO-MATCH][AMBIGUOUS] Event '{event.headline}' marked LOCATION_AMBIGUOUS: "
                f"{geo_res.ambiguity_reason}. Halting network impact propagation."
            )
            return MatchedImpact(
                event_id=event.id,
                matched_entity_ids=[],
                match_confidence=round(geo_res.entity_match_confidence / 100.0, 2),
                downstream_entity_ids=[],
                geo_status="LOCATION_AMBIGUOUS",
                ambiguity_reason=geo_res.ambiguity_reason,
            )

        if geo_res.status == "LOCATION_UNRESOLVED":
            logger.warning(
                f"[GEO-MATCH][UNRESOLVED] Event '{event.headline}' marked LOCATION_UNRESOLVED: "
                f"{geo_res.ambiguity_reason}. Halting network impact propagation."
            )
            return None

        matched_entity_ids: List[str] = []
        max_confidence = 0.0

        # If an unambiguous primary entity was identified by geo-matching
        if geo_res.primary_matched_entity_id:
            matched_entity_ids = [geo_res.primary_matched_entity_id]
            max_confidence = geo_res.entity_match_confidence / 100.0
        else:
            # Fallback to lexical matching only if geo status is not ambiguous or unresolved
            for entity in entities:
                scores = []
                for ext_entity in event.extracted_entities:
                    scores.append(fuzz.ratio(ext_entity.lower(), entity.name.lower()))
                    scores.append(fuzz.partial_ratio(ext_entity.lower(), entity.name.lower()))

                best_entity_score = max(scores) if scores else 0.0
                if best_entity_score >= threshold_score:
                    matched_entity_ids.append(entity.id)
                    max_confidence = max(max_confidence, best_entity_score / 100.0)

        if not matched_entity_ids:
            logger.info(f"No network entities matched event '{event.headline}'")
            return None

        # Gather downstream impacted entities via network traversal
        downstream_ids = set()
        for matched_id in matched_entity_ids:
            downstream_entities = self.network_service.get_downstream(matched_id, max_depth=5)
            for de in downstream_entities:
                downstream_ids.add(de.id)

        # Exclude direct matches from downstream list
        downstream_ids = list(downstream_ids - set(matched_entity_ids))

        impact = MatchedImpact(
            event_id=event.id,
            matched_entity_ids=matched_entity_ids,
            match_confidence=round(max_confidence, 2),
            downstream_entity_ids=downstream_ids,
            geo_status=geo_res.status,
            ambiguity_reason=geo_res.ambiguity_reason,
        )

        logger.info(
            f"Entity Matcher linked event '{event.headline}' (status={geo_res.status}) "
            f"to direct entities {matched_entity_ids} and downstream {downstream_ids}"
        )
        return impact


# Module instance singleton
matcher_service_instance = MatcherService()


def get_matcher_service() -> MatcherService:
    return matcher_service_instance
