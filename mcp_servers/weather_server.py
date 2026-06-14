from __future__ import annotations

import sys
from pathlib import Path

# Allow importing the live_weather module from the crisismind package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "crisismind"))

from common import SimpleMCPServer, ToolDefinition
from live_weather import fetch_live_weather


def weather_snapshot(arguments: dict[str, object]) -> dict[str, object]:
    request = arguments.get("request", {})
    if not isinstance(request, dict):
        raise ValueError("request must be an object.")
    rainfall = int(request.get("rainfall_mm", 0))
    wind = int(request.get("wind_kph", 0))
    temperature = int(request.get("temperature_c", 0))
    river_level = float(request.get("river_level", 0))
    aqi = int(request.get("air_quality_index", 0))
    return {
        "rainfall_mm": rainfall,
        "wind_kph": wind,
        "temperature_c": temperature,
        "river_level": river_level,
        "aqi": aqi,
        "alert_band": _alert_band(rainfall=rainfall, wind=wind, temperature=temperature, river_level=river_level),
    }


def _alert_band(rainfall: int, wind: int, temperature: int, river_level: float) -> str:
    if rainfall >= 180 or wind >= 120 or temperature >= 43 or river_level >= 4.0:
        return "high"
    if rainfall >= 120 or wind >= 80 or temperature >= 38 or river_level >= 3.0:
        return "elevated"
    return "monitor"


def live_snapshot(arguments: dict[str, object]) -> dict[str, object]:
    """Fetch real-time weather for the given lat/lon from Open-Meteo."""
    lat = float(arguments.get("lat", 0))
    lon = float(arguments.get("lon", 0))
    return fetch_live_weather(lat, lon)


if __name__ == "__main__":
    server = SimpleMCPServer(
        server_name="Weather MCP Server",
        tools=[
            ToolDefinition(
                name="weather.snapshot",
                description="Return the weather snapshot used by the disaster engine.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "request": {"type": "object"},
                    },
                    "required": ["request"],
                },
                handler=weather_snapshot,
            ),
            ToolDefinition(
                name="weather.live_snapshot",
                description="Fetch real-time weather for latitude/longitude from Open-Meteo.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "lat": {"type": "number", "description": "Latitude"},
                        "lon": {"type": "number", "description": "Longitude"},
                    },
                    "required": ["lat", "lon"],
                },
                handler=live_snapshot,
            ),
        ],
    )
    server.serve_forever()
