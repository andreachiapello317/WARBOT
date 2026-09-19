"""Menu e tastiere del mondo OSM. Aprire il menu non esegue Overpass."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from core.session import city_label
from services.live.osm import CATEGORIES, LIST_LIMIT, NEAR_CATEGORIES, e
from worlds.osm.queries import engine_id, menu_queries, public_id


def kb(label: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(label, callback_data=data)


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


def world_nav_row(*, back: str = "world:list") -> list[InlineKeyboardButton]:
    return [
        kb("⬅️ OSM", "osm:menu") if back == "osm:menu" else kb("⬅️ Indietro", back),
        kb("🌍 Mondi", "world:list"),
        kb("📍 Cambia città", "city:ask"),
    ]


def menu_text(city: dict) -> str:
    name = city_label(city)
    lines = [
        "🗺️ <b>OSM WORLD</b>",
        f"📍 {e(name)}",
        "",
    ]
    for item in menu_queries():
        lines.append(f"{item['emoji']} {e(item['title'])}")
    return "\n".join(lines)


def menu_keyboard() -> InlineKeyboardMarkup:
    buttons = [kb(f"{item['emoji']} {item['title']}", item["callback"]) for item in menu_queries()]
    rows = _pairs(buttons)
    rows.append([kb("🗺️ Mappa", "osm:map")])
    rows.append(world_nav_row(back="world:list"))
    return InlineKeyboardMarkup(rows)


def results_keyboard(
    rows: list[dict] | None = None,
    *,
    page: int = 0,
    query_id: str | None = None,
    error: bool = False,
    filt: dict | None = None,
    nearby: bool = False,
) -> InlineKeyboardMarkup:
    pub = public_id(query_id) or query_id or "rail"
    engine = engine_id(query_id) or query_id
    if error:
        retry = f"osm:n:{pub}" if nearby else f"osm:{pub}"
        return InlineKeyboardMarkup(
            [
                [kb("🔄 Riprova", retry)],
                world_nav_row(back="osm:menu"),
            ]
        )
    start = max(0, page) * LIST_LIMIT
    items = list(rows or [])
    chunk = items[start : start + LIST_LIMIT]
    buttons = [kb(str(row.get("name") or "punto")[:40], f"osm:item:{start + i}") for i, row in enumerate(chunk)]
    grid = _pairs(buttons)
    filt = filt or {}
    if engine == "rail" and not nearby:
        main = filt.get("rail") != "all"
        ctr = filt.get("scope") == "ctr"
        grid.insert(
            0,
            [
                kb("· Principali" if main else "Principali", "osm:f:main"),
                kb("· Tutte" if not main else "Tutte", "osm:f:all"),
            ],
        )
        grid.insert(
            1,
            [
                kb("· Centro" if ctr else "Centro", "osm:f:ctr"),
                kb("· Tutta la città" if not ctr else "Tutta la città", "osm:f:wide"),
            ],
        )
    if engine == "aero" and not nearby:
        pax = filt.get("aero") != "any"
        near = filt.get("aero") == "near"
        grid.insert(
            0,
            [
                kb("· Passeggeri" if pax and not near else "Passeggeri", "osm:f:pax"),
                kb("· Tutti" if not pax and not near else "Tutti", "osm:f:any"),
                kb("· Vicino" if near else "Vicino", "osm:f:anear"),
            ],
        )
    extra: list[InlineKeyboardButton] = []
    if start + LIST_LIMIT < len(items):
        extra.append(kb("➡️ Altri", f"osm:{pub}:page:{page + 1}"))
    if page > 0:
        extra.append(kb("⬅️ Indietro", f"osm:{pub}:page:{page - 1}"))
    if extra:
        grid.append(extra)
    if nearby:
        grid.append([kb("🔎 Vicino", "osm:near"), kb("🌍 Zona", "osm:zone")])
    grid.append(world_nav_row(back="osm:menu"))
    return InlineKeyboardMarkup(grid)


def item_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [kb("📍 Dove si trova", "osm:imap"), kb("🗺️ Apri mappa", "osm:imap")],
            [kb("🏷️ Dettagli OSM", "osm:tags")],
            [kb("🔎 Cosa c'è vicino", "osm:near")],
            [kb("🌍 Esplora zona", "osm:zone")],
            [kb("📋 Lista", "osm:list")],
            world_nav_row(back="osm:menu"),
        ]
    )


def nearby_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        kb(f"{CATEGORIES[key]['emoji']} {CATEGORIES[key]['title']}", f"osm:n:{key}")
        for key in NEAR_CATEGORIES
    ]
    rows = _pairs(buttons)
    rows.append([kb("🗺️ Apri mappa", "osm:imap")])
    rows.append([kb("📋 Scheda", "osm:backi")])
    rows.append(world_nav_row(back="osm:menu"))
    return InlineKeyboardMarkup(rows)


def item_side_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [kb("📋 Scheda", "osm:backi"), kb("🔎 Vicino", "osm:near")],
            [kb("🗺️ Mappa", "osm:imap")],
            world_nav_row(back="osm:menu"),
        ]
    )
