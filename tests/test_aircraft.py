"""Aerei LIVE: ADSB.lol, distanza, paginazione. Senza Overpass."""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from services.live.adsb_client import point_url
from services.live.aircraft import (
    PAGE_SIZE,
    Aircraft,
    altitude_m,
    bbox_from_radius,
    clear_aircraft_cache,
    empty_text,
    error_text,
    format_aircraft,
    get_aircraft_nearby,
    haversine_km,
    km_to_nm,
    normalize_aircraft,
    parse_ac,
    sort_aircraft,
    velocity_kmh,
    wait_text,
)
from worlds.airtraffic.queries import QUERIES as AIR_QUERIES
from worlds.osm.queries import PUBLIC_TO_ENGINE
from services.live.osm import CATEGORIES, WORLD_CATEGORIES


MILANO = (45.4642, 9.1900)
ROMA = (41.9028, 12.4964)
LONDRA = (51.5074, -0.1278)


def _ac(
    hex_id: str,
    lat: float,
    lon: float,
    *,
    flight: str | None = "AZA123  ",
    alt_baro: object = 27625,
    gs: float | None = 410.4,
    track: float | None = 245.0,
    baro_rate: float | None = 64.0,
    seen: float = 0.4,
    r: str | None = "EI-ABC",
    t: str | None = "A320",
) -> dict:
    return {
        "hex": hex_id,
        "flight": flight,
        "lat": lat,
        "lon": lon,
        "alt_baro": alt_baro,
        "gs": gs,
        "track": track,
        "baro_rate": baro_rate,
        "seen": seen,
        "r": r,
        "t": t,
        "type": "adsb_icao",
        "messages": 1,
        "mlat": [],
        "tisb": [],
        "rssi": -20.0,
    }


class IsolationTest(unittest.TestCase):
    def test_airtraffic_not_in_overpass_categories(self) -> None:
        self.assertIn("aero", WORLD_CATEGORIES)
        self.assertNotIn("air", WORLD_CATEGORIES)
        self.assertNotIn("air", CATEGORIES)
        self.assertNotIn("aircraft", PUBLIC_TO_ENGINE)
        self.assertEqual(AIR_QUERIES[0]["id"], "aircraft")
        self.assertEqual(len(AIR_QUERIES), 1)

    def test_osm_menu_does_not_list_airtraffic(self) -> None:
        from worlds.osm.menu import menu_text

        text = menu_text({"name": "Milano", "display": "Milano, Italia", "lat": 45.46, "lon": 9.19})
        self.assertIn("Aeroporti", text)
        self.assertNotIn("AIR TRAFFIC", text)
        self.assertNotIn("Aerei LIVE", text)
        self.assertNotIn("OPEN SKY", text)

    def test_no_opensky_runtime(self) -> None:
        import worlds.registry as registry

        self.assertNotIn("opensky", [item["id"] for item in registry.WORLD_META])
        with self.assertRaises(ModuleNotFoundError):
            __import__("services.live.opensky_client")
        with self.assertRaises(ModuleNotFoundError):
            __import__("worlds.opensky.handler")


class RadiusTest(unittest.TestCase):
    def test_50km_is_27nm(self) -> None:
        self.assertEqual(km_to_nm(50), 27)
        self.assertEqual(km_to_nm(1), 1)
        self.assertEqual(km_to_nm(5000), 250)

    def test_milan_50km_bbox_edges(self) -> None:
        lamin, lomin, lamax, lomax = bbox_from_radius(*MILANO, 50)
        north = haversine_km(MILANO[0], MILANO[1], lamax, MILANO[1])
        east = haversine_km(MILANO[0], MILANO[1], MILANO[0], lomax)
        self.assertAlmostEqual(north, 50, delta=0.6)
        self.assertAlmostEqual(east, 50, delta=0.6)

    def test_point_url(self) -> None:
        url = point_url(*MILANO, 27)
        self.assertTrue(url.startswith("https://api.adsb.lol/v2/lat/"))
        self.assertIn("/lon/", url)
        self.assertTrue(url.endswith("/dist/27"))
        self.assertNotIn("opensky", url.lower())


class DistanceTest(unittest.TestCase):
    def test_milan_rome(self) -> None:
        km = haversine_km(*MILANO, *ROMA)
        self.assertGreater(km, 470)
        self.assertLess(km, 490)

    def test_same_point(self) -> None:
        self.assertAlmostEqual(haversine_km(*MILANO, *MILANO), 0.0, places=6)


class NormalizeTest(unittest.TestCase):
    def test_callsign_stripped_and_units(self) -> None:
        plane = parse_ac(_ac("4ca123", 45.50, 9.25), center_lat=MILANO[0], center_lon=MILANO[1])
        self.assertIsNotNone(plane)
        assert plane is not None
        self.assertEqual(plane.callsign, "AZA123")
        self.assertEqual(plane.icao24, "4ca123")
        self.assertEqual(velocity_kmh(plane.velocity), 760)
        self.assertEqual(altitude_m(plane.altitude), 8420)
        self.assertAlmostEqual(plane.heading or 0, 245.0)
        self.assertFalse(plane.on_ground)
        self.assertGreater(plane.distance_km, 0)

    def test_ground_flag(self) -> None:
        plane = parse_ac(
            _ac("abcabc", 45.47, 9.20, alt_baro="ground", gs=12.0),
            center_lat=MILANO[0],
            center_lon=MILANO[1],
        )
        self.assertIsNotNone(plane)
        assert plane is not None
        self.assertTrue(plane.on_ground)
        self.assertEqual(altitude_m(plane.altitude), 0)

    def test_geom_altitude_fallback(self) -> None:
        raw = _ac("abc", 45.47, 9.20, alt_baro=None)
        raw["alt_geom"] = 3281
        plane = parse_ac(raw, center_lat=MILANO[0], center_lon=MILANO[1])
        self.assertIsNotNone(plane)
        assert plane is not None
        self.assertEqual(altitude_m(plane.altitude), 1000)

    def test_missing_coords_dropped(self) -> None:
        raw = _ac("dead", 45.47, 9.20)
        raw["lat"] = None
        raw["lon"] = None
        self.assertIsNone(parse_ac(raw, center_lat=MILANO[0], center_lon=MILANO[1]))

    def test_last_position_fallback(self) -> None:
        raw = _ac("4ca999", 0, 0)
        raw["lat"] = None
        raw["lon"] = None
        raw["lastPosition"] = {"lat": 45.47, "lon": 9.20, "nic": 0, "rc": 0, "seen_pos": 1}
        plane = parse_ac(raw, center_lat=MILANO[0], center_lon=MILANO[1])
        self.assertIsNotNone(plane)

    def test_missing_fields_ok(self) -> None:
        raw = {"hex": "abc123", "lat": 45.47, "lon": 9.20, "type": "adsb_icao", "messages": 1, "mlat": [], "tisb": [], "rssi": -1, "seen": 0}
        plane = parse_ac(raw, center_lat=MILANO[0], center_lon=MILANO[1])
        self.assertIsNotNone(plane)
        assert plane is not None
        self.assertIsNone(plane.callsign)
        self.assertIsNone(plane.velocity)
        self.assertIsNone(plane.heading)

    def test_dedup_keeps_newer(self) -> None:
        a = _ac("4ca123", 45.47, 9.20, flight="OLD", seen=12)
        b = _ac("4ca123", 45.48, 9.21, flight="AZA999", alt_baro=6562, seen=1)
        planes = normalize_aircraft(
            [a, b],
            center_lat=MILANO[0],
            center_lon=MILANO[1],
            radius_km=50,
            now_ms=1_700_000_000_000,
        )
        self.assertEqual(len(planes), 1)
        self.assertEqual(planes[0].callsign, "AZA999")

    def test_outside_radius_dropped(self) -> None:
        far = _ac("far001", 46.5, 10.5)
        planes = normalize_aircraft([far], center_lat=MILANO[0], center_lon=MILANO[1], radius_km=50)
        self.assertEqual(planes, [])


class SortTest(unittest.TestCase):
    def test_distance_then_airborne(self) -> None:
        ground = Aircraft("g1", "GND", 45.47, 9.20, 0, 10, 0, 0, True, 1, 2.0)
        near_low = Aircraft("a1", "NEAR", 45.47, 9.20, 3000, 100, 0, 0, False, 1, 5.0)
        far = Aircraft("a3", "FAR", 45.70, 9.50, 8000, 100, 0, 0, False, 1, 40.0)
        ordered = sort_aircraft([ground, far, near_low])
        self.assertEqual([p.icao24 for p in ordered], ["g1", "a1", "a3"])


class FormatTest(unittest.TestCase):
    def test_wait_and_empty(self) -> None:
        place = {"name": "Milano", "display": "Milano, Italia"}
        self.assertIn("Milano", wait_text(place))
        self.assertIn("Nessun aereo rilevato nell'area di Milano", empty_text(place))

    def test_telegram_card(self) -> None:
        plane = parse_ac(_ac("4ca123", 45.60, 9.30), center_lat=MILANO[0], center_lon=MILANO[1])
        assert plane is not None
        bundle = {"ok": True, "aircraft": [plane.as_row()], "time": None}
        text = format_aircraft(bundle, {"name": "Milano"})
        self.assertIn("AEREI LIVE — MILANO", text)
        self.assertIn("AZA123", text)
        self.assertIn("ICAO: 4CA123", text)
        self.assertIn("8.420 m", text)
        self.assertIn("760 km/h", text)
        self.assertIn("245°", text)
        self.assertIn("Distanza:", text)

    def test_pagination_twenty(self) -> None:
        rows = []
        for i in range(25):
            plane = Aircraft(
                f"{i:06x}",
                f"CS{i:03d}",
                45.46,
                9.19,
                8000,
                200,
                90,
                0,
                False,
                1,
                float(i),
            )
            rows.append(plane.as_row())
        bundle = {"ok": True, "aircraft": rows, "time": 1}
        page0 = format_aircraft(bundle, {"name": "Milano"}, offset=0, limit=PAGE_SIZE)
        page1 = format_aircraft(bundle, {"name": "Milano"}, offset=PAGE_SIZE, limit=PAGE_SIZE)
        self.assertIn("CS000", page0)
        self.assertNotIn("CS020", page0)
        self.assertIn("CS020", page1)
        self.assertIn("1–20 di 25", page0)

    def test_error_messages(self) -> None:
        place = {"name": "Roma"}
        text = error_text({"code": "timeout"}, place)
        self.assertIn("Servizio traffico aereo temporaneamente non disponibile", text)
        self.assertIn("Riprova tra poco", text)
        self.assertNotIn("Traceback", text)
        self.assertNotIn("OpenSky", text)
        self.assertNotIn("OPENSKY", text)

    def test_ground_alt_line(self) -> None:
        gnd = Aircraft("bb", "TAX", 45.46, 9.19, 0, 9, 0, 0, True, 1, 1.0).as_row()
        text = format_aircraft({"ok": True, "aircraft": [gnd], "time": 1}, {"name": "Milano"})
        self.assertIn("Alt: a terra", text)


class ErrorCodeTest(unittest.TestCase):
    def test_mapping(self) -> None:
        from services.live.aircraft import _error_code

        self.assertEqual(_error_code(0), "timeout")
        self.assertEqual(_error_code(429), "rate")
        self.assertEqual(_error_code(503), "unavailable")
        self.assertEqual(_error_code(404), "unavailable")
        self.assertEqual(_error_code(-1), "network")


class ClientMockTest(unittest.TestCase):
    def setUp(self) -> None:
        clear_aircraft_cache()

    def tearDown(self) -> None:
        clear_aircraft_cache()

    def _payload(self, rows: list[dict]) -> bytes:
        return json.dumps({"ac": rows, "now": 1_700_000_000_000, "total": len(rows), "msg": "ok", "ctime": 1, "ptime": 1}).encode()

    def test_http_429(self) -> None:
        with patch("core.http.http_get", return_value=(429, b"", {"retry-after": "30"})):
            bundle = get_aircraft_nearby(*MILANO, force=True)
        self.assertFalse(bundle["ok"])
        self.assertEqual(bundle["code"], "rate")
        self.assertIn("temporaneamente non disponibile", error_text(bundle, {"name": "Milano"}))

    def test_429_short_retry_after(self) -> None:
        payload = self._payload([_ac("abcabc", 45.47, 9.20)])
        calls = {"n": 0}

        def fake_http(url: str, **_kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                return 429, b"", {"retry-after": "0.1"}
            return 200, payload, {}

        with (
            patch("core.http.time.sleep") as sleep,
            patch("core.http.http_get", side_effect=fake_http),
        ):
            bundle = get_aircraft_nearby(*MILANO, force=True)
        self.assertTrue(bundle["ok"])
        self.assertEqual(len(bundle["aircraft"]), 1)
        sleep.assert_called()

    def test_timeout(self) -> None:
        with patch("core.http.http_get", return_value=(0, b"", {})):
            bundle = get_aircraft_nearby(*MILANO, force=True)
        self.assertFalse(bundle["ok"])
        self.assertEqual(bundle["code"], "timeout")

    def test_http_5xx(self) -> None:
        with patch("core.http.http_get", return_value=(503, b"", {})):
            bundle = get_aircraft_nearby(*MILANO, force=True)
        self.assertFalse(bundle["ok"])
        self.assertEqual(bundle["code"], "unavailable")

    def test_bad_json(self) -> None:
        with patch("core.http.http_get", return_value=(200, b"not-json", {})):
            bundle = get_aircraft_nearby(*MILANO, force=True)
        self.assertFalse(bundle["ok"])
        self.assertEqual(bundle["code"], "bad_json")

    def test_empty_list(self) -> None:
        with patch("core.http.http_get", return_value=(200, self._payload([]), {})):
            bundle = get_aircraft_nearby(*MILANO, force=True)
        self.assertTrue(bundle["ok"])
        self.assertEqual(bundle["aircraft"], [])
        self.assertIn("Nessun aereo rilevato", empty_text({"name": "Milano"}))

    def test_success_normalizes(self) -> None:
        payload = self._payload([_ac("4ca123", 45.47, 9.20)])
        with patch("core.http.http_get", return_value=(200, payload, {})) as http:
            bundle = get_aircraft_nearby(*MILANO, force=True)
        self.assertTrue(bundle["ok"])
        self.assertEqual(bundle["aircraft"][0]["callsign"], "AZA123")
        url = http.call_args[0][0]
        self.assertIn("/v2/point/", url)
        self.assertEqual(bundle.get("provider"), "airplanes.live")

    def test_fallback_adsb_on_403(self) -> None:
        payload = self._payload([_ac("4ca123", 45.47, 9.20)])

        def fake(url: str, **_kwargs):
            if "airplanes.live" in url:
                return 403, b'{"error":"contact"}', {}
            return 200, payload, {}

        with patch("core.http.http_get", side_effect=fake):
            bundle = get_aircraft_nearby(*MILANO, force=True)
        self.assertTrue(bundle["ok"])
        self.assertEqual(bundle.get("provider"), "adsb.lol")

    def test_cache_avoids_second_http(self) -> None:
        payload = self._payload([_ac("4ca123", 45.47, 9.20)])
        with patch("core.http.http_get", return_value=(200, payload, {})) as http:
            a = get_aircraft_nearby(*MILANO, force=True)
            b = get_aircraft_nearby(*MILANO, force=False)
        self.assertTrue(a["ok"] and b["ok"])
        self.assertEqual(http.call_count, 1)

    def test_no_credentials_in_request(self) -> None:
        with patch("core.http.http_get", return_value=(200, self._payload([]), {})) as http:
            get_aircraft_nearby(*MILANO, force=True)
        self.assertNotIn("Authorization", str(http.call_args))
        self.assertNotIn("api_key", str(http.call_args).lower())


class LiveAdsbTest(unittest.TestCase):
    """Chiamata reale a ADSB.lol. Saltata se la rete non risponde."""

    def test_milan_live(self) -> None:
        if not (os.getenv("AIRTRAFFIC_LIVE_TEST") or "1").strip():
            pass
        bundle = get_aircraft_nearby(*MILANO, force=True)
        if not bundle.get("ok"):
            self.skipTest("ADSB.lol non raggiungibile: http=%s code=%s" % (bundle.get("http"), bundle.get("code")))
        self.assertEqual(bundle.get("provider"), "adsb.lol")
        self.assertIn("aircraft", bundle)


if __name__ == "__main__":
    unittest.main()
