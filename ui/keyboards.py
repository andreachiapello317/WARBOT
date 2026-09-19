"""Tastiere inline del live: hub, zone, navi, ISS, OSM WORLD."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from services.live import REGIONS
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


def live_hub_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [kb_btn("🔄 Aggiorna posizioni", "home:live")],
            [kb_btn("✈️ Aerei Italia", "live:ac:it"), kb_btn("🌊 Mediterraneo", "live:ac:med")],
            [kb_btn("🚁 Elicotteri", "live:heli:it"), kb_btn("⚓ Navi Baltico", "live:ships")],
            [kb_btn("🛰️ Mappa ISS", "live:iss"), kb_btn("🌍 OSM WORLD", "live:ow")],
            [kb_btn("❓ Aiuto", "home:aiuto")],
        ]
    )


def osm_world_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [kb_btn("🔎 Cerca località", "live:ow")],
            [kb_btn("📡 Posizioni live", "home:live")],
            nav_row(),
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
    rows.append([kb_btn("📡 Posizioni live", "home:live")])
    rows.append(nav_row())
    return InlineKeyboardMarkup(rows)


def osm_category_keyboard(rows: list[dict] | None = None) -> InlineKeyboardMarkup:
    items = list(rows or [])[:LIST_LIMIT]
    buttons = [kb_btn(str(row.get("name") or "punto")[:40], f"live:ow:i:{i}") for i, row in enumerate(items)]
    grid = _pairs(buttons)
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


def live_region_keyboard(kind: str, region: str) -> InlineKeyboardMarkup:
    region_btns = [
        kb_btn(f"{cfg['emoji']} {cfg['title']}", f"live:{kind}:{key}") for key, cfg in REGIONS.items()
    ]
    rows = _pairs(region_btns)
    if kind == "heli":
        rows.append(
            [
                kb_btn("✈️ Tutti gli aerei", f"live:ac:{region}"),
                kb_btn("🔄 Aggiorna", f"live:heli:{region}"),
            ]
        )
    else:
        rows.append(
            [
                kb_btn("🚁 Solo elicotteri", f"live:heli:{region}"),
                kb_btn("🔄 Aggiorna", f"live:ac:{region}"),
            ]
        )
    rows.append([kb_btn("⚓ Navi", "live:ships"), kb_btn("🛰️ ISS", "live:iss")])
    rows.append([kb_btn("📡 Posizioni live", "home:live")])
    rows.append(nav_row())
    return InlineKeyboardMarkup(rows)


def live_misc_keyboard(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [kb_btn("🔄 Aggiorna", token), kb_btn("✈️ Aerei", "live:ac:it")],
            [kb_btn("⚓ Navi", "live:ships"), kb_btn("🛰️ ISS", "live:iss")],
            [kb_btn("📡 Posizioni live", "home:live")],
            nav_row(),
        ]
    )
