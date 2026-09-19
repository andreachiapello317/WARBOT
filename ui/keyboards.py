"""Tastiere inline OSM WORLD."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from services.live.osm import CATEGORIES, LIST_LIMIT, WORLD_CATEGORIES


def kb_btn(label: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(label, callback_data=data)


def nav_row() -> list[InlineKeyboardButton]:
    return [kb_btn("⬅️ Indietro", "nav:back"), kb_btn("🏠 Inizio", "home:menu")]


def _pairs(items: list[InlineKeyboardButton]) -> list[list[InlineKeyboardButton]]:
    rows: list[list[InlineKeyboardButton]] = []
    pair: list[InlineKeyboardButton] = []
    for btn in items:
        pair.append(btn)
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    return rows


def back_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([nav_row()])


def osm_world_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [kb_btn("🔎 Cerca località", "live:ow")],
            [kb_btn("❓ Aiuto", "home:aiuto")],
        ]
    )


def osm_hits_keyboard(n: int) -> InlineKeyboardMarkup:
    buttons = [kb_btn(str(i + 1), f"live:ow:p:{i}") for i in range(max(0, min(n, 5)))]
    rows = _pairs(buttons)
    rows.append([kb_btn("🔎 Un'altra ricerca", "live:ow")])
    rows.append(nav_row())
    return InlineKeyboardMarkup(rows)


def osm_place_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        kb_btn(f"{CATEGORIES[key]['emoji']} {CATEGORIES[key]['title']}", f"live:ow:c:{key}")
        for key in WORLD_CATEGORIES
    ]
    rows = _pairs(buttons)
    rows.append([kb_btn("🗺️ Mappa", "live:ow:map")])
    rows.append([kb_btn("🔎 Cerca un'altra località", "live:ow")])
    rows.append(nav_row())
    return InlineKeyboardMarkup(rows)


def osm_category_keyboard(
    rows: list[dict] | None = None,
    *,
    page: int = 0,
    error_cat: str | None = None,
) -> InlineKeyboardMarkup:
    if error_cat:
        return InlineKeyboardMarkup(
            [
                [kb_btn("🔄 Riprova", f"live:ow:c:{error_cat}")],
                [kb_btn("📍 Località", "live:ow:here")],
                nav_row(),
            ]
        )
    start = max(0, page) * LIST_LIMIT
    items = list(rows or [])
    chunk = items[start : start + LIST_LIMIT]
    buttons = [kb_btn(str(row.get("name") or "punto")[:40], f"live:ow:i:{start + i}") for i, row in enumerate(chunk)]
    grid = _pairs(buttons)
    extra: list[InlineKeyboardButton] = []
    if start + LIST_LIMIT < len(items):
        extra.append(kb_btn("➡️ Altri risultati", "live:ow:more"))
    if page > 0:
        extra.append(kb_btn("⬅️ Lista precedente", "live:ow:pg"))
    if extra:
        grid.append(extra)
    grid.append([kb_btn("📍 Località", "live:ow:here"), kb_btn("🗺️ Mappa", "live:ow:map")])
    grid.append([kb_btn("🔎 Cerca un'altra località", "live:ow")])
    grid.append(nav_row())
    return InlineKeyboardMarkup(grid)


def osm_item_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [kb_btn("📋 Lista", "live:ow:list"), kb_btn("📍 Località", "live:ow:here")],
            [kb_btn("🗺️ Mappa", "live:ow:map")],
            [kb_btn("🔎 Cerca un'altra località", "live:ow")],
            nav_row(),
        ]
    )
