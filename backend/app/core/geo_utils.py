"""Geospatial utilities: Haversine distance, coordinate validation, and location normalization.
"""

from __future__ import annotations

import math
import re
from typing import Dict, Optional, Tuple


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates the great-circle distance between two points on the Earth surface

    using the Haversine formula.

    Parameters
    ----------
    lat1, lon1: Coordinates of point 1 in decimal degrees.
    lat2, lon2: Coordinates of point 2 in decimal degrees.

    Returns
    -------
    float: Distance in kilometers, rounded to 2 decimal places.
    """
    # Earth radius in kilometers
    R = 6371.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    # Clamp to avoid floating point precision issues outside [-1, 1]
    a = min(1.0, max(0.0, a))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    distance = R * c
    return round(distance, 2)


# Common countries and their aliases
KNOWN_COUNTRIES = {
    "india": "India",
    "netherlands": "Netherlands",
    "the netherlands": "Netherlands",
    "united states": "United States",
    "usa": "United States",
    "us": "United States",
    "germany": "Germany",
    "china": "China",
    "japan": "Japan",
    "taiwan": "Taiwan",
    "south korea": "South Korea",
    "korea": "South Korea",
    "singapore": "Singapore",
    "united kingdom": "United Kingdom",
    "uk": "United Kingdom",
    "vietnam": "Vietnam",
    "malaysia": "Malaysia",
    "brazil": "Brazil",
    "canada": "Canada",
    "mexico": "Mexico",
    "belgium": "Belgium",
    "chile": "Chile",
    "egypt": "Egypt",
    "bangladesh": "Bangladesh",
    "slovakia": "Slovakia",
    "france": "France",
    "italy": "Italy",
}

# Known Indian states and regional entities for disambiguation
KNOWN_INDIAN_STATES = {
    "gujarat": "Gujarat",
    "maharashtra": "Maharashtra",
    "karnataka": "Karnataka",
    "tamil nadu": "Tamil Nadu",
    "telangana": "Telangana",
    "andhra pradesh": "Andhra Pradesh",
    "delhi": "Delhi",
    "rajasthan": "Rajasthan",
    "haryana": "Haryana",
    "west bengal": "West Bengal",
    "uttar pradesh": "Uttar Pradesh",
}

# Known cities to state/country mapping for immediate offline resolution
KNOWN_CITY_HIERARCHY = {
    "surat": {"city": "Surat", "state": "Gujarat", "country": "India", "lat": 21.17024, "lon": 72.83106},
    "ahmedabad": {"city": "Ahmedabad", "state": "Gujarat", "country": "India", "lat": 23.0225, "lon": 72.5714},
    "mumbai": {"city": "Mumbai", "state": "Maharashtra", "country": "India", "lat": 19.0760, "lon": 72.8777},
    "rotterdam": {"city": "Rotterdam", "state": "South Holland", "country": "Netherlands", "lat": 51.9244, "lon": 4.4777},
    "amsterdam": {"city": "Amsterdam", "state": "North Holland", "country": "Netherlands", "lat": 52.3676, "lon": 4.9041},
    "shanghai": {"city": "Shanghai", "state": "Shanghai", "country": "China", "lat": 31.2304, "lon": 121.4737},
    "los angeles": {"city": "Los Angeles", "state": "California", "country": "United States", "lat": 34.0522, "lon": -118.2437},
    "singapore": {"city": "Singapore", "state": "Singapore", "country": "Singapore", "lat": 1.3521, "lon": 103.8198},
    "shenzhen": {"city": "Shenzhen", "state": "Guangdong", "country": "China", "lat": 22.5431, "lon": 114.0579},
    "hamburg": {"city": "Hamburg", "state": "Hamburg", "country": "Germany", "lat": 53.5511, "lon": 9.9937},
    "houston": {"city": "Houston", "state": "Texas", "country": "United States", "lat": 29.7604, "lon": -95.3698},
    "chicago": {"city": "Chicago", "state": "Illinois", "country": "United States", "lat": 41.8781, "lon": -87.6298},
    "chennai": {"city": "Chennai", "state": "Tamil Nadu", "country": "India", "lat": 13.0827, "lon": 80.2707},
    "austin": {"city": "Austin", "state": "Texas", "country": "United States", "lat": 30.2672, "lon": -97.7431},
    "munich": {"city": "Munich", "state": "Bavaria", "country": "Germany", "lat": 48.1351, "lon": 11.5820},
    "antwerp": {"city": "Antwerp", "state": "Flanders", "country": "Belgium", "lat": 51.2194, "lon": 4.4025},
    "dresden": {"city": "Dresden", "state": "Saxony", "country": "Germany", "lat": 51.0504, "lon": 13.7373},
    "tokyo": {"city": "Tokyo", "state": "Tokyo", "country": "Japan", "lat": 35.6762, "lon": 139.6503},
    "bangkok": {"city": "Bangkok", "state": "Bangkok", "country": "Thailand", "lat": 13.7563, "lon": 100.5018},
    "hsinchu": {"city": "Hsinchu", "state": "Hsinchu", "country": "Taiwan", "lat": 24.8138, "lon": 120.9675},
    "berlin": {"city": "Berlin", "state": "Berlin", "country": "Germany", "lat": 52.5200, "lon": 13.4050},
    "detroit": {"city": "Detroit", "state": "Michigan", "country": "United States", "lat": 42.3314, "lon": -83.0458},
    "sendai": {"city": "Sendai", "state": "Miyagi", "country": "Japan", "lat": 38.2682, "lon": 140.8694},
    "portland": {"city": "Portland", "state": "Oregon", "country": "United States", "lat": 45.5152, "lon": -122.6784},
    "santiago": {"city": "Santiago", "state": "Santiago", "country": "Chile", "lat": -33.4489, "lon": -70.6693},
    "suez": {"city": "Suez", "state": "Suez", "country": "Egypt", "lat": 29.9737, "lon": 32.5599},
    "dhaka": {"city": "Dhaka", "state": "Dhaka", "country": "Bangladesh", "lat": 23.8103, "lon": 90.4125},
    "bratislava": {"city": "Bratislava", "state": "Bratislava", "country": "Slovakia", "lat": 48.1486, "lon": 17.1077},
    "san jose": {"city": "San Jose", "state": "California", "country": "United States", "lat": 37.3382, "lon": -121.8863},
    "paris": {"city": "Paris", "state": "Ile-de-France", "country": "France", "lat": 48.8566, "lon": 2.3522},
    "chongqing": {"city": "Chongqing", "state": "Chongqing", "country": "China", "lat": 29.4316, "lon": 106.9123},
    "osaka": {"city": "Osaka", "state": "Osaka", "country": "Japan", "lat": 34.6937, "lon": 135.5023},
    "felixstowe": {"city": "Felixstowe", "state": "Suffolk", "country": "United Kingdom", "lat": 51.9586, "lon": 1.3511},
    "milan": {"city": "Milan", "state": "Lombardy", "country": "Italy", "lat": 45.4642, "lon": 9.1900},
}


def normalize_location_string(raw: str) -> Dict[str, Optional[str]]:
    """Normalizes place strings into standard administrative components:

    place_name, city, state, country.

    Examples:
    - "Surat, Gujarat, India" -> city="Surat", state="Gujarat", country="India"
    - "ABC Industrial Area, Surat" -> name="ABC Industrial Area", city="Surat", state="Gujarat", country="India"
    - "Rotterdam Logistics Port, Netherlands" -> name="Rotterdam Logistics Port", city="Rotterdam", country="Netherlands"
    """
    if not raw or not raw.strip():
        return {
            "name": None,
            "city": None,
            "district": None,
            "state": None,
            "country": None,
            "normalized_query": "",
        }

    text = raw.strip()
    # Normalize separators
    parts = [p.strip() for p in re.split(r"[,;|/]+", text) if p.strip()]

    resolved_country: Optional[str] = None
    resolved_state: Optional[str] = None
    resolved_city: Optional[str] = None
    resolved_name: Optional[str] = None

    # Check parts from end to start for country, state, city
    remaining_parts = []
    for part in parts:
        part_clean = re.sub(r"[^\w\s-]", "", part).strip().lower()
        if not part_clean:
            continue

        if part_clean in KNOWN_COUNTRIES:
            resolved_country = KNOWN_COUNTRIES[part_clean]
        elif part_clean in KNOWN_INDIAN_STATES:
            resolved_state = KNOWN_INDIAN_STATES[part_clean]
            if not resolved_country:
                resolved_country = "India"
        else:
            remaining_parts.append(part.strip())

    # Look through remaining parts or full text for known cities
    full_lower = text.lower()
    for city_key, info in KNOWN_CITY_HIERARCHY.items():
        # Match whole word
        if re.search(r"\b" + re.escape(city_key) + r"\b", full_lower):
            if not resolved_city:
                resolved_city = info["city"]
            if not resolved_state and info.get("state"):
                resolved_state = info["state"]
            if not resolved_country and info.get("country"):
                resolved_country = info["country"]
            break

    # If remaining parts exist, the first one is often the specific facility/area name
    if remaining_parts:
        if resolved_city and remaining_parts[0].lower() == resolved_city.lower():
            if len(remaining_parts) > 1:
                resolved_name = remaining_parts[1]
        else:
            resolved_name = remaining_parts[0]
            if not resolved_city and len(remaining_parts) > 1:
                resolved_city = remaining_parts[1]

    # Clean redundant name if it just equals the city
    if resolved_name and resolved_city and resolved_name.lower() == resolved_city.lower():
        resolved_name = None

    # Build canonical normalized query for caching
    query_parts = []
    if resolved_name:
        query_parts.append(resolved_name)
    if resolved_city:
        query_parts.append(resolved_city)
    if resolved_state and resolved_state != resolved_city:
        query_parts.append(resolved_state)
    if resolved_country:
        query_parts.append(resolved_country)

    normalized_query = ", ".join(query_parts) if query_parts else text

    return {
        "name": resolved_name,
        "city": resolved_city,
        "district": None,
        "state": resolved_state,
        "country": resolved_country,
        "normalized_query": normalized_query,
    }
