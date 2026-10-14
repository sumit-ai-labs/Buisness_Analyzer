"""Verification Service — Phase D of Credibility Verification Engine.

Orchestrates all four credibility signals and computes the final authenticity score.

Architecture position:
    Detect → Understand → [VERIFY] → Connect → Assess → Alert

Signal weights (must sum to 1.0):
    source_reputation       : 0.35
    corroboration           : 0.25
    content_style           : 0.20
    llm_extraction_confidence: 0.20

Credibility thresholds:
    high        : 80 – 100
    moderate    : 60 – 79.99
    low         : 35 – 59.99
    unconfirmed :  0 – 34.99

Gate threshold: 35
    Events with authenticity_score < 35 are flagged is_gated=True and labelled
    "unconfirmed". They are NOT deleted and remain visible for review.

Disclaimer:
    This system produces a credibility/confidence score.
    It does NOT establish objective truth.
"""

from __future__ import annotations

import math
import logging
from urllib.parse import urlparse

from app.models.events import DisruptionEvent
from app.models.credibility import CredibilityAssessment
from app.core.domain_reputation import lookup_domain
from app.services.corroboration_service import count_corroborating_sources
from app.services.weather_service import WeatherSignal
from app.core import credibility_model

logger = logging.getLogger("business_disruption")

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

CRED_WEIGHTS: dict[str, float] = {
    "source_reputation": 0.35,
    "corroboration": 0.25,
    "content_style": 0.20,
    "llm_extraction_confidence": 0.20,
}
_WEIGHT_SUM = sum(CRED_WEIGHTS.values())
assert math.isclose(_WEIGHT_SUM, 1.0, abs_tol=1e-9), (
    f"CRED_WEIGHTS must sum to 1.0; got {_WEIGHT_SUM}"
)

CORROBORATION_CAP: int = 3
GATE_THRESHOLD: float = 35.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_domain(url: str) -> str:
    """Extract bare domain from a URL."""
    if not url:
        return ""
    url = url.strip().lower()
    if "://" in url:
        try:
            host = urlparse(url).hostname or ""
        except Exception:
            host = ""
    else:
        host = url.split("/")[0]
    if host.startswith("www."):
        host = host[4:]
    return host


def bucket_confidence(score: float) -> str:
    """Map a 0-100 authenticity score to a confidence label bucket.

    Thresholds (inclusive lower, exclusive upper for overlapping boundaries):
        high        ≥ 80
        moderate    ≥ 60
        low         ≥ 35
        unconfirmed  < 35

    Parameters
    ----------
    score: float in [0, 100]

    Returns
    -------
    str — one of 'high', 'moderate', 'low', 'unconfirmed'
    """
    if score >= 80.0:
        return "high"
    elif score >= 60.0:
        return "moderate"
    elif score >= 35.0:
        return "low"
    else:
        return "unconfirmed"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class VerificationService:
    """Orchestrates the four-signal credibility verification workflow.

    Usage
    -----
    service = VerificationService()
    assessment = service.verify(event, recent_events)
    """

    def __init__(self, time_window_hours: int = 48):
        self.time_window_hours = time_window_hours

    def verify(
        self,
        event: DisruptionEvent,
        recent_events: list[DisruptionEvent] | None = None,
        *,
        # Optional pre-computed overrides (used in tests / demo)
        override_source_reputation: float | None = None,
        override_corroboration_count: int | None = None,
        override_content_style_score: float | None = None,
        weather_signal: WeatherSignal | None = None,
    ) -> CredibilityAssessment:
        """Run the full verification pipeline for a DisruptionEvent.

        Parameters
        ----------
        event:
            The DisruptionEvent to assess.
        recent_events:
            Other recent events to search for corroboration. Pass [] or None
            for no corroboration check.
        override_*:
            Optional test/demo overrides to bypass live computation for
            individual signals.
        weather_signal:
            Optional WeatherSignal from the weather corroboration service.
            If ``confirms_event=True``, adds +1 to corroboration_count
            (respecting CORROBORATION_CAP). Only applied for flood/weather
            event types.

        Returns
        -------
        CredibilityAssessment with complete factor breakdown.
        """
        if recent_events is None:
            recent_events = []

        source_domain = _extract_domain(event.source_url)

        # ------------------------------------------------------------------
        # Signal 1: Source Reputation
        # ------------------------------------------------------------------
        if override_source_reputation is not None:
            rep_score = override_source_reputation
            rep_tier = "override"
        else:
            rep_score, rep_tier = lookup_domain(source_domain)

        # ------------------------------------------------------------------
        # Signal 2: Cross-source Corroboration (+ optional weather signal)
        # ------------------------------------------------------------------
        if override_corroboration_count is not None:
            corroboration_count = override_corroboration_count
        else:
            corroboration_count = count_corroborating_sources(
                event, recent_events, time_window_hours=self.time_window_hours
            )

        # Weather corroboration: if weather confirms the event, add +1
        weather_confirmed = False
        weather_contradicted = False
        if weather_signal is not None and weather_signal.confirms_event:
            corroboration_count += 1
            weather_confirmed = True
            logger.info(
                f"[VERIFY][WEATHER] +1 corroboration for event={event.id} "
                f"(precip={weather_signal.precipitation_mm_24h}mm)"
            )
        elif (
            weather_signal is not None
            and weather_signal.status == "checked"
            and getattr(weather_signal, "classification", "not_supported") == "not_supported"
            and event.event_type in {"flood", "weather"}
        ):
            weather_contradicted = True
            logger.info(
                f"[VERIFY][WEATHER] telemetry did not support event={event.id} "
                f"(precip={weather_signal.precipitation_mm_24h}mm wind={weather_signal.wind_speed_kmh}km/h)"
            )

        corroboration_score = min(corroboration_count, CORROBORATION_CAP) / CORROBORATION_CAP

        # ------------------------------------------------------------------
        # Signal 3: ML Content-Style Score
        # ------------------------------------------------------------------
        if override_content_style_score is not None:
            content_style_score = override_content_style_score
            model_ver = credibility_model.get_model_version()
        else:
            text = " ".join(filter(None, [event.headline, event.summary]))
            content_style_score = credibility_model.predict_style_score(text)
            if not credibility_model.is_loaded():
                model_ver = "credibility-clf-unavailable"
            elif credibility_model.get_last_error() and "Inference failure" in (credibility_model.get_last_error() or ""):
                model_ver = "credibility-clf-error"
            else:
                model_ver = credibility_model.get_model_version()

        # ------------------------------------------------------------------
        # Signal 4: LLM Extraction Confidence (pass-through — not recomputed)
        # ------------------------------------------------------------------
        llm_conf = event.confidence

        # ------------------------------------------------------------------
        # Weighted Credibility Formula
        # ------------------------------------------------------------------
        source_reputation_component = rep_score * 100.0
        corroboration_component = corroboration_score * 100.0
        content_style_component = content_style_score * 100.0
        llm_component = llm_conf * 100.0

        weighted_source    = CRED_WEIGHTS["source_reputation"]       * source_reputation_component
        weighted_corr      = CRED_WEIGHTS["corroboration"]            * corroboration_component
        weighted_ml        = CRED_WEIGHTS["content_style"]            * content_style_component
        weighted_llm       = CRED_WEIGHTS["llm_extraction_confidence"] * llm_component

        authenticity_score = round(
            weighted_source + weighted_corr + weighted_ml + weighted_llm,
            2,
        )
        if weather_contradicted:
            authenticity_score = round(authenticity_score - 15.0, 2)
        # Hard clamp to [0, 100]
        authenticity_score = max(0.0, min(100.0, authenticity_score))

        confidence_label = bucket_confidence(authenticity_score)
        is_gated = authenticity_score < GATE_THRESHOLD

        factors = {
            "source_reputation":        round(weighted_source, 2),
            "corroboration":            round(weighted_corr, 2),
            "content_style":            round(weighted_ml, 2),
            "llm_extraction_confidence": round(weighted_llm, 2),
        }
        if weather_signal is not None and event.event_type in {"flood", "weather"}:
            factors["weather_corroboration"] = 15.0 if weather_confirmed else (-15.0 if weather_contradicted else 0.0)

        # ------------------------------------------------------------------
        # Structured log entry
        # ------------------------------------------------------------------
        logger.info(
            f"[VERIFY] event={event.id} domain={source_domain} "
            f"source={rep_score:.2f} corroboration={corroboration_count} "
            f"ml={content_style_score:.2f} llm={llm_conf:.2f} "
            f"score={authenticity_score:.2f} label={confidence_label} "
            f"gated={str(is_gated).lower()}"
        )

        return CredibilityAssessment(
            event_id=event.id,
            source_domain=source_domain if source_domain else "unknown",
            source_reputation_score=rep_score,
            source_tier=rep_tier,
            corroborating_source_count=corroboration_count,
            corroboration_score=corroboration_score,
            content_style_score=content_style_score,
            model_version=model_ver,
            llm_extraction_confidence=llm_conf,
            authenticity_score=authenticity_score,
            confidence_label=confidence_label,
            is_gated=is_gated,
            factors=factors,
        )


# ---------------------------------------------------------------------------
# Module singleton
# ---------------------------------------------------------------------------
_verification_service_instance: VerificationService | None = None


def get_verification_service() -> VerificationService:
    """Return the module-level VerificationService singleton."""
    global _verification_service_instance
    if _verification_service_instance is None:
        _verification_service_instance = VerificationService()
    return _verification_service_instance
