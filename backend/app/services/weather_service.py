"""Weather Corroboration Service — optional independent signal for the Credibility Engine.

Checks real weather telemetry at an entity's coordinates to independently
corroborate flood/weather-type disruption events. This plugs into the existing
corroboration count in the credibility formula — it is NOT a new pipeline stage.

Design rules:
- Only fires for event types in EVENT_WEATHER_MAP (flood, weather).
- API failure or missing coordinates degrade to neutral (never crashes, never
  fabricates confirmation, never counts as disconfirming evidence).
- Uses Open-Meteo — free, no API key, no signup.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

from app.core.weather_client import get_recent_weather
from app.models.entity import BusinessEntity
from app.models.events import DisruptionEvent

logger = logging.getLogger("business_disruption")


# ---------------------------------------------------------------------------
# WeatherSignal model
# ---------------------------------------------------------------------------

WeatherSignalStatus = Literal[
    "checked",
    "no_coordinates",
    "not_applicable",
    "unavailable",
    "insufficient_coverage",
    "not_checked",
    "confirmed",
    "not_supported",
]

WeatherSignalClassification = Literal[
    "confirmed",
    "not_supported",
    "unavailable",
    "not_checked",
    "insufficient_coverage",
]


class WeatherSignal(BaseModel):
    """Result of an independent weather corroboration check.

    status meanings:
        checked         — API responded; confirms_event reflects threshold comparison.
        no_coordinates  — Entity has no lat/lon; cannot check.
        not_applicable  — Event type is not weather-related (e.g. strike, closure).
        unavailable     — API call failed; treat as neutral.
        insufficient_coverage — Geographic or temporal coverage inadequate.
    """

    status: WeatherSignalStatus = Field(
        ..., description="Outcome status of the weather check"
    )
    classification: WeatherSignalClassification = Field(
        default="not_checked",
        description="Standardized classification: confirmed, not_supported, unavailable, not_checked, insufficient_coverage",
    )
    confirms_event: bool = Field(
        default=False,
        description="True if weather data corroborates the disruption event",
    )
    precipitation_mm_24h: Optional[float] = Field(
        default=None,
        description="Total precipitation (mm) in the last 24 hours at entity coordinates",
    )
    wind_speed_kmh: Optional[float] = Field(
        default=None,
        description="Current wind speed (km/h) at entity coordinates",
    )
    explanation: Optional[str] = Field(
        default=None,
        description="Human-readable explanation of evidence and its limitations",
    )

    @model_validator(mode="after")
    def populate_classification_and_explanation(self) -> WeatherSignal:
        # Determine classification if default or not explicitly specialized
        if not self.classification or self.classification == "not_checked":
            if self.confirms_event or self.status == "confirmed":
                self.classification = "confirmed"
            elif self.status in ("not_supported",):
                self.classification = "not_supported"
            elif self.status == "checked":
                self.classification = "confirmed" if self.confirms_event else "not_supported"
            elif self.status == "unavailable":
                self.classification = "unavailable"
            elif self.status in ("no_coordinates", "insufficient_coverage"):
                self.classification = "insufficient_coverage"
            else:
                self.classification = "not_checked"

        # Construct clear explanation text if not already provided
        if not self.explanation:
            precip_str = f"{self.precipitation_mm_24h:.1f}mm" if self.precipitation_mm_24h is not None else "N/A"
            wind_str = f"{self.wind_speed_kmh:.1f}km/h" if self.wind_speed_kmh is not None else "N/A"
            if self.classification == "confirmed":
                self.explanation = (
                    f"Confirmed: Local weather observations ({precip_str} rain, {wind_str} wind) "
                    f"satisfy the configured threshold criteria."
                )
            elif self.classification == "not_supported":
                self.explanation = (
                    f"Not supported by the available observations: Measured local weather ({precip_str} rain, "
                    f"{wind_str} wind) remained below the disruption threshold."
                )
            elif self.classification == "unavailable":
                self.explanation = (
                    "Unavailable: Weather provider service was unreachable or returned no data; "
                    "corroboration is inconclusive."
                )
            elif self.classification == "insufficient_coverage":
                self.explanation = (
                    "Insufficient geographic or temporal coverage: Missing valid coordinates or "
                    "observation window does not match the event timeframe."
                )
            else:
                self.explanation = "Not checked: Disruption event type is not weather-related."
        return self


# ---------------------------------------------------------------------------
# Thresholds per event type
# ---------------------------------------------------------------------------

EVENT_WEATHER_MAP: dict[str, dict[str, float]] = {
    "flood": {"precipitation_mm_threshold": 20.0},
    "weather": {"precipitation_mm_threshold": 15.0, "wind_kmh_threshold": 40.0},
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def check_weather_corroboration(
    event: DisruptionEvent,
    entity: BusinessEntity,
) -> WeatherSignal:
    """Check real weather data to independently corroborate a disruption event.

    Returns a WeatherSignal — never raises. Defaults to ``confirms_event=False``
    whenever data is unavailable or the event type is not weather-related.

    Parameters
    ----------
    event:
        The disruption event to corroborate.
    entity:
        The business entity with (optional) latitude/longitude.

    Returns
    -------
    WeatherSignal with status, classification, explanation, and telemetry data.
    """
    # Gate 1: Is this event type weather-checkable?
    thresholds = EVENT_WEATHER_MAP.get(event.event_type)
    if not thresholds:
        return WeatherSignal(
            status="not_applicable",
            classification="not_checked",
            confirms_event=False,
            explanation="Not checked: Disruption event type is not weather-related.",
        )

    # Gate 2: Does the entity have valid coordinates?
    if entity.latitude is None or entity.longitude is None:
        return WeatherSignal(
            status="no_coordinates",
            classification="insufficient_coverage",
            confirms_event=False,
            explanation="Insufficient geographic or temporal coverage: Entity has no geographic coordinates.",
        )

    if (
        abs(entity.latitude) > 90.0
        or abs(entity.longitude) > 180.0
        or (entity.latitude == 0.0 and entity.longitude == 0.0)
    ):
        return WeatherSignal(
            status="no_coordinates",
            classification="insufficient_coverage",
            confirms_event=False,
            explanation="Insufficient geographic or temporal coverage: Invalid coordinate values.",
        )

    # Gate 3: Temporal relevance check
    # Current telemetry (last 24-48h) cannot confirm or disprove an incident older than 48 hours.
    if event.published_at is not None:
        event_time = event.published_at
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - event_time).total_seconds() / 3600.0
        if age_hours > 48.0:
            logger.info(
                f"[WEATHER] event={event.id} published_at={event.published_at} is {age_hours:.1f}h old "
                f"(exceeds 48h observation telemetry window) -> insufficient_coverage"
            )
            return WeatherSignal(
                status="insufficient_coverage",
                classification="insufficient_coverage",
                confirms_event=False,
                explanation="Insufficient geographic or temporal coverage: Event publication date is outside the 48h observation telemetry window.",
            )

    # Gate 4: Fetch actual weather data
    data = await get_recent_weather(entity.latitude, entity.longitude)
    if data is None:
        return WeatherSignal(
            status="unavailable",
            classification="unavailable",
            confirms_event=False,
            explanation="Unavailable: Weather provider service was unreachable or returned no data; corroboration is inconclusive.",
        )

    # Extract precipitation total from hourly data
    hourly_precip = data.get("hourly", {}).get("precipitation", []) or []
    total_precip = sum(p for p in hourly_precip if isinstance(p, (int, float)))

    # Extract wind speed from current data
    current_wind = data.get("current", {}).get("wind_speed_10m")
    if isinstance(current_wind, (int, float)):
        wind_speed = float(current_wind)
    else:
        wind_speed = None

    # Check precipitation threshold
    precip_threshold = thresholds.get("precipitation_mm_threshold", 999.0)
    confirms_precip = total_precip >= precip_threshold

    # Check wind threshold (only for event types that specify it)
    wind_threshold = thresholds.get("wind_kmh_threshold")
    confirms_wind = False
    if wind_threshold is not None and wind_speed is not None:
        confirms_wind = wind_speed >= wind_threshold

    # For flood: only precipitation matters
    # For weather: either precipitation OR wind can confirm
    confirms = confirms_precip or confirms_wind

    logger.info(
        f"[WEATHER] event={event.id} type={event.event_type} "
        f"precip={total_precip:.1f}mm wind={wind_speed}km/h "
        f"confirms={confirms}"
    )

    if not confirms:
        # Check if the flood is described as caused by upstream, river overflow, dam release, surge, or prior rainfall
        text_content = f"{event.headline or ''} {event.summary or ''}".lower()
        is_upstream_or_hydrological = any(
            phrase in text_content
            for phrase in (
                "river overflow",
                "overflowing river",
                "dam release",
                "dam breach",
                "upstream water",
                "upstream rain",
                "upstream runoff",
                "storm surge",
                "tidal surge",
                "runoff",
                "reservoir breach",
                "earlier rainfall",
                "snowmelt",
            )
        )
        if is_upstream_or_hydrological:
            logger.info(
                f"[WEATHER] event={event.id} flood source is hydrological/upstream ({total_precip:.1f}mm local rain) "
                f"-> inconclusive telemetry; classifying as insufficient_coverage to avoid false penalty."
            )
            return WeatherSignal(
                status="insufficient_coverage",
                classification="insufficient_coverage",
                confirms_event=False,
                precipitation_mm_24h=round(total_precip, 2),
                wind_speed_kmh=round(wind_speed, 2) if wind_speed is not None else None,
                explanation=(
                    "Insufficient coverage: Flood reported as river overflow, dam release, or upstream runoff; "
                    "local surface precipitation alone is inconclusive and cannot disprove the event."
                ),
            )

    return WeatherSignal(
        status="checked",
        classification="confirmed" if confirms else "not_supported",
        confirms_event=confirms,
        precipitation_mm_24h=round(total_precip, 2),
        wind_speed_kmh=round(wind_speed, 2) if wind_speed is not None else None,
    )
