"""CityContext + sessione utente. Un solo geocoding, condiviso da tutti i mondi."""

from __future__ import annotations

import logging
import time
from typing import Any

from telegram.ext import ContextTypes

log = logging.getLogger("warbot.city")

CITY_KEY = "city"
WORLD_KEY = "world"
SCREEN_KEY = "screen"
WAITING_KEY = "waiting_city"
HITS_KEY = "city_hits"
OSM_STATE_KEY = "osm_state"
AIRTRAFFIC_STATE_KEY = "airtraffic_state"

DYNAMIC_STATE_KEYS = (
    OSM_STATE_KEY,
    AIRTRAFFIC_STATE_KEY,
    "sky_state",
    "earth_state",
    "space_state",
)

SCREEN_CITY = "city"
SCREEN_HITS = "hits"
SCREEN_WORLDS = "worlds"
SCREEN_OSM_MENU = "osm_menu"
SCREEN_OSM_RESULTS = "osm_results"
SCREEN_OSM_ITEM = "osm_item"
SCREEN_OSM_NEAR = "osm_near"
SCREEN_AIRTRAFFIC_MENU = "airtraffic_menu"
SCREEN_AIRTRAFFIC_RESULTS = "airtraffic_results"


def city_from_hit(hit: dict[str, Any]) -> dict[str, Any]:
    """Normalizza un hit del geocoder nel CityContext condiviso."""
    lat = float(hit["lat"])
    lon = float(hit["lon"])
    name = hit.get("name") or hit.get("display") or ""
    display = hit.get("display") or hit.get("name") or ""
    country = hit.get("country") or ""
    return {
        "name": name,
        "display": display,
        "display_name": display,
        "lat": lat,
        "lon": lon,
        "latitude": lat,
        "longitude": lon,
        "bbox": hit.get("bbox"),
        "country": country,
        "country_code": str(hit.get("country_code") or "").lower(),
        "state": hit.get("state") or "",
        "region": hit.get("state") or hit.get("region") or "",
        "municipality": hit.get("municipality") or hit.get("city") or "",
        "timezone": hit.get("timezone") or "",
        "bbox_note": hit.get("bbox_note") or "",
        "source": hit.get("source") or "",
        "geocoded_at": hit.get("geocoded_at") or time.time(),
        "geocoding": {
            "source": hit.get("source") or "",
            "country": country,
            "country_code": str(hit.get("country_code") or "").lower(),
            "state": hit.get("state") or "",
            "bbox_note": hit.get("bbox_note") or "",
        },
    }


def get_city(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any] | None:
    city = context.user_data.get(CITY_KEY)
    if isinstance(city, dict) and "lat" in city and "lon" in city:
        return city
    legacy = context.user_data.get("osm_place")
    if isinstance(legacy, dict) and "lat" in legacy:
        set_city(context, city_from_hit(legacy))
        return get_city(context)
    return None


def _clear_dynamic(context: ContextTypes.DEFAULT_TYPE) -> None:
    for key in DYNAMIC_STATE_KEYS:
        context.user_data.pop(key, None)


def set_city(context: ContextTypes.DEFAULT_TYPE, hit: dict[str, Any]) -> dict[str, Any]:
    city = city_from_hit(hit)
    context.user_data[CITY_KEY] = city
    context.user_data["osm_place"] = city
    context.user_data[WAITING_KEY] = False
    _clear_dynamic(context)
    log.info("[CITY] resolved=%s lat=%s lon=%s", city.get("name"), city.get("lat"), city.get("lon"))
    return city


def clear_city(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(CITY_KEY, None)
    context.user_data.pop("osm_place", None)
    context.user_data.pop(HITS_KEY, None)
    context.user_data.pop(WORLD_KEY, None)
    _clear_dynamic(context)
    context.user_data[WAITING_KEY] = True
    set_screen(context, SCREEN_CITY)


def city_label(city: dict[str, Any] | None) -> str:
    if not city:
        return ""
    raw = str(city.get("name") or city.get("display") or "").split(",")[0].strip()
    return raw or "qui"


def waiting_city(context: ContextTypes.DEFAULT_TYPE) -> bool:
    if WAITING_KEY in context.user_data:
        return bool(context.user_data.get(WAITING_KEY))
    return get_city(context) is None


def ask_city(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data[WAITING_KEY] = True
    set_screen(context, SCREEN_CITY)


def set_world(context: ContextTypes.DEFAULT_TYPE, world_id: str | None) -> None:
    if world_id:
        context.user_data[WORLD_KEY] = world_id
        log.info("[WORLD] selected=%s city=%s", world_id, city_label(get_city(context)))
    else:
        context.user_data.pop(WORLD_KEY, None)


def get_world_id(context: ContextTypes.DEFAULT_TYPE) -> str | None:
    value = context.user_data.get(WORLD_KEY)
    return str(value) if value else None


def set_screen(context: ContextTypes.DEFAULT_TYPE, screen: str) -> None:
    context.user_data[SCREEN_KEY] = screen


def get_screen(context: ContextTypes.DEFAULT_TYPE) -> str:
    return str(context.user_data.get(SCREEN_KEY) or SCREEN_CITY)


def world_state(context: ContextTypes.DEFAULT_TYPE, world_id: str) -> dict[str, Any]:
    key = f"{world_id}_state"
    raw = context.user_data.get(key)
    if not isinstance(raw, dict):
        raw = {}
        context.user_data[key] = raw
    return raw


def osm_state(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any]:
    return world_state(context, "osm")


def airtraffic_state(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any]:
    return world_state(context, "airtraffic")


def set_hits(context: ContextTypes.DEFAULT_TYPE, hits: list[dict[str, Any]]) -> None:
    context.user_data[HITS_KEY] = list(hits)


def get_hits(context: ContextTypes.DEFAULT_TYPE) -> list[dict[str, Any]]:
    raw = context.user_data.get(HITS_KEY)
    return list(raw) if isinstance(raw, list) else []
