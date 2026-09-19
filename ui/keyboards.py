"""Tastiere inline del live: hub, zone, navi, ISS."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from services.live import REGIONS


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
            [kb_btn("🛰️ Mappa ISS", "live:iss"), kb_btn("🗺️ OSM Milano", "live:osm:milano")],
            [kb_btn("❓ Aiuto", "home:aiuto")],
        ]
    )


def osm_place_keyboard(place: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [kb_btn("🔄 Aggiorna", f"live:osm:{place}")],
            [
                kb_btn("✈️ Aeroporti", f"live:osm:{place}:aerodrome"),
                kb_btn("🚉 Stazioni", f"live:osm:{place}:station"),
            ],
            [kb_btn("🏥 Ospedali", f"live:osm:{place}:hospital")],
            [kb_btn("📡 Posizioni live", "home:live")],
            nav_row(),
        ]
    )


def osm_category_keyboard(place: str, category: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [kb_btn("🔄 Aggiorna", f"live:osm:{place}:{category}")],
            [
                kb_btn("✈️ Aeroporti", f"live:osm:{place}:aerodrome"),
                kb_btn("🚉 Stazioni", f"live:osm:{place}:station"),
            ],
            [kb_btn("🏥 Ospedali", f"live:osm:{place}:hospital")],
            [kb_btn("🗺️ Riepilogo OSM", f"live:osm:{place}")],
            [kb_btn("📡 Posizioni live", "home:live")],
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
