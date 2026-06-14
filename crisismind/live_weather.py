"""Fetch live weather and reverse-geocode coordinates using free public APIs.

Open-Meteo — https://open-meteo.com/ (no API key, free, open-source)
Nominatim  — https://nominatim.openstreetmap.org/ (free, no key)

Both use stdlib ``urllib`` so no extra dependencies are needed.
"""

from __future__ import annotations

import json
import math
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


_OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
_AQI_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
_TIMEOUT = 8  # seconds


def fetch_live_weather(lat: float, lon: float) -> dict[str, Any]:
    """Return current weather conditions for *lat*/*lon*.

    Falls back to safe defaults if the API is unreachable.
    """
    params = urllib.parse.urlencode(
        {
            "latitude": lat,
            "longitude": lon,
            "current": ",".join(
                [
                    "temperature_2m",
                    "wind_speed_10m",
                    "wind_gusts_10m",
                    "rain",
                    "relative_humidity_2m",
                    "apparent_temperature",
                    "precipitation",
                ]
            ),
            "timezone": "auto",
        }
    )
    try:
        with urllib.request.urlopen(f"{_OPEN_METEO_URL}?{params}", timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return _weather_defaults()

    current = data.get("current", {})
    rain_mm = current.get("rain", 0) or 0
    precipitation = current.get("precipitation", 0) or 0
    rainfall = max(rain_mm, precipitation)
    wind_kph = current.get("wind_speed_10m", 0) or 0
    wind_gusts = current.get("wind_gusts_10m", 0) or 0
    temperature = current.get("temperature_2m", 25) or 25

    # Fetch AQI separately (different Open-Meteo endpoint)
    aqi = _fetch_aqi(lat, lon)

    # Estimate river level from rainfall (rough heuristic — real sensor data
    # would come from a proper hydrology API, but this gives a reasonable
    # approximation for the analysis engine).
    river_level = round(1.0 + (rainfall / 60) * 3.0, 1)

    return {
        "rainfall_mm": round(rainfall),
        "wind_kph": round(wind_kph),
        "wind_gusts_kph": round(wind_gusts),
        "temperature_c": round(temperature),
        "river_level": min(river_level, 5.0),
        "air_quality_index": aqi,
        "humidity_percent": round(current.get("relative_humidity_2m", 50) or 50),
        "apparent_temperature_c": round(current.get("apparent_temperature", temperature) or temperature),
    }


def _fetch_aqi(lat: float, lon: float) -> int:
    """Fetch European AQI from Open-Meteo Air Quality API."""
    params = urllib.parse.urlencode(
        {
            "latitude": lat,
            "longitude": lon,
            "current": "european_aqi",
        }
    )
    try:
        with urllib.request.urlopen(f"{_AQI_URL}?{params}", timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return int(data.get("current", {}).get("european_aqi", 50) or 50)
    except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError):
        return 50


def reverse_geocode(lat: float, lon: float) -> str:
    """Return a human-readable location name for *lat*/*lon*.

    Falls back to a coordinate string if the API is unreachable.
    """
    params = urllib.parse.urlencode(
        {
            "lat": lat,
            "lon": lon,
            "format": "json",
            "zoom": 10,
            "addressdetails": 1,
        }
    )
    headers = {"User-Agent": "DisasterDetectionAI/0.2 (disaster-research-project)"}
    req = urllib.request.Request(f"{_NOMINATIM_URL}?{params}", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return f"{lat:.4f}°N, {lon:.4f}°E"

    address = data.get("address", {})
    city = (
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("county")
        or address.get("state_district")
        or ""
    )
    state = address.get("state", "")
    if city and state:
        return f"{city}, {state}"
    if city:
        return city
    if state:
        return state
    return data.get("display_name", f"{lat:.4f}°N, {lon:.4f}°E")



def forward_geocode(query: str) -> dict[str, Any]:
    """Convert a place name into lat/lon coordinates using Nominatim.

    Returns a dict with ``lat``, ``lon``, and ``display_name`` keys.
    Falls back to a zero-coordinate result if the API is unreachable or
    finds no matches.
    """
    _NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
    params = urllib.parse.urlencode(
        {
            "q": query,
            "format": "json",
            "limit": 1,
            "addressdetails": 1,
        }
    )
    headers = {"User-Agent": "DisasterDetectionAI/0.2 (disaster-research-project)"}
    req = urllib.request.Request(f"{_NOMINATIM_SEARCH_URL}?{params}", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            results = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return {"lat": 0.0, "lon": 0.0, "display_name": query, "found": False}

    if not results:
        return {"lat": 0.0, "lon": 0.0, "display_name": query, "found": False}

    hit = results[0]
    return {
        "lat": float(hit.get("lat", 0)),
        "lon": float(hit.get("lon", 0)),
        "display_name": hit.get("display_name", query),
        "found": True,
    }


def auto_detect_disaster_type(weather: dict[str, Any]) -> str:
    """Guess the most likely disaster type from live weather readings."""
    rainfall = weather.get("rainfall_mm", 0)
    wind = weather.get("wind_kph", 0)
    temperature = weather.get("temperature_c", 25)

    # Simple priority: cyclone winds → flood rains → heatwave
    if wind >= 80:
        return "cyclone"
    if rainfall >= 50:
        return "flood"
    if temperature >= 38:
        return "heatwave"
    # Default: pick the dominant signal
    wind_score = wind / 180
    rain_score = rainfall / 250
    heat_score = max(temperature - 30, 0) / 18
    scores = {"flood": rain_score, "cyclone": wind_score, "heatwave": heat_score}
    return max(scores, key=scores.get)  # type: ignore[arg-type]


def estimate_signals(weather: dict[str, Any]) -> dict[str, int]:
    """Estimate social/news signal levels and population parameters.

    In a production system these would come from real social-media sentiment
    APIs and census databases.  Here we derive plausible values from the
    weather severity so the analysis engine has something meaningful to work
    with.
    """
    rainfall = weather.get("rainfall_mm", 0)
    wind = weather.get("wind_kph", 0)
    temperature = weather.get("temperature_c", 25)
    aqi = weather.get("air_quality_index", 50)

    # Composite severity 0-1
    severity = min(
        (rainfall / 250 + wind / 180 + max(temperature - 30, 0) / 18 + aqi / 300) / 4,
        1.0,
    )

    social = min(round(30 + severity * 70), 100)
    news = min(round(20 + severity * 65), 100)
    density = min(round(40 + severity * 40), 100)
    vulnerable = min(round(12 + severity * 25), 50)

    return {
        "social_signal_level": social,
        "news_signal_level": news,
        "population_density": density,
        "vulnerable_population_percent": vulnerable,
    }


def _weather_defaults() -> dict[str, Any]:
    """Safe fallback values when the API is unreachable."""
    return {
        "rainfall_mm": 0,
        "wind_kph": 0,
        "wind_gusts_kph": 0,
        "temperature_c": 25,
        "river_level": 1.0,
        "air_quality_index": 50,
        "humidity_percent": 50,
        "apparent_temperature_c": 25,
    }
