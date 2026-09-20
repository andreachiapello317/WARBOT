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
        "description": "Aerei LIVE intorno alla città",
    },
    {
        "id": "sky",
        "title": "SKY",
        "icon": "🌤️",
        "description": "Meteo, aria, mare, sole",
    },
    {
        "id": "earth",
        "title": "EARTH",
        "icon": "🌋",
        "description": "Terremoti, incendi, eventi, fiumi",
    },
    {
        "id": "space",
        "title": "SPACE",
        "icon": "🛰️",
        "description": "ISS, Starlink, satelliti visibili",
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
    from worlds.earth.handler import handle as earth_handle
    from worlds.earth.handler import show_menu as earth_menu
    from worlds.osm.handler import handle as osm_handle
    from worlds.osm.handler import show_menu as osm_menu
    from worlds.sky.handler import handle as sky_handle
    from worlds.sky.handler import show_menu as sky_menu
    from worlds.space.handler import handle as space_handle
    from worlds.space.handler import show_menu as space_menu

    handlers = {
        "osm": (osm_handle, osm_menu),
        "airtraffic": (air_handle, air_menu),
        "sky": (sky_handle, sky_menu),
        "earth": (earth_handle, earth_menu),
        "space": (space_handle, space_menu),
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


def world_ids() -> tuple[str, ...]:
    return tuple(item["id"] for item in WORLD_META)


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


def callback_pattern() -> str:
    prefixes = "|".join(("city", "world", "nav", "home", "live") + world_ids())
    return rf"^({prefixes}):"


WORLDS = WORLD_META
