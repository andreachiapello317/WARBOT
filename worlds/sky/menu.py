"""Menu SKY. Aprire il menu non chiama Open-Meteo."""

from __future__ import annotations

from telegram import InlineKeyboardMarkup

from core.session import city_label
from services.live.osm import e
from worlds.nav import kb, results_markup, world_nav_row
from worlds.sky.queries import QUERIES


def menu_text(city: dict) -> str:
    name = city_label(city)
    lines = ["🌤️ <b>SKY</b>", f"📍 {e(name)}", ""]
    for item in QUERIES:
        lines.append(f"{item['emoji']} {item['title']}")
    lines.append("")
    lines.append("<i>Open-Meteo · lat/lon della città. Nessuna API key.</i>")
    return "\n".join(lines)


def menu_keyboard() -> InlineKeyboardMarkup:
    rows = [[kb(f"{item['emoji']} {item['title']}", f"sky:{item['id']}")] for item in QUERIES]
    rows.append(world_nav_row(back="world:list"))
    return InlineKeyboardMarkup(rows)


def results_keyboard(bundle: dict, *, page: int, query_id: str, error: bool, rows: list) -> InlineKeyboardMarkup:
    extra = []
    kind = (query_id or "").split(":")[0]
    if kind == "weather" and not error:
        extra = [
            [
                kb("📅 Oggi", "sky:weather"),
                kb("📅 Domani", "sky:weather:day:1"),
                kb("📅 7 giorni", "sky:weather:week"),
            ]
        ]
    elif kind == "air" and not error:
        extra = [
            [
                kb("Ora", "sky:air"),
                kb("Prossime 12h", "sky:air:hours"),
            ]
        ]
    return results_markup(
        prefix="sky",
        query_id=kind or "weather",
        page=page,
        total=len(rows),
        error=error,
        extra_rows=extra,
        menu_callback="sky:menu",
    )
