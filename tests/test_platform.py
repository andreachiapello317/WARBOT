"""Geo condiviso, registry, parser SKY/EARTH, niente OpenSky."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from core.geo import haversine_km, km_to_nm
from core.http import error_code, parse_json
from core.pagination import clamp_page, page_count, page_slice
from core.session import city_from_hit
from worlds.earth.service import format_earth
from worlds.registry import WORLD_META, parse_callback, world_ids
from worlds.sky.service import format_sky, run_sky


MILANO = {"name": "Milano", "display": "Milano, Italia", "lat": 45.4642, "lon": 9.1900}


class GeoTest(unittest.TestCase):
    def test_milan_rome(self) -> None:
        km = haversine_km(45.4642, 9.1900, 41.9028, 12.4964)
        self.assertGreater(km, 470)
        self.assertLess(km, 490)

    def test_km_to_nm(self) -> None:
        self.assertEqual(km_to_nm(50), 27)


class PaginationTest(unittest.TestCase):
    def test_pages(self) -> None:
        self.assertEqual(page_count(0), 1)
        self.assertEqual(page_count(20), 1)
        self.assertEqual(page_count(21), 2)
        self.assertEqual(clamp_page(9, 25), 1)
        self.assertEqual(page_slice(list(range(25)), 1), list(range(20, 25)))


class HttpHelpersTest(unittest.TestCase):
    def test_error_codes(self) -> None:
        self.assertEqual(error_code(0), "timeout")
        self.assertEqual(error_code(429), "rate")
        self.assertEqual(error_code(403), "denied")
        self.assertTrue(parse_json(b"not")[1])
        self.assertEqual(parse_json(b'{"a":1}')[0], {"a": 1})


class CityContextTest(unittest.TestCase):
    def test_aliases(self) -> None:
        city = city_from_hit(
            {
                "name": "Milano",
                "display": "Milano, Lombardia, Italia",
                "lat": 45.46,
                "lon": 9.19,
                "country": "Italia",
                "country_code": "IT",
                "state": "Lombardia",
            }
        )
        self.assertEqual(city["latitude"], city["lat"])
        self.assertEqual(city["longitude"], city["lon"])
        self.assertEqual(city["country_code"], "it")
        self.assertEqual(city["display_name"], "Milano, Lombardia, Italia")
        self.assertIn("geocoded_at", city)


class RegistryTest(unittest.TestCase):
    def test_five_worlds(self) -> None:
        self.assertEqual(list(world_ids()), ["osm", "airtraffic", "sky", "earth", "space"])
        self.assertEqual(parse_callback("sky:weather:day:1"), ("sky", ["weather", "day", "1"]))
        self.assertEqual(parse_callback("earth:earthquakes"), ("earth", ["earthquakes"]))
        self.assertEqual(parse_callback("space:iss"), ("space", ["iss"]))
        self.assertNotIn("opensky", [w["id"] for w in WORLD_META])


class SkyFormatTest(unittest.TestCase):
    def test_error_and_weather(self) -> None:
        err = format_sky({"ok": False, "code": "timeout"}, MILANO)
        self.assertIn("temporaneamente non disponibile", err)
        bundle = {
            "ok": True,
            "kind": "weather",
            "query": "weather",
            "timezone": "Europe/Rome",
            "current": {
                "temperature_2m": 22.2,
                "apparent_temperature": 22.0,
                "relative_humidity_2m": 64,
                "cloud_cover": 58,
                "wind_speed_10m": 14,
                "precipitation_probability": 20,
                "weather_code": 2,
            },
            "daily": {
                "sunrise": ["2026-09-20T06:58"],
                "sunset": ["2026-09-20T19:21"],
                "uv_index_max": [4.2],
                "time": ["2026-09-20"],
            },
        }
        text = format_sky(bundle, MILANO)
        self.assertIn("22°C", text)
        self.assertIn("Alba", text)

    def test_marine_not_pertinent(self) -> None:
        text = format_sky({"ok": True, "kind": "marine", "pertinent": False, "grid_km": 210}, MILANO)
        self.assertIn("non pertinenti", text)

    def test_run_sky_uses_cache_not_menu(self) -> None:
        fake = {"ok": True, "kind": "weather", "current": {}, "daily": {}, "rows": []}
        with patch("worlds.sky.service.fetch_weather", return_value=dict(fake)) as fetch:
            a = run_sky(MILANO, "weather")
            b = run_sky(MILANO, "weather:week")
        fetch.assert_called_once()
        self.assertTrue(a["ok"] and b["ok"])


class EarthFormatTest(unittest.TestCase):
    def test_empty_quakes(self) -> None:
        text = format_earth({"ok": True, "kind": "earthquakes", "rows": [], "radius_km": 500}, MILANO)
        self.assertIn("Nessun terremoto", text)

    def test_quake_card(self) -> None:
        text = format_earth(
            {
                "ok": True,
                "kind": "earthquakes",
                "radius_km": 500,
                "rows": [
                    {
                        "magnitude": 2.4,
                        "place": "4 km N of Bergamo",
                        "time_ms": int(__import__("time").time() * 1000) - 12 * 60 * 1000,
                        "depth_km": 9,
                        "distance_km": 87,
                        "url": "https://earthquake.usgs.gov/earthquakes/eventpage/x",
                    }
                ],
            },
            MILANO,
        )
        self.assertIn("M 2.4", text)
        self.assertIn("87 km", text)
        self.assertIn("usgs.gov", text)

    def test_flood_is_forecast(self) -> None:
        text = format_earth(
            {
                "ok": True,
                "kind": "flood",
                "forecast": True,
                "rows": [{"date": "2026-09-20", "discharge": 12.5}],
            },
            MILANO,
        )
        self.assertIn("Previsione", text)
        self.assertIn("12.5", text)

    def test_malformed_usgs(self) -> None:
        from worlds.earth.service import fetch_earthquakes

        with patch("worlds.earth.service._get", return_value=(200, {"features": "nope"}, False, 10)):
            bundle = fetch_earthquakes(45.46, 9.19)
        self.assertTrue(bundle["ok"])
        self.assertEqual(bundle["rows"], [])


if __name__ == "__main__":
    unittest.main()
