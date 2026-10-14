"""Geocoding Service with Provider Abstraction, Caching, and Fallback Resilience.

Adheres to:
- OpenStreetMap Nominatim usage policies (User-Agent header, rate limit respect).
- Normalized query caching to prevent redundant API queries.
- Safe failure principle: if coordinates cannot be determined, returns unresolved EventLocation
  with latitude=None, longitude=None, confidence=0.0. Never invents coordinates.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, Optional
import httpx

from app.core.geo_utils import KNOWN_CITY_HIERARCHY, normalize_location_string
from app.models.geo import EventLocation

logger = logging.getLogger("business_disruption")


class GeocoderProvider(ABC):
    """Abstract interface for external geocoding providers."""

    @abstractmethod
    def geocode(self, query: str) -> Optional[EventLocation]:
        """Geocodes a place name/address into an EventLocation."""
        pass

    @abstractmethod
    def reverse_geocode(self, lat: float, lon: float) -> Optional[Dict[str, str]]:
        """Reverse geocodes coordinates into administrative address components."""
        pass


class NominatimGeocoderProvider(GeocoderProvider):
    """OpenStreetMap Nominatim Geocoding Provider.

    Respects OSM Nominatim Usage Policy:
    - User-Agent header identified.
    - 1-second polite rate limit.
    """

    BASE_URL = "https://nominatim.openstreetmap.org/search"
    REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
    USER_AGENT = "BusinessDisruptionMonitor/1.0 (Autonomous Business Disruption Platform)"

    def __init__(self, timeout_sec: float = 3.0):
        self.timeout_sec = timeout_sec
        self._last_call_time = 0.0

    def _rate_limit(self):
        elapsed = time.time() - self._last_call_time
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        self._last_call_time = time.time()

    def geocode(self, query: str) -> Optional[EventLocation]:
        if not query or not query.strip():
            return None

        # Check known dictionary first to avoid hitting external OSM Nominatim
        norm = normalize_location_string(query)
        city_key = (norm.get("city") or "").lower()
        if city_key in KNOWN_CITY_HIERARCHY:
            info = KNOWN_CITY_HIERARCHY[city_key]
            return EventLocation(
                raw_text=query,
                name=norm.get("name"),
                city=info["city"],
                state=info.get("state"),
                country=info.get("country"),
                latitude=info["lat"],
                longitude=info["lon"],
                confidence=0.95,
                source="nominatim_cached_authority",
                is_resolved=True,
            )

        try:
            self._rate_limit()
            headers = {"User-Agent": self.USER_AGENT}
            params = {
                "q": query,
                "format": "json",
                "addressdetails": "1",
                "limit": "1",
            }
            with httpx.Client(timeout=self.timeout_sec) as client:
                resp = client.get(self.BASE_URL, params=params, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    if data and len(data) > 0:
                        top = data[0]
                        addr = top.get("address", {})
                        city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("county")
                        state = addr.get("state")
                        country = addr.get("country")
                        lat = float(top["lat"])
                        lon = float(top["lon"])

                        return EventLocation(
                            raw_text=query,
                            name=norm.get("name") or top.get("name"),
                            city=city,
                            district=addr.get("district"),
                            state=state,
                            country=country,
                            postal_code=addr.get("postcode"),
                            latitude=lat,
                            longitude=lon,
                            confidence=0.90,
                            source="nominatim",
                            is_resolved=True,
                        )
                elif resp.status_code == 429:
                    logger.warning("Nominatim rate limited (429). Falling back safely.")
                else:
                    logger.warning(f"Nominatim returned HTTP {resp.status_code} for query '{query}'")
        except Exception as exc:
            logger.warning(f"Nominatim geocode failed for query '{query}': {exc}")

        return None

    def reverse_geocode(self, lat: float, lon: float) -> Optional[Dict[str, str]]:
        try:
            self._rate_limit()
            headers = {"User-Agent": self.USER_AGENT}
            params = {
                "lat": lat,
                "lon": lon,
                "format": "json",
            }
            with httpx.Client(timeout=self.timeout_sec) as client:
                resp = client.get(self.REVERSE_URL, params=params, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    addr = data.get("address", {})
                    return {
                        "city": addr.get("city") or addr.get("town") or addr.get("village"),
                        "state": addr.get("state"),
                        "country": addr.get("country"),
                    }
        except Exception as exc:
            logger.warning(f"Nominatim reverse geocode failed for {lat}, {lon}: {exc}")
        return None


class GeocodingService:
    """Enterprise Geocoding Service orchestrating normalization, caching, and provider resolution.
    """

    def __init__(self, provider: Optional[GeocoderProvider] = None):
        self.provider = provider or NominatimGeocoderProvider()
        self._cache: Dict[str, EventLocation] = {}
        self._init_cache()

    def _init_cache(self):
        """Pre-seeds cache with common verified enterprise locations."""
        for key, info in KNOWN_CITY_HIERARCHY.items():
            loc = EventLocation(
                raw_text=info["city"],
                name=None,
                city=info["city"],
                state=info.get("state"),
                country=info.get("country"),
                latitude=info["lat"],
                longitude=info["lon"],
                confidence=0.98,
                source="preconfigured_authority",
                is_resolved=True,
            )
            self._cache[key] = loc
            self._cache[info["city"].lower()] = loc
            self._cache[f"{info['city'].lower()}, {info.get('country', '').lower()}"] = loc

    def resolve_place(self, text: str) -> EventLocation:
        """Resolves a raw location string into a structured EventLocation.

        Never invents coordinates. If resolution fails, returns unresolved model.
        """
        if not text or not text.strip():
            return EventLocation(
                raw_text="",
                confidence=0.0,
                source="empty_input",
                is_resolved=False,
            )

        norm = normalize_location_string(text)
        cache_key = norm.get("normalized_query", text).lower().strip()

        # Cache check
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            # Create a copy with the original raw text preserved
            res = cached.model_copy()
            res.raw_text = text
            if norm.get("name"):
                res.name = norm["name"]
            return res

        # Check by city name alone in cache
        if norm.get("city") and norm["city"].lower() in self._cache:
            cached = self._cache[norm["city"].lower()]
            res = cached.model_copy()
            res.raw_text = text
            res.name = norm.get("name")
            return res

        # Query provider safely
        try:
            resolved = self.provider.geocode(text)
            if resolved and resolved.is_resolved:
                self._cache[cache_key] = resolved
                return resolved

            # Try normalized query if distinct from raw text
            if norm.get("normalized_query") and norm["normalized_query"] != text:
                resolved_norm = self.provider.geocode(norm["normalized_query"])
                if resolved_norm and resolved_norm.is_resolved:
                    self._cache[cache_key] = resolved_norm
                    return resolved_norm
        except Exception as exc:
            logger.warning(f"Geocoding provider failed for '{text}': {exc}. Failing safely to unresolved.")

        # Failure-safe fallback: mark unresolved, zero coordinates
        logger.info(f"Geocoding could not resolve location '{text}'. Marked UNRESOLVED.")
        unresolved = EventLocation(
            raw_text=text,
            name=norm.get("name"),
            city=norm.get("city"),
            state=norm.get("state"),
            country=norm.get("country"),
            latitude=None,
            longitude=None,
            confidence=0.15 if norm.get("city") else 0.0,
            source="unresolved",
            is_resolved=False,
        )
        self._cache[cache_key] = unresolved
        return unresolved


# Module instance singleton
_geocoding_service_instance: Optional[GeocodingService] = None


def get_geocoding_service() -> GeocodingService:
    global _geocoding_service_instance
    if _geocoding_service_instance is None:
        _geocoding_service_instance = GeocodingService()
    return _geocoding_service_instance
