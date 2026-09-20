"""Menu EARTH."""

from __future__ import annotations

from telegram import InlineKeyboardMarkup

from core.session import city_label
from services.live.osm import e
from worlds.earth.queries import QUERIES
from worlds.nav import kb, results_markup, world_nav_row


def menu_text(city: dict) -> str:
    name = city_label(city)
    lines = ["🌋 <b>EARTH</b>", f"📍 {e(name)}", ""]
    for item in QUERIES:
        lines.append(f"{item['emoji']} {item['title']}")
    return "\n".join(lines)


def menu_keyboard() -> InlineKeyboardMarkup:
    rows = [[kb(f"{item['emoji']} {item['title']}", f"earth:{item['id']}")] for item in QUERIES]
    rows.append(world_nav_row(back="world:list"))
    return InlineKeyboardMarkup(rows)


def results_keyboard(bundle: dict, *, page: int, query_id: str, error: bool, rows: list) -> InlineKeyboardMarkup:
    extra = []
    kind = (query_id or "").split(":")[0]
    if kind == "earthquakes" and not error:
        extra = [
            [
                kb("24h", "earth:earthquakes"),
                kb("7 giorni", "earth:eq7"),
                kb("M≥4", "earth:eqm4"),
            ]
        ]
    return results_markup(
        prefix="earth",
        query_id=query_id or "earthquakes",
        page=page,
        total=len(rows),
        error=error,
        extra_rows=extra,
        menu_callback="earth:menu",
    )
