"""Tests for weather corroboration service (Part B).

Covers the four testing checkpoints:
1. Mocked weather above threshold → confirms_event=True
2. Mocked weather below threshold → confirms_event=False
3. API failure (None response) → status="unavailable", no crash
4. Non-weather event type → status="not_applicable", no API call
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.models.entity import BusinessEntity, EntityMetadata
from app.models.events import DisruptionEvent
from app.services.weather_service import (
    WeatherSignal,
    check_weather_corroboration,
    EVENT_WEATHER_MAP,
)
from app.services.verification_service import VerificationService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_entity(lat=13.08, lon=80.27) -> BusinessEntity:
    """Create a test entity with coordinates (default: Chennai)."""
    return BusinessEntity(
        name="Test Factory",
        type="factory",
        location="Chennai, India",
        criticality="high",
        latitude=lat,
        longitude=lon,
    )


def _make_event(event_type: str = "flood") -> DisruptionEvent:
    """Create a test disruption event."""
    return DisruptionEvent(
        source_url="https://reuters.com/flood-chennai",
        source_result_id="sr-001",
        headline="Major flooding hits Chennai industrial zone",
        summary="Heavy rains cause flooding in Chennai port area",
        event_type=event_type,
        location_mentioned="Chennai, India",
        severity_raw="high",
        confidence=0.9,
        is_relevant=True,
    )


MOCK_WEATHER_ABOVE_THRESHOLD = {
    "hourly": {
        "precipitation": [5.0, 3.0, 4.0, 2.0, 6.0, 1.0, 0.5, 0.5] + [0.0] * 40,
        # Total = 22.0mm → above flood threshold of 20.0mm
    },
    "current": {
        "wind_speed_10m": 25.0,
    },
}


MOCK_WEATHER_BELOW_THRESHOLD = {
    "hourly": {
        "precipitation": [1.0, 0.5, 0.2, 0.3] + [0.0] * 44,
        # Total = 2.0mm → well below flood threshold of 20.0mm
    },
    "current": {
        "wind_speed_10m": 10.0,
    },
}


# ---------------------------------------------------------------------------
# Test 1: Above threshold → confirms_event=True
# ---------------------------------------------------------------------------


class TestWeatherAboveThreshold:
    @pytest.mark.asyncio
    async def test_flood_above_threshold_confirms(self):
        """Weather data above precipitation threshold → confirms_event=True."""
        entity = _make_entity()
        event = _make_event("flood")

        with patch(
            "app.services.weather_service.get_recent_weather",
            new_callable=AsyncMock,
            return_value=MOCK_WEATHER_ABOVE_THRESHOLD,
        ):
            signal = await check_weather_corroboration(event, entity)

        assert signal.status == "checked"
        assert signal.confirms_event is True
        assert signal.precipitation_mm_24h is not None
        assert signal.precipitation_mm_24h >= 20.0

    @pytest.mark.asyncio
    async def test_weather_event_with_high_wind(self):
        """Weather event with wind above threshold → confirms_event=True."""
        entity = _make_entity()
        event = _make_event("weather")

        mock_data = {
            "hourly": {"precipitation": [1.0] + [0.0] * 47},  # 1.0mm — below threshold
            "current": {"wind_speed_10m": 55.0},  # above 40 km/h threshold
        }

        with patch(
            "app.services.weather_service.get_recent_weather",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            signal = await check_weather_corroboration(event, entity)

        assert signal.status == "checked"
        assert signal.confirms_event is True  # wind alone can confirm for 'weather' type


# ---------------------------------------------------------------------------
# Test 2: Below threshold → confirms_event=False
# ---------------------------------------------------------------------------


class TestWeatherBelowThreshold:
    @pytest.mark.asyncio
    async def test_flood_below_threshold_does_not_confirm(self):
        """Weather data below precipitation threshold → confirms_event=False."""
        entity = _make_entity()
        event = _make_event("flood")

        with patch(
            "app.services.weather_service.get_recent_weather",
            new_callable=AsyncMock,
            return_value=MOCK_WEATHER_BELOW_THRESHOLD,
        ):
            signal = await check_weather_corroboration(event, entity)

        assert signal.status == "checked"
        assert signal.confirms_event is False
        assert signal.precipitation_mm_24h is not None
        assert signal.precipitation_mm_24h < 20.0

    def test_weather_contradiction_reduces_credibility_score(self):
        """Checked weather below threshold reduces credibility for flood/weather events."""
        event = _make_event("flood")
        signal = WeatherSignal(
            status="checked",
            confirms_event=False,
            precipitation_mm_24h=2.0,
            wind_speed_kmh=10.0,
        )

        verifier = VerificationService()
        without_weather = verifier.verify(
            event,
            [],
            override_source_reputation=0.9,
            override_corroboration_count=0,
            override_content_style_score=0.8,
        )
        with_weather = verifier.verify(
            event,
            [],
            override_source_reputation=0.9,
            override_corroboration_count=0,
            override_content_style_score=0.8,
            weather_signal=signal,
        )

        assert with_weather.authenticity_score == without_weather.authenticity_score - 15.0
        assert with_weather.factors["weather_corroboration"] == -15.0


# ---------------------------------------------------------------------------
# Test 3: API failure → status="unavailable", no crash
# ---------------------------------------------------------------------------


class TestWeatherAPIFailure:
    @pytest.mark.asyncio
    async def test_api_returns_none_is_unavailable(self):
        """get_recent_weather returning None → status='unavailable', no crash."""
        entity = _make_entity()
        event = _make_event("flood")

        with patch(
            "app.services.weather_service.get_recent_weather",
            new_callable=AsyncMock,
            return_value=None,
        ):
            signal = await check_weather_corroboration(event, entity)

        assert signal.status == "unavailable"
        assert signal.confirms_event is False
        assert signal.precipitation_mm_24h is None

    @pytest.mark.asyncio
    async def test_missing_coordinates_is_no_coordinates(self):
        """Entity without lat/lon → status='no_coordinates'."""
        entity = BusinessEntity(
            name="No-Coord Factory",
            type="factory",
            location="Unknown",
            criticality="high",
            latitude=None,
            longitude=None,
        )
        event = _make_event("flood")

        # No API call should be made at all
        signal = await check_weather_corroboration(event, entity)

        assert signal.status == "no_coordinates"
        assert signal.confirms_event is False


# ---------------------------------------------------------------------------
# Test 4: Non-weather event → status="not_applicable", no API call
# ---------------------------------------------------------------------------


class TestNonWeatherEventType:
    @pytest.mark.asyncio
    async def test_strike_event_not_applicable(self):
        """Non-weather event type (strike) → status='not_applicable', no API call."""
        entity = _make_entity()
        event = _make_event("strike")

        # Patch the API call to verify it's never called
        with patch(
            "app.services.weather_service.get_recent_weather",
            new_callable=AsyncMock,
        ) as mock_api:
            signal = await check_weather_corroboration(event, entity)
            mock_api.assert_not_called()

        assert signal.status == "not_applicable"
        assert signal.confirms_event is False

    @pytest.mark.asyncio
    async def test_closure_event_not_applicable(self):
        """Non-weather event type (closure) → status='not_applicable'."""
        entity = _make_entity()
        event = _make_event("closure")

        signal = await check_weather_corroboration(event, entity)

        assert signal.status == "not_applicable"
        assert signal.confirms_event is False

    @pytest.mark.asyncio
    async def test_supplier_failure_not_applicable(self):
        """Non-weather event type (supplier_failure) → status='not_applicable'."""
        entity = _make_entity()
        event = _make_event("supplier_failure")

        signal = await check_weather_corroboration(event, entity)

        assert signal.status == "not_applicable"
        assert signal.confirms_event is False


# ---------------------------------------------------------------------------
# WeatherSignal model validation
# ---------------------------------------------------------------------------


class TestWeatherSignalModel:
    def test_checked_signal(self):
        s = WeatherSignal(
            status="checked",
            confirms_event=True,
            precipitation_mm_24h=34.5,
            wind_speed_kmh=25.0,
        )
        assert s.status == "checked"
        assert s.confirms_event is True

    def test_unavailable_signal(self):
        s = WeatherSignal(status="unavailable", confirms_event=False)
        assert s.precipitation_mm_24h is None

    def test_event_weather_map_keys(self):
        """Only flood and weather event types are weather-checkable."""
        assert "flood" in EVENT_WEATHER_MAP
        assert "weather" in EVENT_WEATHER_MAP
        assert "strike" not in EVENT_WEATHER_MAP
        assert "closure" not in EVENT_WEATHER_MAP
        assert "supplier_failure" not in EVENT_WEATHER_MAP
