"""Menu AIR TRAFFIC. Aprire il menu non chiama ADSB.lol."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from core.session import city_label
from services.live.aircraft import PAGE_SIZE, e
from worlds.airtraffic.queries import QUERIES


def kb(label: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(label, callback_data=data)


def world_nav_row(*, back: str = "world:list") -> list[InlineKeyboardButton]:
    return [
        kb("⬅️ Air Traffic", "airtraffic:menu") if back == "airtraffic:menu" else kb("⬅️ Indietro", back),
        kb("🌍 Mondi", "world:list"),
        kb("📍 Cambia città", "city:ask"),
    ]


def menu_text(city: dict) -> str:
    name = city_label(city)
    lines = [
        "✈️ <b>AIR TRAFFIC</b>",
        f"📍 {e(name)}",
        "",
    ]
    for item in QUERIES:
        lines.append(f"{item['emoji']} {item['title']}")
    lines.append("")
    lines.append("<i>ADSB.lol · aerei LIVE. Nessun Overpass.</i>")
    return "\n".join(lines)


def menu_keyboard() -> InlineKeyboardMarkup:
    rows = [[kb(f"{item['emoji']} {item['title']}", f"airtraffic:{item['id']}")] for item in QUERIES]
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
                [kb("🔄 Riprova", f"airtraffic:{query_id}")],
                world_nav_row(back="airtraffic:menu"),
            ]
        )
    items = list(rows or [])
    total = len(items)
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE) if total else 1
    page = max(0, min(int(page), pages - 1))
    extra: list[InlineKeyboardButton] = []
    if total > PAGE_SIZE:
        if page > 0:
            extra.append(kb("⬅️", f"airtraffic:{query_id}:page:{page - 1}"))
        extra.append(kb(f"Pagina {page + 1}/{pages}", f"airtraffic:{query_id}:page:{page}"))
        if page + 1 < pages:
            extra.append(kb("➡️", f"airtraffic:{query_id}:page:{page + 1}"))
    grid: list[list[InlineKeyboardButton]] = []
    if extra:
        grid.append(extra)
    grid.append(world_nav_row(back="airtraffic:menu"))
    return InlineKeyboardMarkup(grid)
