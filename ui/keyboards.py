"""Tastiere inline OSM WORLD."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from services.live.osm import CATEGORIES, LIST_LIMIT, NEAR_CATEGORIES, WORLD_CATEGORIES


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
    cat: str | None = None,
    filt: dict | None = None,
    nearby: bool = False,
) -> InlineKeyboardMarkup:
    if error_cat:
        retry = f"live:ow:n:{error_cat}" if nearby else f"live:ow:c:{error_cat}"
        return InlineKeyboardMarkup(
            [
                [kb_btn("🔄 Riprova", retry)],
                [kb_btn("📍 Località", "live:ow:here")],
                nav_row(),
            ]
        )
    start = max(0, page) * LIST_LIMIT
    items = list(rows or [])
    chunk = items[start : start + LIST_LIMIT]
    buttons = [kb_btn(str(row.get("name") or "punto")[:40], f"live:ow:i:{start + i}") for i, row in enumerate(chunk)]
    grid = _pairs(buttons)
    filt = filt or {}
    if cat == "rail" and not nearby:
        main = filt.get("rail") != "all"
        ctr = filt.get("scope") == "ctr"
        grid.insert(
            0,
            [
                kb_btn("· Principali" if main else "Principali", "live:ow:f:main"),
                kb_btn("· Tutte" if not main else "Tutte", "live:ow:f:all"),
            ],
        )
        grid.insert(
            1,
            [
                kb_btn("· Centro" if ctr else "Centro", "live:ow:f:ctr"),
                kb_btn("· Tutta la città" if not ctr else "Tutta la città", "live:ow:f:wide"),
            ],
        )
    if cat == "aero" and not nearby:
        pax = filt.get("aero") != "any"
        near = filt.get("aero") == "near"
        grid.insert(
            0,
            [
                kb_btn("· Passeggeri" if pax and not near else "Passeggeri", "live:ow:f:pax"),
                kb_btn("· Tutti" if not pax and not near else "Tutti", "live:ow:f:any"),
                kb_btn("· Vicino" if near else "Vicino", "live:ow:f:anear"),
            ],
        )
    extra: list[InlineKeyboardButton] = []
    if start + LIST_LIMIT < len(items):
        extra.append(kb_btn("➡️ Altri risultati", "live:ow:more"))
    if page > 0:
        extra.append(kb_btn("⬅️ Indietro", "live:ow:pg"))
    if extra:
        grid.append(extra)
    if nearby:
        grid.append([kb_btn("🔎 Vicino", "live:ow:near"), kb_btn("🌍 Zona", "live:ow:zone")])
    grid.append([kb_btn("📍 Località", "live:ow:here"), kb_btn("🗺️ Mappa", "live:ow:map")])
    grid.append([kb_btn("🔎 Cerca un'altra località", "live:ow")])
    grid.append(nav_row())
    return InlineKeyboardMarkup(grid)


def osm_item_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [kb_btn("📍 Dove si trova", "live:ow:imap"), kb_btn("🗺️ Apri mappa", "live:ow:imap")],
            [kb_btn("🏷️ Dettagli OSM", "live:ow:osm")],
            [kb_btn("🔎 Cosa c'è vicino", "live:ow:near")],
            [kb_btn("🌍 Esplora zona", "live:ow:zone")],
            [kb_btn("📋 Lista", "live:ow:list"), kb_btn("📍 Località", "live:ow:here")],
            nav_row(),
        ]
    )


def osm_nearby_keyboard(*, zone: bool = False) -> InlineKeyboardMarkup:
    buttons = [
        kb_btn(f"{CATEGORIES[key]['emoji']} {CATEGORIES[key]['title']}", f"live:ow:n:{key}")
        for key in NEAR_CATEGORIES
    ]
    rows = _pairs(buttons)
    rows.append([kb_btn("🗺️ Apri mappa", "live:ow:imap")])
    rows.append([kb_btn("📋 Scheda", "live:ow:backi"), kb_btn("📍 Località", "live:ow:here")])
    rows.append(nav_row())
    return InlineKeyboardMarkup(rows)


def osm_item_side_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [kb_btn("📋 Scheda", "live:ow:backi"), kb_btn("🔎 Vicino", "live:ow:near")],
            [kb_btn("🗺️ Mappa", "live:ow:imap"), kb_btn("📍 Località", "live:ow:here")],
            nav_row(),
        ]
    )
