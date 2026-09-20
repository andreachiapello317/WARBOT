"""Menu CITY LIFE. Aprire il menu non chiama API."""

from __future__ import annotations

from telegram import InlineKeyboardMarkup

from core.session import city_label
from services.live.osm import e
from worlds.life.queries import QUERIES
from worlds.nav import kb, results_markup, world_nav_row


def menu_text(city: dict) -> str:
    name = city_label(city)
    lines = [
        "🏙️ <b>CITY LIFE</b>",
        f"📍 {e(name)}",
        "",
        "Mobilità OSM, allerte Meteoalarm, aria Open-Meteo, vita in città.",
        "",
    ]
    for item in QUERIES:
        lines.append(f"{item['emoji']} {item['title']}")
    lines.append("")
    lines.append(
        "<i>Niente TomTom/Google/GTFS-RT: servono chiavi o feed locali. "
        "Notifiche push non sono su questo piano. Condividi la posizione in chat per «vicino a me».</i>"
    )
    return "\n".join(lines)


def menu_keyboard() -> InlineKeyboardMarkup:
    rows: list[list] = []
    pair: list = []
    for item in QUERIES:
        pair.append(kb(f"{item['emoji']} {item['title']}", f"life:{item['id']}"))
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    rows.append(world_nav_row(back="world:list"))
    return InlineKeyboardMarkup(rows)


def results_keyboard(bundle: dict, *, page: int, query_id: str, error: bool, rows: list) -> InlineKeyboardMarkup:
    kind = (query_id or "").split(":")[0] or "near"
    extra = []
    if kind == "near" and not error:
        extra = [
            [
                kb("🚦 Mobilità", "life:mobility"),
                kb("🏥 Sicurezza", "life:safety"),
            ]
        ]
    return results_markup(
        prefix="life",
        query_id=kind,
        page=page,
        total=len(rows),
        error=error,
        extra_rows=extra,
        menu_callback="life:menu",
    )
