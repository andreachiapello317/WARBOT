"""Registry centrale dei mondi. Il core Telegram non conosce le query interne.

I metadati sono statici (menu città). Gli handler si caricano al primo uso,
così worlds.city può costruire il WORLD MENU senza import circolari.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from telegram import Update
from telegram.ext import ContextTypes

HandleFn = Callable[[Update, ContextTypes.DEFAULT_TYPE, list[str]], Awaitable[None]]
MenuFn = Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]

# Terzo mondo: nel repo non esiste un terzo mondo Telegram già implementato.
# Non se ne inventa uno. Solo OSM + AIR TRAFFIC.
WORLD_META: tuple[dict[str, str], ...] = (
    {
        "id": "osm",
        "title": "OSM WORLD",
        "icon": "🗺️",
        "description": "Luoghi e infrastrutture OpenStreetMap",
    },
    {
        "id": "airtraffic",
        "title": "AIR TRAFFIC",
        "icon": "✈️",
        "description": "Aerei LIVE via ADSB.lol",
    },
)


@dataclass(frozen=True)
class World:
    id: str
    title: str
    icon: str
    description: str
    handle: HandleFn
    show_menu: MenuFn


_loaded: dict[str, World] = {}


def _ensure() -> None:
    if _loaded:
        return
    from worlds.airtraffic.handler import handle as air_handle
    from worlds.airtraffic.handler import show_menu as air_menu
    from worlds.osm.handler import handle as osm_handle
    from worlds.osm.handler import show_menu as osm_menu

    handlers = {
        "osm": (osm_handle, osm_menu),
        "airtraffic": (air_handle, air_menu),
    }
    for meta in WORLD_META:
        handle, menu = handlers[meta["id"]]
        _loaded[meta["id"]] = World(
            id=meta["id"],
            title=meta["title"],
            icon=meta["icon"],
            description=meta["description"],
            handle=handle,
            show_menu=menu,
        )


def get_world(world_id: str | None) -> World | None:
    if not world_id:
        return None
    _ensure()
    return _loaded.get(world_id.strip().lower())


def world_menu_items() -> list[dict[str, Any]]:
    return [
        {
            "id": item["id"],
            "title": item["title"],
            "icon": item["icon"],
            "description": item["description"],
            "callback": f"world:{item['id']}",
        }
        for item in WORLD_META
    ]


def parse_callback(data: str) -> tuple[str, list[str]]:
    bits = [part for part in (data or "").split(":") if part != ""]
    if not bits:
        return "", []
    return bits[0], bits[1:]


WORLDS = WORLD_META
