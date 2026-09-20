"""Menu SPACE."""

from __future__ import annotations

from telegram import InlineKeyboardMarkup

from core.session import city_label
from services.live.osm import e
from worlds.nav import kb, results_markup, world_nav_row
from worlds.space.queries import QUERIES


def menu_text(city: dict) -> str:
    name = city_label(city)
    lines = ["🛰️ <b>SPACE</b>", f"📍 {e(name)}", ""]
    for item in QUERIES:
        lines.append(f"{item['emoji']} {item['title']}")
    lines.append("")
    lines.append("<i>ISS · CelesTrak TLE · calcolo locale. Nessuna API key.</i>")
    return "\n".join(lines)


def menu_keyboard() -> InlineKeyboardMarkup:
    rows = [[kb(f"{item['emoji']} {item['title']}", f"space:{item['id']}")] for item in QUERIES]
    rows.append(world_nav_row(back="world:list"))
    return InlineKeyboardMarkup(rows)


def results_keyboard(bundle: dict, *, page: int, query_id: str, error: bool, rows: list) -> InlineKeyboardMarkup:
    shown = [r for r in rows if (r.get("elevation") or -90) >= 0] or rows
    return results_markup(
        prefix="space",
        query_id=query_id or "iss",
        page=page,
        total=len(shown),
        error=error,
        menu_callback="space:menu",
    )
