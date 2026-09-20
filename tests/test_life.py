"""CITY LIFE: orari OSM, confronto città, formattazione, niente API sul menu."""

from __future__ import annotations

import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from core.geo import azimuth_deg, cardinal_it
from core.session import get_previous_city, set_city
from worlds.life.hours import is_open_now
from worlds.life.queries import get_query
from worlds.life.service import format_life, run_compare
from worlds.registry import WORLD_META, world_ids
from worlds.sky.service import format_sky
from worlds.space.service import aurora_chance, format_space


MILANO = {
    "name": "Milano",
    "display": "Milano, Italia",
    "lat": 45.4642,
    "lon": 9.1900,
    "bbox": (45.3, 9.0, 45.6, 9.4),
    "country": "Italia",
    "country_code": "it",
    "state": "Lombardia",
    "source": "test",
}

TORINO = {
    "name": "Torino",
    "display": "Torino, Italia",
    "lat": 45.0703,
    "lon": 7.6869,
    "bbox": (45.0, 7.5, 45.2, 7.8),
    "country": "Italia",
    "country_code": "it",
    "state": "Piemonte",
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


class FakeUpdate:
    def __init__(self) -> None:
        self.effective_chat = SimpleNamespace(id=1)
        self.effective_message = SimpleNamespace(message_id=9, text="x")
        self.callback_query = None


class HoursTest(unittest.TestCase):
    def test_always_open(self) -> None:
        now = datetime(2026, 9, 20, 15, 0, tzinfo=ZoneInfo("Europe/Rome"))
        self.assertTrue(is_open_now("24/7", now))

    def test_weekday_range(self) -> None:
        wed = datetime(2026, 9, 16, 12, 0, tzinfo=ZoneInfo("Europe/Rome"))
        sat = datetime(2026, 9, 19, 12, 0, tzinfo=ZoneInfo("Europe/Rome"))
        spec = "Mo-Fr 09:00-18:00"
        self.assertTrue(is_open_now(spec, wed))
        self.assertFalse(is_open_now(spec, sat))

    def test_unknown_seasonal(self) -> None:
        now = datetime(2026, 9, 20, 12, 0, tzinfo=ZoneInfo("Europe/Rome"))
        self.assertIsNone(is_open_now("Apr-Oct 09:00-19:00", now))
        self.assertIsNone(is_open_now("", now))


class RegistryLifeTest(unittest.TestCase):
    def test_six_worlds_life_second(self) -> None:
        self.assertEqual(list(world_ids()), ["osm", "life", "airtraffic", "sky", "earth", "space"])
        self.assertEqual(WORLD_META[1]["id"], "life")
        self.assertIsNotNone(get_query("near"))
        self.assertIsNotNone(get_query("vicino"))
        self.assertIsNone(get_query("tomtom"))


class CompareSessionTest(unittest.TestCase):
    def test_previous_city_kept(self) -> None:
        ctx = FakeContext()
        set_city(ctx, MILANO)  # type: ignore[arg-type]
        self.assertIsNone(get_previous_city(ctx))  # type: ignore[arg-type]
        set_city(ctx, TORINO)  # type: ignore[arg-type]
        prev = get_previous_city(ctx)  # type: ignore[arg-type]
        self.assertIsNotNone(prev)
        self.assertEqual(prev["name"], "Milano")  # type: ignore[index]

    def test_compare_without_previous(self) -> None:
        text = format_life({"ok": True, "kind": "compare", "other": None, "rows": []}, MILANO)
        self.assertIn("Cambia città", text)
        self.assertIn("CONFRONTO", text)


class FormatCardsTest(unittest.TestCase):
    def test_pollen_card(self) -> None:
        text = format_sky(
            {
                "ok": True,
                "kind": "pollen",
                "current": {"grass_pollen": 12.0, "birch_pollen": 0.0},
            },
            MILANO,
        )
        self.assertIn("POLLINI", text)
        self.assertIn("Erba", text)
        self.assertIn("moderato", text)

    def test_aurora_chance_milan(self) -> None:
        self.assertIn("non visibile", aurora_chance(45.46, 3.0))
        self.assertIn("possibile", aurora_chance(69.0, 5.0))

    def test_aurora_card(self) -> None:
        text = format_space(
            {"ok": True, "kind": "aurora", "kp": 2.0, "kp_max": 3.0, "chance": "non visibile a questa latitudine"},
            MILANO,
        )
        self.assertIn("Kp ora", text)
        self.assertIn("non visibile", text)

    def test_iss_direction(self) -> None:
        text = format_space(
            {
                "ok": True,
                "kind": "iss",
                "iss": {"lat": 45.0, "lon": 9.0, "altitude": 420, "velocity": 27600, "provider": "wheretheiss.at"},
                "distance_km": 80,
                "next_pass": {
                    "in_minutes": 42,
                    "max_el": 38,
                    "aos": "2026-09-20T21:14:00+00:00",
                    "aos_az": 320.0,
                    "aos_dir": "NO",
                    "max_dir": "NE",
                    "sun_el": -18.0,
                },
            },
            MILANO,
        )
        self.assertIn("Compare da NO", text)
        self.assertIn("Notturno", text)

    def test_azimuth_cardinal(self) -> None:
        az = azimuth_deg(45.0, 9.0, 46.0, 9.0)
        self.assertTrue(az > 350 or az < 10)
        self.assertEqual(cardinal_it(0), "N")
        self.assertEqual(cardinal_it(270), "O")


class MenuNoApiTest(unittest.IsolatedAsyncioTestCase):
    async def test_life_menu_does_not_call_overpass(self) -> None:
        from worlds.life.handler import show_menu

        ctx = FakeContext()
        set_city(ctx, MILANO)  # type: ignore[arg-type]
        with (
            patch("worlds.life.overpass.overpass") as op,
            patch("worlds.life.alerts.fetch_meteoalarm") as al,
            patch("worlds.sky.service.fetch_air") as air,
        ):
            op.side_effect = AssertionError("Overpass sul menu CITY LIFE")
            al.side_effect = AssertionError("Meteoalarm sul menu")
            air.side_effect = AssertionError("Open-Meteo sul menu")
            await show_menu(FakeUpdate(), ctx)  # type: ignore[arg-type]
        text = ctx.bot.edits[-1]["text"]
        self.assertIn("CITY LIFE", text)
        self.assertIn("Vicino a me", text)
        self.assertIn("Mobilità", text)


class CompareRunTest(unittest.TestCase):
    def test_compare_uses_two_cities_no_geocode(self) -> None:
        fake_air = {"ok": True, "kind": "air", "current": {"european_aqi": 40, "pm2_5": 12}}
        fake_wx = {"ok": True, "kind": "weather", "current": {"temperature_2m": 18}}
        with (
            patch("worlds.life.service.fetch_air", return_value=fake_air) as air,
            patch("worlds.life.service.fetch_weather", return_value=fake_wx) as wx,
        ):
            bundle = run_compare(MILANO, TORINO)
        self.assertEqual(air.call_count, 2)
        self.assertEqual(wx.call_count, 2)
        text = format_life(bundle, MILANO)
        self.assertIn("MILANO", text)
        self.assertIn("TORINO", text)
        self.assertIn("18°C vs 18°C", text)


if __name__ == "__main__":
    unittest.main()
