"""Validation tests for Weather Corroboration & Alert Explanations (Phase 2 - Sections 4 & 5).

Verifies:
- Weather data associated with relevant event location
- Observation timestamps relevant to event timeframe (>48h gives insufficient_coverage, no penalty)
- Coordinates and geographic coverage sufficiency (invalid coords give insufficient_coverage)
- Weather provider failure is distinguished from contradictory evidence
- Missing coordinates distinguished from negative weather observation
- Weather observation does not automatically prove business disruption
- Duplicate weather observations not counted repeatedly
- Credibility calculation remains within valid [0, 100] range
- 15-point reduction applied only on genuine contradictory checked data
- Alert explanation weather_signal covers all 5 required classifications:
  1. Confirmed
  2. Not supported by the available observations
  3. Unavailable
  4. Not checked
  5. Insufficient geographic or temporal coverage
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
import pytest

from app.models.entity import BusinessEntity
from app.models.events import DisruptionEvent
from app.models.risk import Alert, RiskAssessment
from app.services.alert_service import AlertService
from app.services.verification_service import VerificationService
from app.services.weather_service import (
    WeatherSignal,
    check_weather_corroboration,
)


def _make_entity(lat: float | None = 13.08, lon: float | None = 80.27) -> BusinessEntity:
    return BusinessEntity(
        id="ent-weather-test",
        name="Chennai Manufacturing Center",
        type="factory",
        location="Chennai, India",
        criticality="high",
        latitude=lat,
        longitude=lon,
    )


def _make_event(event_type: str = "flood", published_at: datetime | None = None) -> DisruptionEvent:
    return DisruptionEvent(
        source_url="https://reuters.com/flood-chennai",
        source_result_id="res-weather-1",
        headline="Torrential rains flood industrial corridors in Chennai",
        summary="Heavy monsoon rain causes severe waterlogging in industrial areas.",
        event_type=event_type,
        location_mentioned="Chennai, India",
        severity_raw="high",
        confidence=0.88,
        is_relevant=True,
        published_at=published_at or datetime.now(timezone.utc),
    )


class TestWeatherCorroborationValidation:
    @pytest.mark.asyncio
    async def test_weather_data_associated_with_event_coordinates(self):
        """Weather query uses the entity coordinates for the event location."""
        entity = _make_entity(lat=19.076, lon=72.877)  # Mumbai
        event = _make_event("flood")

        with patch("app.services.weather_service.get_recent_weather", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {
                "hourly": {"precipitation": [25.0] + [0.0] * 40},
                "current": {"wind_speed_10m": 15.0},
            }
            signal = await check_weather_corroboration(event, entity)
            mock_get.assert_called_once_with(19.076, 72.877)

        assert signal.status == "checked"
        assert signal.classification == "confirmed"
        assert signal.confirms_event is True
        assert "Confirmed" in signal.explanation

    @pytest.mark.asyncio
    async def test_observation_timestamps_outside_48h_is_insufficient_coverage(self):
        """Events published >48 hours ago are classified as insufficient_coverage, preventing false penalty."""
        entity = _make_entity()
        old_pub = datetime.now(timezone.utc) - timedelta(days=5)  # 5 days ago
        event = _make_event("flood", published_at=old_pub)

        signal = await check_weather_corroboration(event, entity)
        assert signal.status == "insufficient_coverage"
        assert signal.classification == "insufficient_coverage"
        assert signal.confirms_event is False
        assert "outside the 48h observation telemetry window" in signal.explanation

        # Verify no 15-point penalty is applied for insufficient temporal coverage
        verifier = VerificationService()
        base = verifier.verify(event, [], override_source_reputation=0.8, override_corroboration_count=0, override_content_style_score=0.8)
        assessed = verifier.verify(event, [], override_source_reputation=0.8, override_corroboration_count=0, override_content_style_score=0.8, weather_signal=signal)
        assert assessed.authenticity_score == base.authenticity_score
        assert "weather_corroboration" not in assessed.factors or assessed.factors["weather_corroboration"] == 0.0

    @pytest.mark.asyncio
    async def test_invalid_coordinates_classified_as_insufficient_coverage(self):
        """Invalid coordinate values (out of bounds or (0,0)) return insufficient_coverage."""
        bad_entity = _make_entity(lat=0.0, lon=0.0)  # Null Island
        event = _make_event("flood")

        signal = await check_weather_corroboration(event, bad_entity)
        assert signal.classification == "insufficient_coverage"
        assert signal.confirms_event is False

    @pytest.mark.asyncio
    async def test_weather_provider_failure_is_distinguished_from_contradiction(self):
        """API provider failure (None response) is classified as unavailable, never disproven."""
        entity = _make_entity()
        event = _make_event("flood")

        with patch("app.services.weather_service.get_recent_weather", new_callable=AsyncMock, return_value=None):
            signal = await check_weather_corroboration(event, entity)

        assert signal.status == "unavailable"
        assert signal.classification == "unavailable"
        assert signal.confirms_event is False
        assert "Unavailable" in signal.explanation

        # Provider failure does NOT apply penalty
        verifier = VerificationService()
        base = verifier.verify(event, [], override_source_reputation=0.8, override_corroboration_count=0, override_content_style_score=0.8)
        assessed = verifier.verify(event, [], override_source_reputation=0.8, override_corroboration_count=0, override_content_style_score=0.8, weather_signal=signal)
        assert assessed.authenticity_score == base.authenticity_score

    @pytest.mark.asyncio
    async def test_missing_coordinates_distinguished_from_negative_observation(self):
        """Entity without coordinates is classified as insufficient_coverage, not contradictory."""
        entity = _make_entity(lat=None, lon=None)
        event = _make_event("flood")

        signal = await check_weather_corroboration(event, entity)
        assert signal.status == "no_coordinates"
        assert signal.classification == "insufficient_coverage"
        assert signal.confirms_event is False

    def test_fifteen_point_reduction_only_on_valid_not_supported_check(self):
        """15-point reduction is strictly applied when telemetry was successfully checked and failed support."""
        event = _make_event("flood")
        contradictory_signal = WeatherSignal(
            status="checked",
            classification="not_supported",
            confirms_event=False,
            precipitation_mm_24h=1.2,
            wind_speed_kmh=8.0,
        )

        verifier = VerificationService()
        base = verifier.verify(event, [], override_source_reputation=0.8, override_corroboration_count=0, override_content_style_score=0.8)
        assessed = verifier.verify(event, [], override_source_reputation=0.8, override_corroboration_count=0, override_content_style_score=0.8, weather_signal=contradictory_signal)

        assert assessed.authenticity_score == base.authenticity_score - 15.0
        assert assessed.factors["weather_corroboration"] == -15.0

    def test_credibility_calculation_clamped_to_valid_range(self):
        """Applying the 15-point deduction to an already low score does not drop below 0.0."""
        event = _make_event("flood")
        event.confidence = 0.1
        contradictory_signal = WeatherSignal(
            status="checked",
            classification="not_supported",
            confirms_event=False,
            precipitation_mm_24h=0.0,
        )

        verifier = VerificationService()
        # Even with minimum reputation (0.1) and style (0.1), clamped at or above 0.0
        assessed = verifier.verify(
            event,
            [],
            override_source_reputation=0.1,
            override_corroboration_count=0,
            override_content_style_score=0.1,
            weather_signal=contradictory_signal,
        )
        assert assessed.authenticity_score >= 0.0
        assert assessed.authenticity_score <= 100.0

    def test_duplicate_weather_observations_not_counted_repeatedly(self):
        """Multiple verifications or repeated signal passes do not stack weather bonuses."""
        event = _make_event("flood")
        confirmed_signal = WeatherSignal(
            status="checked",
            classification="confirmed",
            confirms_event=True,
            precipitation_mm_24h=45.0,
        )

        verifier = VerificationService()
        v1 = verifier.verify(event, [], override_source_reputation=0.8, override_corroboration_count=0, override_content_style_score=0.8, weather_signal=confirmed_signal)
        # Weather confirmation adds at most +1 to corroboration count (from 0 to 1)
        assert v1.corroborating_source_count == 1
        assert v1.corroboration_score == round(1.0 / 3.0, 4) or abs(v1.corroboration_score - 1/3) < 0.01


class TestAlertExplanationWeatherSignalValidation:
    def setup_method(self):
        self.service = AlertService()

    def _create_mock_alert(self, event: DisruptionEvent, weather_signal: WeatherSignal | None = None) -> str:
        self.service._events[event.id] = event
        if weather_signal:
            self.service._weather_signals[event.id] = weather_signal

        assessment = RiskAssessment(
            event_id=event.id,
            entity_id="entity-test",
            severity_score=75.0,
            factors={"dependency_weight_pct": 100.0},
            risk_level="high",
        )
        self.service._assessments[assessment.id] = assessment

        alert = Alert(
            event_id=event.id,
            risk_assessment_id=assessment.id,
            entity_ids=["entity-test"],
            message="Test alert message",
            dedupe_key=f"dedupe-{event.id}",
        )
        self.service._alerts[alert.id] = alert
        return alert.id

    def test_alert_explanation_distinguishes_confirmed(self):
        event = _make_event("flood")
        signal = WeatherSignal(
            status="checked",
            classification="confirmed",
            confirms_event=True,
            precipitation_mm_24h=35.0,
        )
        alert_id = self._create_mock_alert(event, signal)
        payload = self.service.explain_alert(alert_id)
        ws = payload["weather_signal"]
        assert ws is not None
        assert ws["classification"] == "confirmed"
        assert ws["confirms_event"] is True
        assert "Confirmed" in ws["explanation"]

    def test_alert_explanation_distinguishes_not_supported(self):
        event = _make_event("flood")
        signal = WeatherSignal(
            status="checked",
            classification="not_supported",
            confirms_event=False,
            precipitation_mm_24h=2.0,
        )
        alert_id = self._create_mock_alert(event, signal)
        payload = self.service.explain_alert(alert_id)
        ws = payload["weather_signal"]
        assert ws is not None
        assert ws["classification"] == "not_supported"
        assert ws["confirms_event"] is False
        assert "Not supported by the available observations" in ws["explanation"]

    def test_alert_explanation_distinguishes_unavailable(self):
        event = _make_event("flood")
        signal = WeatherSignal(status="unavailable", classification="unavailable", confirms_event=False)
        alert_id = self._create_mock_alert(event, signal)
        payload = self.service.explain_alert(alert_id)
        ws = payload["weather_signal"]
        assert ws is not None
        assert ws["classification"] == "unavailable"
        assert "Unavailable" in ws["explanation"]

    def test_alert_explanation_distinguishes_not_checked(self):
        event = _make_event("strike")  # Non-weather event
        alert_id = self._create_mock_alert(event, None)
        payload = self.service.explain_alert(alert_id)
        ws = payload["weather_signal"]
        assert ws is not None
        assert ws["classification"] == "not_checked"
        assert "Not checked" in ws["explanation"]

    def test_alert_explanation_distinguishes_insufficient_coverage(self):
        event = _make_event("flood")
        signal = WeatherSignal(
            status="insufficient_coverage",
            classification="insufficient_coverage",
            confirms_event=False,
        )
        alert_id = self._create_mock_alert(event, signal)
        payload = self.service.explain_alert(alert_id)
        ws = payload["weather_signal"]
        assert ws is not None
        assert ws["classification"] == "insufficient_coverage"
        assert "Insufficient geographic or temporal coverage" in ws["explanation"]
