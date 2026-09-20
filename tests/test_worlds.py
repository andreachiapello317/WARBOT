"""CITY → WORLDS → QUERIES: navigazione, CityContext, nessun re-geocoding."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.session import (
    SCREEN_OSM_MENU,
    SCREEN_WORLDS,
    city_from_hit,
    get_city,
    get_world_id,
    set_city,
    set_screen,
    set_world,
)
from worlds.city import city_prompt_text, format_worlds
from worlds.osm.menu import menu_text as osm_menu_text
from worlds.osm.queries import engine_id, public_id
from worlds.airtraffic.menu import menu_text as air_menu_text
from worlds.airtraffic.queries import get_query
from worlds.registry import WORLD_META, parse_callback, world_menu_items


MILANO = {
    "name": "Milano",
    "display": "Milano, Italia",
    "lat": 45.4642,
    "lon": 9.1900,
    "bbox": (45.3, 9.0, 45.6, 9.4),
    "country": "Italia",
    "source": "test",
}

TOKYO = {
    "name": "Tokyo",
    "display": "Tokyo, Japan",
    "lat": 35.6762,
    "lon": 139.6503,
    "bbox": (35.5, 139.5, 35.8, 139.8),
    "country": "Japan",
    "source": "test",
}


class FakeBot:
    def __init__(self) -> None:
        self.edits: list[dict] = []
        self.sends: list[dict] = []

    async def edit_message_text(self, **kwargs):
        self.edits.append(kwargs)

    async def send_message(self, **kwargs):
        self.sends.append(kwargs)
        return SimpleNamespace(message_id=2)


class FakeContext:
    def __init__(self) -> None:
        self.user_data: dict = {}
        self.chat_data: dict = {"last_bot_msg": {"id": 1, "kind": "text"}}
        self.bot = FakeBot()
        self.args: list[str] = []


class FakeUpdate:
    def __init__(self) -> None:
        self.effective_chat = SimpleNamespace(id=1)
        self.effective_message = SimpleNamespace(message_id=9, text="x")
        self.callback_query = None


def _hit(place: dict) -> dict:
    return dict(place)


class RegistryTest(unittest.TestCase):
    def test_two_worlds_no_invented_third(self) -> None:
        ids = [item["id"] for item in WORLD_META]
        self.assertEqual(ids, ["osm", "airtraffic", "sky", "earth", "space"])
        items = world_menu_items()
        self.assertEqual(items[0]["callback"], "world:osm")
        self.assertEqual(items[1]["callback"], "world:airtraffic")
        self.assertEqual(items[2]["callback"], "world:sky")
        self.assertEqual(items[3]["callback"], "world:earth")
        self.assertEqual(items[4]["callback"], "world:space")

    def test_parse_callback_hierarchy(self) -> None:
        self.assertEqual(parse_callback("world:osm"), ("world", ["osm"]))
        self.assertEqual(parse_callback("osm:rail:page:2"), ("osm", ["rail", "page", "2"]))
        self.assertEqual(parse_callback("airtraffic:aircraft:page:1"), ("airtraffic", ["aircraft", "page", "1"]))
        self.assertEqual(parse_callback("world:airtraffic"), ("world", ["airtraffic"]))
        self.assertEqual(parse_callback("city:ask"), ("city", ["ask"]))


class CityContextTest(unittest.TestCase):
    def test_city_fields(self) -> None:
        ctx = FakeContext()
        city = set_city(ctx, MILANO)  # type: ignore[arg-type]
        self.assertEqual(city["name"], "Milano")
        self.assertEqual(city["lat"], 45.4642)
        self.assertEqual(city["lon"], 9.1900)
        self.assertEqual(city["bbox"], MILANO["bbox"])
        self.assertIn("geocoding", city)
        self.assertEqual(get_city(ctx)["lat"], 45.4642)  # type: ignore[index]

    def test_change_city_clears_airtraffic_state(self) -> None:
        from core.session import airtraffic_state

        ctx = FakeContext()
        set_city(ctx, MILANO)  # type: ignore[arg-type]
        airtraffic_state(ctx)["bundle"] = {"ok": True, "aircraft": [{"icao24": "old"}]}  # type: ignore[arg-type]
        set_city(ctx, TOKYO)  # type: ignore[arg-type]
        self.assertNotIn("bundle", airtraffic_state(ctx))  # type: ignore[arg-type]

    def test_start_text(self) -> None:
        text = city_prompt_text()
        self.assertIn("WARBOT", text)
        self.assertIn("città", text.lower())
        self.assertNotIn("Aeroporti", text)

    def test_world_menu_after_city(self) -> None:
        text = format_worlds(city_from_hit(MILANO))
        self.assertIn("Milano", text)
        self.assertIn("OSM WORLD", text)
        self.assertIn("AIR TRAFFIC", text)
        self.assertIn("SKY", text)
        self.assertIn("EARTH", text)
        self.assertIn("SPACE", text)
        self.assertNotIn("OPEN SKY", text)
        self.assertNotIn("Stazioni", text)
        self.assertNotIn("Aeroporti", text)


class QueryMapTest(unittest.TestCase):
    def test_osm_public_ids(self) -> None:
        self.assertEqual(engine_id("airports"), "aero")
        self.assertEqual(engine_id("rail"), "rail")
        self.assertEqual(engine_id("hospitals"), "hosp")
        self.assertEqual(public_id("aero"), "airports")
        osm = osm_menu_text(city_from_hit(MILANO))
        self.assertIn("Stazioni", osm)
        self.assertIn("OSM WORLD", osm)
        self.assertNotIn("AIR TRAFFIC", osm)
        self.assertNotIn("OPEN SKY", osm)

    def test_airtraffic_documented_only(self) -> None:
        self.assertIsNotNone(get_query("aircraft"))
        self.assertIsNone(get_query("nearby"))
        self.assertIsNone(get_query("traffic"))
        self.assertIsNone(get_query("arrival"))
        self.assertIsNone(get_query("departure"))
        air = air_menu_text(city_from_hit(MILANO))
        self.assertIn("Aerei LIVE", air)
        self.assertIn("AIR TRAFFIC", air)
        self.assertNotIn("Stazioni", air)


class FlowTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.update = FakeUpdate()
        self.ctx = FakeContext()
        self.geocode_calls = 0

    def _geocode(self, query: str):
        self.geocode_calls += 1
        place = MILANO if "milano" in query.lower() else TOKYO
        return {"ok": True, "hits": [_hit(place)]}

    async def test_start_milano_world_menu_no_external_query(self) -> None:
        from worlds.city import lookup_city, show_city_prompt, show_worlds
        from worlds.osm.handler import show_menu as osm_menu
        from worlds.airtraffic.handler import show_menu as air_menu

        await show_city_prompt(self.update, self.ctx)  # type: ignore[arg-type]
        last = self.ctx.bot.edits[-1]["text"] if self.ctx.bot.edits else self.ctx.bot.sends[-1]["text"]
        self.assertIn("città", last.lower())

        with (
            patch("worlds.city.geocode", side_effect=self._geocode),
            patch("worlds.osm.queries.search") as osm_search,
            patch("worlds.airtraffic.queries.get_aircraft_in_area") as air_search,
            patch("services.live.osm.search") as osm_search2,
        ):
            osm_search.side_effect = AssertionError("Overpass sul WORLD MENU")
            osm_search2.side_effect = AssertionError("Overpass sul WORLD MENU")
            air_search.side_effect = AssertionError("ADSB.lol sul WORLD MENU")
            await lookup_city(self.update, self.ctx, "Milano")  # type: ignore[arg-type]
            self.assertEqual(self.geocode_calls, 1)
            city = get_city(self.ctx)  # type: ignore[arg-type]
            self.assertEqual(city["name"], "Milano")
            menu = self.ctx.bot.edits[-1]["text"]
            self.assertIn("Scegli un mondo", menu)
            self.assertIn("OSM WORLD", menu)
            self.assertIn("AIR TRAFFIC", menu)
            self.assertIn("SKY", menu)
            self.assertNotIn("Stazioni ferroviarie", menu)

            await osm_menu(self.update, self.ctx)  # type: ignore[arg-type]
            osm_txt = self.ctx.bot.edits[-1]["text"]
            self.assertIn("OSM WORLD", osm_txt)
            self.assertIn("Stazioni", osm_txt)

            await air_menu(self.update, self.ctx)  # type: ignore[arg-type]
            air_txt = self.ctx.bot.edits[-1]["text"]
            self.assertIn("AIR TRAFFIC", air_txt)
            self.assertIn("Aerei LIVE", air_txt)

            await show_worlds(self.update, self.ctx)  # type: ignore[arg-type]
            await osm_menu(self.update, self.ctx)  # type: ignore[arg-type]
            await air_menu(self.update, self.ctx)  # type: ignore[arg-type]
            self.assertEqual(self.geocode_calls, 1)
            self.assertEqual(get_city(self.ctx)["lat"], 45.4642)  # type: ignore[index]

    async def test_osm_stations_calls_only_overpass(self) -> None:
        from worlds.osm.handler import show_query

        set_city(self.ctx, MILANO)  # type: ignore[arg-type]
        fake_bundle = {"ok": True, "rows": [{"name": "Milano Centrale", "lat": 45.48, "lon": 9.20, "category": "rail"}], "title": "Stazioni", "emoji": "🚆", "total": 1, "pool": 1}

        with (
            patch("worlds.osm.queries.peek", return_value=None),
            patch("worlds.osm.handler.peek_query", return_value=None),
            patch("worlds.osm.handler.run_query", return_value=fake_bundle) as run,
            patch("worlds.airtraffic.queries.get_aircraft_in_area") as air,
        ):
            air.side_effect = AssertionError("ADSB.lol non deve partire da OSM stazioni")
            await show_query(self.update, self.ctx, "rail")  # type: ignore[arg-type]
            run.assert_called_once()
            text = self.ctx.bot.edits[-1]["text"]
            self.assertIn("Centrale", text)

    async def test_airtraffic_aircraft_calls_only_adsb(self) -> None:
        from worlds.airtraffic.handler import show_query

        set_city(self.ctx, MILANO)  # type: ignore[arg-type]
        fake = {
            "ok": True,
            "aircraft": [
                {
                    "icao24": "4ca123",
                    "callsign": "AZA123",
                    "distance_km": 18.4,
                    "altitude": 8420,
                    "velocity": 760,
                    "heading": 245,
                    "on_ground": False,
                }
            ],
            "time": 1,
        }

        with (
            patch("worlds.airtraffic.queries.get_aircraft_in_area", return_value=fake) as air,
            patch("worlds.osm.queries.search") as osm,
        ):
            osm.side_effect = AssertionError("Overpass non deve partire da AIR TRAFFIC")
            await show_query(self.update, self.ctx, "aircraft")  # type: ignore[arg-type]
            air.assert_called_once()
            args, _kwargs = air.call_args
            self.assertAlmostEqual(args[0], 45.4642, places=3)
            self.assertAlmostEqual(args[1], 9.1900, places=3)
            text = self.ctx.bot.edits[-1]["text"]
            self.assertIn("AZA123", text)
            self.assertIn("ICAO: 4CA123", text)

    async def test_airtraffic_pagination_does_not_requery(self) -> None:
        from worlds.airtraffic.handler import show_page, show_query

        set_city(self.ctx, MILANO)  # type: ignore[arg-type]
        rows = [
            {
                "icao24": f"{i:06x}",
                "callsign": f"CS{i:03d}",
                "distance_km": float(i),
                "altitude": 8000,
                "velocity": 700,
                "heading": 90,
                "on_ground": False,
            }
            for i in range(25)
        ]
        fake = {"ok": True, "aircraft": rows, "time": 1}
        with patch("worlds.airtraffic.queries.get_aircraft_in_area", return_value=fake) as air:
            await show_query(self.update, self.ctx, "aircraft")  # type: ignore[arg-type]
            await show_page(self.update, self.ctx, "aircraft", 1)  # type: ignore[arg-type]
            self.assertEqual(air.call_count, 1)
        text = self.ctx.bot.edits[-1]["text"]
        self.assertIn("CS020", text)

    async def test_change_city_tokyo_no_query_on_menu(self) -> None:
        from worlds.city import lookup_city

        set_city(self.ctx, MILANO)  # type: ignore[arg-type]
        with (
            patch("worlds.city.geocode", side_effect=self._geocode),
            patch("worlds.osm.queries.search") as osm,
            patch("worlds.airtraffic.queries.get_aircraft_in_area") as air,
        ):
            osm.side_effect = AssertionError("no overpass")
            air.side_effect = AssertionError("no adsb")
            await lookup_city(self.update, self.ctx, "Tokyo")  # type: ignore[arg-type]
            city = get_city(self.ctx)  # type: ignore[arg-type]
            self.assertEqual(city["name"], "Tokyo")
            self.assertAlmostEqual(city["lat"], 35.6762, places=3)
            menu = self.ctx.bot.edits[-1]["text"]
            self.assertIn("Tokyo", menu)
            self.assertIn("Scegli un mondo", menu)

    async def test_back_from_osm_to_worlds(self) -> None:
        from bot import go_back
        from worlds.osm.handler import show_menu as osm_menu

        set_city(self.ctx, MILANO)  # type: ignore[arg-type]
        await osm_menu(self.update, self.ctx)  # type: ignore[arg-type]
        self.assertEqual(get_world_id(self.ctx), "osm")  # type: ignore[arg-type]
        await go_back(self.update, self.ctx)  # type: ignore[arg-type]
        text = self.ctx.bot.edits[-1]["text"]
        self.assertIn("Scegli un mondo", text)

    async def test_back_from_airtraffic_results_to_menu(self) -> None:
        from bot import go_back
        from core.session import SCREEN_AIRTRAFFIC_RESULTS, set_screen
        from worlds.airtraffic.handler import show_menu as air_menu

        set_city(self.ctx, MILANO)  # type: ignore[arg-type]
        await air_menu(self.update, self.ctx)  # type: ignore[arg-type]
        set_screen(self.ctx, SCREEN_AIRTRAFFIC_RESULTS)  # type: ignore[arg-type]
        await go_back(self.update, self.ctx)  # type: ignore[arg-type]
        text = self.ctx.bot.edits[-1]["text"]
        self.assertIn("AIR TRAFFIC", text)
        self.assertIn("Aerei LIVE", text)

    async def test_dispatch_world_switch_no_geocode(self) -> None:
        from bot import dispatch

        set_city(self.ctx, MILANO)  # type: ignore[arg-type]
        with patch("worlds.city.geocode") as geo:
            await dispatch(self.update, self.ctx, "world:osm")  # type: ignore[arg-type]
            await dispatch(self.update, self.ctx, "world:airtraffic")  # type: ignore[arg-type]
            await dispatch(self.update, self.ctx, "world:sky")  # type: ignore[arg-type]
            await dispatch(self.update, self.ctx, "world:list")  # type: ignore[arg-type]
            geo.assert_not_called()
            self.assertEqual(get_city(self.ctx)["name"], "Milano")  # type: ignore[index]


if __name__ == "__main__":
    unittest.main()
