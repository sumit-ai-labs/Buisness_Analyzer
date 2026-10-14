"""Weather Client — fetches real-time weather data from Open-Meteo.

Open-Meteo is free, requires no API key, and returns hourly precipitation
and current wind speed data. This matches the zero-auth pattern established
with OpenStreetMap/Nominatim.

Failure policy: ``get_recent_weather`` never raises — it returns None on any
failure and logs a warning.
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger("business_disruption")

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


async def get_recent_weather(lat: float, lon: float) -> dict | None:
    """Return last-24h precipitation and current wind speed for a coordinate.

    Parameters
    ----------
    lat, lon:
        WGS-84 coordinates of the location to query.

    Returns
    -------
    dict — parsed Open-Meteo JSON response, or None on any failure.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "precipitation",
        "current": "wind_speed_10m",
        "past_days": 1,
        "forecast_days": 1,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(OPEN_METEO_URL, params=params)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.warning(f"Weather lookup failed for ({lat},{lon}): {e}")
        return None
