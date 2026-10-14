from typing import Dict, Optional
from app.core.dynamic_config import DynamicConfigStore, get_config_store
from app.core.logging import logger
from app.models.entity import BusinessEntity
from app.models.events import DisruptionEvent
from app.models.risk import RiskAssessment


class RiskService:
    """Deterministic Risk Engine evaluating 0-100 severity score with transparent factor breakdown."""

    def __init__(self, config_store: DynamicConfigStore = None):
        self.config_store = config_store or get_config_store()

    def evaluate_risk(
        self,
        entity: BusinessEntity,
        event: DisruptionEvent,
        dependency_weight: float = 1.0,
        credibility_score: Optional[float] = None,
    ) -> RiskAssessment:
        """Evaluates deterministic risk score for an affected entity given a disruption event.

        Parameters
        ----------
        credibility_score:
            Optional authenticity_score from CredibilityAssessment (0–1, i.e. divide by 100
            before passing in). When supplied, the confidence multiplier blends LLM confidence
            and credibility 50/50. When absent, falls back to original formula.
            All other factors (severity weights, thresholds) remain unchanged.
        """
        config = self.config_store.get_config()
        weights = config.weights
        thresholds = config.thresholds

        # 1. Dependency Factor (0.0 to 100.0)
        f_dependency = max(0.0, min(1.0, dependency_weight)) * 100.0

        # 2. Criticality Factor (0.0 to 100.0)
        crit_map = {"high": 100.0, "medium": 50.0, "low": 25.0}
        f_criticality = crit_map.get(entity.criticality, 50.0)

        # 3. Lead Time Factor (0.0 to 100.0, capped at 60 days)
        lead_days = entity.metadata.lead_time_days if entity.metadata.lead_time_days is not None else 14
        f_lead_time = min(lead_days / 60.0, 1.0) * 100.0

        # 4. Single Source Vulnerability Factor (0.0 or 100.0)
        f_single_source = 0.0 if entity.metadata.alternative_supplier_available else 100.0

        # 5. Extraction Confidence Factor (0.0 to 100.0)
        #    If credibility_score is available: blend LLM confidence 50/50 with credibility.
        #    Combined trust is still bounded to [0, 1] before scaling.
        raw_llm_conf = max(0.0, min(1.0, event.confidence))
        if credibility_score is not None:
            cred_norm = max(0.0, min(1.0, credibility_score))  # already 0–1
            combined_trust = 0.5 * raw_llm_conf + 0.5 * cred_norm
        else:
            combined_trust = raw_llm_conf  # legacy behaviour unchanged
        f_confidence = combined_trust * 100.0

        # Weighted calculation
        c_dependency = weights.dependency * f_dependency
        c_criticality = weights.criticality * f_criticality
        c_lead_time = weights.lead_time * f_lead_time
        c_single_source = weights.single_source * f_single_source
        c_confidence = weights.confidence * f_confidence

        total_score = round(
            c_dependency + c_criticality + c_lead_time + c_single_source + c_confidence, 2
        )
        total_score = min(100.0, max(0.0, total_score))

        # Risk Level Classification based on dynamic thresholds
        if total_score < thresholds.low:
            risk_level = "low"
        elif total_score < thresholds.medium:
            risk_level = "medium"
        elif total_score < thresholds.high:
            risk_level = "high"
        else:
            risk_level = "critical"

        factors: Dict[str, float] = {
            "dependency_weight_pct": round(f_dependency, 1),
            "criticality_score": round(f_criticality, 1),
            "lead_time_days_score": round(f_lead_time, 1),
            "single_source_vulnerability": round(f_single_source, 1),
            "extraction_confidence": round(f_confidence, 1),
            "weighted_dependency_contrib": round(c_dependency, 2),
            "weighted_criticality_contrib": round(c_criticality, 2),
            "weighted_lead_time_contrib": round(c_lead_time, 2),
            "weighted_single_source_contrib": round(c_single_source, 2),
            "weighted_confidence_contrib": round(c_confidence, 2),
        }

        assessment = RiskAssessment(
            event_id=event.id,
            entity_id=entity.id,
            severity_score=total_score,
            factors=factors,
            risk_level=risk_level,
        )

        logger.info(
            f"Risk Engine evaluated entity '{entity.name}' -> Score: {total_score}/100 ({risk_level.upper()})"
        )
        return assessment


# Module instance singleton
risk_service_instance = RiskService()


def get_risk_service() -> RiskService:
    return risk_service_instance
