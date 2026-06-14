from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from autonomous_betting_agent.weatherapi import WeatherLocationMismatchError, fetch_weather_snapshot


class WeatherApiTests(unittest.TestCase):
    def _mock_response(self, payload: dict) -> Mock:
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = payload
        return response

    def test_fetch_rejects_mismatched_weatherapi_location(self) -> None:
        payload = {
            "location": {"name": "England", "region": "Oppland", "country": "Norway", "localtime": "2026-06-14 12:00"},
            "current": {"temp_c": 12, "wind_kph": 10, "wind_mph": 6, "precip_mm": 0, "humidity": 70, "is_day": 1},
            "forecast": {"forecastday": [{"date": "2026-06-14", "day": {"condition": {"text": "Clear"}, "avgtemp_c": 12, "maxwind_kph": 10, "maxwind_mph": 6, "totalprecip_mm": 0, "avghumidity": 70, "daily_chance_of_rain": 0, "daily_chance_of_snow": 0}}]},
        }
        with patch("autonomous_betting_agent.weatherapi.requests.get", return_value=self._mock_response(payload)):
            with self.assertRaises(WeatherLocationMismatchError):
                fetch_weather_snapshot("real_key", "London, England", "2026-06-14T12:00:00Z")

    def test_fetch_allows_mismatch_when_strict_location_disabled(self) -> None:
        payload = {
            "location": {"name": "England", "region": "Oppland", "country": "Norway", "localtime": "2026-06-14 12:00"},
            "current": {"temp_c": 12, "wind_kph": 10, "wind_mph": 6, "precip_mm": 0, "humidity": 70, "is_day": 1},
            "forecast": {"forecastday": [{"date": "2026-06-14", "day": {"condition": {"text": "Clear"}, "avgtemp_c": 12, "maxwind_kph": 10, "maxwind_mph": 6, "totalprecip_mm": 0, "avghumidity": 70, "daily_chance_of_rain": 0, "daily_chance_of_snow": 0}}]},
        }
        with patch("autonomous_betting_agent.weatherapi.requests.get", return_value=self._mock_response(payload)):
            snapshot = fetch_weather_snapshot("real_key", "London, England", "2026-06-14T12:00:00Z", strict_location=False)
        self.assertEqual(snapshot.weather_location, "England, Oppland, Norway")

    def test_fetch_accepts_matching_weatherapi_location(self) -> None:
        payload = {
            "location": {"name": "Berlin", "region": "Berlin", "country": "Germany", "localtime": "2026-06-14 12:00"},
            "current": {"temp_c": 22, "wind_kph": 10, "wind_mph": 6, "precip_mm": 0, "humidity": 50, "is_day": 1},
            "forecast": {"forecastday": [{"date": "2026-06-14", "day": {"condition": {"text": "Clear"}, "avgtemp_c": 22, "maxwind_kph": 10, "maxwind_mph": 6, "totalprecip_mm": 0, "avghumidity": 50, "daily_chance_of_rain": 0, "daily_chance_of_snow": 0}}]},
        }
        with patch("autonomous_betting_agent.weatherapi.requests.get", return_value=self._mock_response(payload)):
            snapshot = fetch_weather_snapshot("real_key", "Berlin, Germany", "2026-06-14T12:00:00Z")
        self.assertEqual(snapshot.weather_location, "Berlin, Berlin, Germany")
        self.assertTrue(snapshot.forecast_is_exact)


if __name__ == "__main__":
    unittest.main()
