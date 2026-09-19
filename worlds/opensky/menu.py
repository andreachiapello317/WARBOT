"""Menu OPEN SKY. Aprire il menu non chiama OpenSky."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from core.session import city_label
from services.live.aircraft import PAGE_SIZE, e
from worlds.opensky.queries import QUERIES


def kb(label: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(label, callback_data=data)


def world_nav_row(*, back: str = "world:list") -> list[InlineKeyboardButton]:
    return [
        kb("⬅️ OpenSky", "opensky:menu") if back == "opensky:menu" else kb("⬅️ Indietro", back),
        kb("🌍 Mondi", "world:list"),
        kb("📍 Cambia città", "city:ask"),
    ]


def menu_text(city: dict) -> str:
    name = city_label(city)
    lines = [
        "✈️ <b>OPEN SKY</b>",
        f"📍 {e(name)}",
        "",
    ]
    for item in QUERIES:
        lines.append(f"{item['emoji']} {item['title']}")
    lines.append("")
    lines.append("<i>OpenSky Network · state vectors. Nessun Overpass.</i>")
    return "\n".join(lines)


def menu_keyboard() -> InlineKeyboardMarkup:
    rows = [[kb(f"{item['emoji']} {item['title']}", f"opensky:{item['id']}")] for item in QUERIES]
    rows.append(world_nav_row(back="world:list"))
    return InlineKeyboardMarkup(rows)


def results_keyboard(
    rows: list[dict] | None = None,
    *,
    page: int = 0,
    query_id: str = "aircraft",
    error: bool = False,
) -> InlineKeyboardMarkup:
    if error:
        return InlineKeyboardMarkup(
            [
                [kb("🔄 Riprova", f"opensky:{query_id}")],
                world_nav_row(back="opensky:menu"),
            ]
        )
    items = list(rows or [])
    start = max(0, page) * PAGE_SIZE
    extra: list[InlineKeyboardButton] = []
    if start + PAGE_SIZE < len(items):
        extra.append(kb("➡️ Altri", f"opensky:{query_id}:page:{page + 1}"))
    if page > 0:
        extra.append(kb("⬅️ Indietro", f"opensky:{query_id}:page:{page - 1}"))
    grid: list[list[InlineKeyboardButton]] = []
    if extra:
        grid.append(extra)
    grid.append(world_nav_row(back="opensky:menu"))
    return InlineKeyboardMarkup(grid)
