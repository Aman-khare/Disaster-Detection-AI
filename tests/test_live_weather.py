from __future__ import annotations

import unittest

from crisismind.live_weather import (
    auto_detect_disaster_type,
    estimate_signals,
    _weather_defaults,
)


class LiveWeatherTests(unittest.TestCase):
    """Unit tests for the live_weather module.

    These tests cover the pure functions only (no network calls).
    """

    def test_auto_detect_cyclone_for_high_wind(self) -> None:
        weather = {"rainfall_mm": 10, "wind_kph": 100, "temperature_c": 28}
        self.assertEqual(auto_detect_disaster_type(weather), "cyclone")

    def test_auto_detect_flood_for_heavy_rain(self) -> None:
        weather = {"rainfall_mm": 80, "wind_kph": 30, "temperature_c": 28}
        self.assertEqual(auto_detect_disaster_type(weather), "flood")

    def test_auto_detect_heatwave_for_high_temp(self) -> None:
        weather = {"rainfall_mm": 5, "wind_kph": 15, "temperature_c": 42}
        self.assertEqual(auto_detect_disaster_type(weather), "heatwave")

    def test_estimate_signals_returns_valid_ranges(self) -> None:
        weather = {"rainfall_mm": 120, "wind_kph": 60, "temperature_c": 34, "air_quality_index": 90}
        signals = estimate_signals(weather)
        for key in ("social_signal_level", "news_signal_level", "population_density", "vulnerable_population_percent"):
            self.assertIn(key, signals)
            self.assertGreaterEqual(signals[key], 0)
            self.assertLessEqual(signals[key], 100)

    def test_weather_defaults_returns_safe_values(self) -> None:
        defaults = _weather_defaults()
        self.assertEqual(defaults["rainfall_mm"], 0)
        self.assertEqual(defaults["temperature_c"], 25)
        self.assertEqual(defaults["wind_kph"], 0)


if __name__ == "__main__":
    unittest.main()
