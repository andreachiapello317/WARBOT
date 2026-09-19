"""Aerei LIVE: bbox, normalizzazione, distanza, OpenSky. Senza Overpass."""

from __future__ import annotations

import json
import math
import unittest
from unittest.mock import patch

from services.live.aircraft import (
    PAGE_SIZE,
    Aircraft,
    altitude_m,
    bbox_from_radius,
    empty_text,
    error_text,
    format_aircraft,
    get_aircraft_nearby,
    haversine_km,
    normalize_states,
    parse_state,
    sort_aircraft,
    velocity_kmh,
    wait_text,
)
from worlds.opensky.queries import QUERIES as OPENSKY_QUERIES
from worlds.osm.queries import PUBLIC_TO_ENGINE
from services.live.osm import CATEGORIES, WORLD_CATEGORIES


MILANO = (45.4642, 9.1900)
ROMA = (41.9028, 12.4964)
LONDRA = (51.5074, -0.1278)
PACIFIC = (0.0, -150.0)


def _state(
    icao24: str,
    lat: float,
    lon: float,
    *,
    callsign: str | None = "AZA123  ",
    alt: float | None = 8430.0,
    on_ground: bool = False,
    velocity: float | None = 204.17,
    heading: float | None = 184.0,
    vrate: float | None = 0.5,
    ts: int = 1_700_000_000,
    geo: float | None = None,
) -> list:
    row = [None] * 14
    row[0] = icao24
    row[1] = callsign
    row[2] = "Italy"
    row[3] = ts
    row[4] = ts
    row[5] = lon
    row[6] = lat
    row[7] = alt
    row[8] = on_ground
    row[9] = velocity
    row[10] = heading
    row[11] = vrate
    row[13] = geo
    return row


class IsolationTest(unittest.TestCase):
    def test_opensky_not_in_overpass_categories(self) -> None:
        self.assertIn("aero", WORLD_CATEGORIES)
        self.assertNotIn("air", WORLD_CATEGORIES)
        self.assertNotIn("air", CATEGORIES)
        self.assertNotIn("aircraft", PUBLIC_TO_ENGINE)
        self.assertEqual(OPENSKY_QUERIES[0]["id"], "aircraft")

    def test_osm_menu_does_not_list_opensky(self) -> None:
        from worlds.osm.menu import menu_text

        text = menu_text({"name": "Milano", "display": "Milano, Italia", "lat": 45.46, "lon": 9.19})
        self.assertIn("Aeroporti", text)
        self.assertNotIn("OPEN SKY", text)
        self.assertNotIn("Aerei LIVE", text)


class BBoxTest(unittest.TestCase):
    def test_milan_50km_edges(self) -> None:
        lamin, lomin, lamax, lomax = bbox_from_radius(*MILANO, 50)
        north = haversine_km(MILANO[0], MILANO[1], lamax, MILANO[1])
        east = haversine_km(MILANO[0], MILANO[1], MILANO[0], lomax)
        self.assertAlmostEqual(north, 50, delta=0.6)
        self.assertAlmostEqual(east, 50, delta=0.6)
        area = (lamax - lamin) * (lomax - lomin)
        self.assertLess(area, 25)
        self.assertGreater(lamin, 44.9)
        self.assertLess(lamax, 46.0)
        self.assertGreater(lomin, 8.4)
        self.assertLess(lomax, 10.0)

    def test_london_accounts_for_latitude(self) -> None:
        m_box = bbox_from_radius(*MILANO, 50)
        l_box = bbox_from_radius(*LONDRA, 50)
        milan_dlon = m_box[3] - m_box[1]
        london_dlon = l_box[3] - l_box[1]
        self.assertGreater(london_dlon, milan_dlon)

    def test_radius_capped(self) -> None:
        wide = bbox_from_radius(*MILANO, 500)
        tight = bbox_from_radius(*MILANO, 150)
        self.assertEqual(wide, tight)


class DistanceTest(unittest.TestCase):
    def test_milan_rome(self) -> None:
        km = haversine_km(*MILANO, *ROMA)
        self.assertGreater(km, 470)
        self.assertLess(km, 490)

    def test_same_point(self) -> None:
        self.assertAlmostEqual(haversine_km(*MILANO, *MILANO), 0.0, places=6)


class NormalizeTest(unittest.TestCase):
    def test_callsign_stripped_and_units(self) -> None:
        plane = parse_state(_state("4ca123", 45.50, 9.25), center_lat=MILANO[0], center_lon=MILANO[1])
        self.assertIsNotNone(plane)
        assert plane is not None
        self.assertEqual(plane.callsign, "AZA123")
        self.assertEqual(plane.icao24, "4ca123")
        self.assertEqual(velocity_kmh(plane.velocity), 735)
        self.assertEqual(altitude_m(plane.altitude), 8430)
        self.assertAlmostEqual(plane.heading or 0, 184.0)
        self.assertFalse(plane.on_ground)
        self.assertGreater(plane.distance_km, 0)

    def test_geo_altitude_fallback(self) -> None:
        row = _state("abc", 45.47, 9.20, alt=None, geo=1000.0)
        plane = parse_state(row, center_lat=MILANO[0], center_lon=MILANO[1])
        self.assertIsNotNone(plane)
        assert plane is not None
        self.assertEqual(altitude_m(plane.altitude), 1000)

    def test_missing_coords_dropped(self) -> None:
        row = _state("dead", 45.47, 9.20)
        row[5] = None
        row[6] = None
        self.assertIsNone(parse_state(row, center_lat=MILANO[0], center_lon=MILANO[1]))

    def test_dedup_keeps_newer(self) -> None:
        a = _state("4ca123", 45.47, 9.20, ts=10, alt=1000)
        b = _state("4ca123", 45.48, 9.21, ts=20, alt=2000, callsign="AZA999")
        planes = normalize_states([a, b], center_lat=MILANO[0], center_lon=MILANO[1], radius_km=50)
        self.assertEqual(len(planes), 1)
        self.assertEqual(planes[0].callsign, "AZA999")
        self.assertEqual(planes[0].altitude, 2000)

    def test_outside_radius_dropped(self) -> None:
        far = _state("far001", 46.5, 10.5)
        planes = normalize_states([far], center_lat=MILANO[0], center_lon=MILANO[1], radius_km=50)
        self.assertEqual(planes, [])


class SortTest(unittest.TestCase):
    def test_airborne_then_distance_then_altitude(self) -> None:
        ground = Aircraft("g1", "GND", 45.47, 9.20, 0, 10, 0, 0, True, 1, 2.0)
        near_low = Aircraft("a1", "NEAR", 45.47, 9.20, 3000, 100, 0, 0, False, 1, 5.0)
        near_high = Aircraft("a2", "HIGH", 45.47, 9.20, 9000, 100, 0, 0, False, 1, 5.0)
        far = Aircraft("a3", "FAR", 45.70, 9.50, 8000, 100, 0, 0, False, 1, 40.0)
        ordered = sort_aircraft([ground, far, near_low, near_high])
        self.assertEqual([p.icao24 for p in ordered], ["a2", "a1", "a3", "g1"])


class FormatTest(unittest.TestCase):
    def test_wait_and_empty(self) -> None:
        place = {"name": "Milano", "display": "Milano, Italia"}
        self.assertIn("Milano", wait_text(place))
        self.assertIn("Nessun aereo rilevato", empty_text(place))

    def test_telegram_card(self) -> None:
        plane = parse_state(_state("4ca123", 45.60, 9.30), center_lat=MILANO[0], center_lon=MILANO[1])
        assert plane is not None
        bundle = {
            "ok": True,
            "aircraft": [plane.as_row()],
            "time": None,
        }
        text = format_aircraft(bundle, {"name": "Milano"})
        self.assertIn("AEREI LIVE — MILANO", text)
        self.assertIn("AZA123", text)
        self.assertIn("km", text)
        self.assertIn("8.430 m", text)
        self.assertIn("735 km/h", text)
        self.assertIn("184°", text)
        self.assertIn("4CA123", text)
        self.assertIn("Aggiornato", text)

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
        self.assertIn("limite", error_text({"code": "rate"}, place))
        self.assertIn("non è momentaneamente disponibile", error_text({"code": "unavailable"}, place))
        self.assertNotIn("Traceback", error_text({"code": "timeout"}, place))

    def test_in_volo_a_terra_sections(self) -> None:
        air = Aircraft("aa", "FLY", 45.47, 9.20, 8000, 200, 10, 0, False, 1, 3.0).as_row()
        gnd = Aircraft("bb", "TAX", 45.46, 9.19, 0, 5, 0, 0, True, 1, 1.0).as_row()
        text = format_aircraft({"ok": True, "aircraft": [air, gnd], "time": 1}, {"name": "Milano"})
        self.assertIn("IN VOLO", text)
        self.assertIn("A TERRA", text)
        self.assertLess(text.index("FLY"), text.index("TAX"))


class ClientMockTest(unittest.TestCase):
    def test_http_429(self) -> None:
        with patch("services.live.aircraft._http_get", return_value=(429, b"")):
            bundle = get_aircraft_nearby(*MILANO, force=True)
        self.assertFalse(bundle["ok"])
        self.assertEqual(bundle["code"], "rate")
        self.assertIn("limite", error_text(bundle, {"name": "Milano"}))

    def test_timeout_not_retried(self) -> None:
        calls = {"n": 0}

        def fake_get(url: str, headers: dict, timeout: int):
            calls["n"] += 1
            return 0, b""

        with patch("services.live.aircraft._http_get", side_effect=fake_get):
            bundle = get_aircraft_nearby(*ROMA, force=True)
        self.assertFalse(bundle["ok"])
        self.assertEqual(bundle["code"], "timeout")
        self.assertEqual(calls["n"], 1)

    def test_bad_json(self) -> None:
        with patch("services.live.aircraft._http_get", return_value=(200, b"not-json")):
            bundle = get_aircraft_nearby(*LONDRA, force=True)
        self.assertFalse(bundle["ok"])
        self.assertEqual(bundle["code"], "bad_json")

    def test_empty_states(self) -> None:
        payload = json.dumps({"time": 1, "states": []}).encode()
        with patch("services.live.aircraft._http_get", return_value=(200, payload)):
            bundle = get_aircraft_nearby(*PACIFIC, force=True)
        self.assertTrue(bundle["ok"])
        self.assertEqual(bundle["aircraft"], [])
        self.assertIn("Nessun aereo", format_aircraft(bundle, {"name": "Pacifico"}))

    def test_valid_payload_filters_junk(self) -> None:
        good = _state("4ca123", 45.50, 9.22)
        junk = _state("", 45.50, 9.22)
        junk[0] = None
        nocoord = _state("none", 45.50, 9.22)
        nocoord[5] = None
        nocoord[6] = None
        payload = json.dumps({"time": 1700000000, "states": [good, junk, nocoord]}).encode()
        with patch("services.live.aircraft._http_get", return_value=(200, payload)):
            bundle = get_aircraft_nearby(*MILANO, force=True)
        self.assertTrue(bundle["ok"])
        self.assertEqual(bundle["raw_states"], 3)
        self.assertEqual(bundle["valid"], 1)
        self.assertEqual(bundle["aircraft"][0]["callsign"], "AZA123")
        lamin, lomin, lamax, lomax = bundle["bbox"]
        self.assertLess(lamin, MILANO[0])
        self.assertGreater(lamax, MILANO[0])
        self.assertLess(lomin, MILANO[1])
        self.assertGreater(lomax, MILANO[1])

    def test_one_transient_retry(self) -> None:
        payload = json.dumps({"time": 1, "states": [_state("abcabc", 45.47, 9.20)]}).encode()
        calls = [(503, b""), (200, payload)]

        def fake_get(url: str, headers: dict, timeout: int):
            self.assertIn("states/all", url)
            self.assertIn("lamin=", url)
            return calls.pop(0)

        with patch("services.live.aircraft._http_get", side_effect=fake_get):
            bundle = get_aircraft_nearby(*MILANO, force=True)
        self.assertTrue(bundle["ok"])
        self.assertEqual(bundle["valid"], 1)
        self.assertEqual(calls, [])


class LiveOpenSkyTest(unittest.TestCase):
    """Chiamate reali a OpenSky. Saltate se la rete/API non risponde.

    Imposta OPENSKY_LIVE_TEST=1 per forzarle: da molti cloud OpenSky
    chiude l'handshake TLS (policy anti-hyperscaler documentata).
    """

    def _probe(self, name: str, lat: float, lon: float) -> dict:
        bundle = get_aircraft_nearby(lat, lon, force=True)
        bundle["_city"] = name
        bundle["_center"] = (lat, lon)
        return bundle

    def test_milano_roma_londra(self) -> None:
        import os

        if not (os.getenv("OPENSKY_LIVE_TEST") or "").strip():
            self.skipTest("OpenSky live test disattivato (OPENSKY_LIVE_TEST=1)")
        results = []
        for name, coords in (("Milano", MILANO), ("Roma", ROMA), ("Londra", LONDRA)):
            bundle = self._probe(name, *coords)
            results.append(bundle)
            lamin, lomin, lamax, lomax = bundle["bbox"]
            self.assertLess(lamin, coords[0])
            self.assertGreater(lamax, coords[0])
            if bundle.get("ok") and bundle.get("aircraft"):
                plane = bundle["aircraft"][0]
                self.assertTrue(math.isfinite(plane["lat"]))
                self.assertTrue(math.isfinite(plane["distance_km"]))
                text = format_aircraft(bundle, {"name": name})
                self.assertIn("AEREI LIVE", text)
        empty = get_aircraft_nearby(*PACIFIC, radius_km=10, force=True)
        print("\n[LIVE]", [(b["_city"], b.get("ok"), b.get("http"), b.get("valid"), b.get("code")) for b in results])
        print("[LIVE empty pacific]", empty.get("ok"), empty.get("http"), empty.get("valid"), empty.get("code"))
        if not any(b.get("ok") for b in results):
            self.skipTest("OpenSky non raggiungibile: " + str([(b["_city"], b.get("http"), b.get("code")) for b in results]))


if __name__ == "__main__":
    unittest.main()
