"""Query Overpass per CITY LIFE. Non tocca le categorie di OSM WORLD."""

from __future__ import annotations

import logging
import time
from typing import Any

from core.geo import haversine_km
from services.live.osm import overpass

log = logging.getLogger("warbot.life")

CACHE_TTL = 180
_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}

FILTERS: dict[str, tuple[str, ...]] = {
    "mobility": (
        "[highway=bus_stop]",
        "[railway=tram_stop]",
        "[railway=subway_entrance]",
        "[station=subway]",
        "[public_transport=station]",
        "[amenity=bicycle_rental]",
        "[amenity=car_sharing]",
        "[amenity=kick-scooter-rental]",
        "[amenity=parking]",
        '["contact:webcam"]',
        "[webcam]",
        '[man_made=surveillance]["camera:type"="webcam"]',
    ),
    "safety": (
        "[amenity=hospital]",
        "[amenity=clinic]",
        "[amenity=doctors]",
        "[amenity=pharmacy]",
        "[emergency=yes]",
    ),
    "culture": (
        "[amenity=cinema]",
        "[amenity=theatre]",
        "[amenity=marketplace]",
        "[amenity=restaurant]",
        "[amenity=cafe]",
        "[amenity=bar]",
        "[amenity=fast_food]",
        "[tourism=museum]",
        "[tourism=attraction]",
        "[tourism=gallery]",
        "[historic=monument]",
        "[leisure=park]",
        "[leisure=stadium]",
    ),
    "services": (
        "[amenity=drinking_water]",
        "[amenity=fountain]",
        "[amenity=toilets]",
        "[internet_access=wlan]",
        "[amenity=internet_cafe]",
        '["contact:webcam"]',
        "[webcam]",
        '[man_made=surveillance]["camera:type"="webcam"]',
    ),
    "walk": (
        "[amenity=drinking_water]",
        "[amenity=fountain]",
        "[amenity=toilets]",
        "[amenity=bench]",
        "[amenity=cafe]",
        "[tourism=viewpoint]",
        "[tourism=artwork]",
        "[tourism=attraction]",
        "[leisure=park]",
        "[highway=bus_stop]",
        "[amenity=pharmacy]",
    ),
    "near": (
        "[amenity=pharmacy]",
        "[amenity=hospital]",
        "[amenity=parking]",
        "[amenity=bicycle_rental]",
        "[amenity=drinking_water]",
        "[amenity=restaurant]",
        "[amenity=cafe]",
        "[amenity=cinema]",
        "[amenity=theatre]",
        "[highway=bus_stop]",
        "[railway=tram_stop]",
        "[railway=subway_entrance]",
        "[internet_access=wlan]",
        "[tourism=museum]",
        "[tourism=attraction]",
        "[amenity=marketplace]",
    ),
}

RADIUS_M = {
    "near": 1200,
    "mobility": 2500,
    "safety": 3500,
    "culture": 2000,
    "services": 1500,
    "walk": 1200,
}


def classify(tags: dict[str, Any]) -> str:
    amenity = str(tags.get("amenity") or "")
    tourism = str(tags.get("tourism") or "")
    railway = str(tags.get("railway") or "")
    highway = str(tags.get("highway") or "")
    leisure = str(tags.get("leisure") or "")
    historic = str(tags.get("historic") or "")
    if tags.get("contact:webcam") or tags.get("webcam") or tags.get("camera:type") == "webcam":
        return "webcam"
    if amenity == "parking":
        return "parking"
    if amenity == "bicycle_rental":
        return "bike"
    if amenity == "car_sharing":
        return "car"
    if amenity == "kick-scooter-rental":
        return "scooter"
    if amenity == "pharmacy":
        return "pharmacy"
    if amenity in {"hospital", "clinic", "doctors"} or tags.get("emergency") == "yes":
        return "hospital"
    if amenity in {"drinking_water", "fountain"}:
        return "water"
    if amenity == "toilets":
        return "toilets"
    if amenity == "bench":
        return "bench"
    if tags.get("internet_access") == "wlan" or amenity == "internet_cafe":
        return "wifi"
    if amenity == "restaurant":
        return "restaurant"
    if amenity in {"cafe", "bar", "fast_food"}:
        return "cafe"
    if amenity == "cinema":
        return "cinema"
    if amenity == "theatre":
        return "theatre"
    if amenity == "marketplace":
        return "market"
    if tourism == "museum" or tourism == "gallery":
        return "museum"
    if tourism in {"attraction", "artwork"} or historic == "monument":
        return "attraction"
    if tourism == "viewpoint":
        return "viewpoint"
    if leisure == "park":
        return "park"
    if leisure == "stadium":
        return "stadium"
    if highway == "bus_stop":
        return "bus"
    if railway == "tram_stop":
        return "tram"
    if railway == "subway_entrance" or tags.get("station") == "subway":
        return "metro"
    if tags.get("public_transport") == "station":
        return "stop"
    return "poi"


LABELS = {
    "parking": "Parcheggio",
    "bike": "Bici sharing",
    "car": "Auto sharing",
    "scooter": "Monopattini",
    "pharmacy": "Farmacia",
    "hospital": "Ospedale / PS",
    "water": "Fontanella",
    "toilets": "Bagni",
    "bench": "Panchina",
    "wifi": "WiFi",
    "restaurant": "Ristorante",
    "cafe": "Locale",
    "cinema": "Cinema",
    "theatre": "Teatro",
    "market": "Mercato",
    "museum": "Museo",
    "attraction": "Attrazione",
    "viewpoint": "Belvedere",
    "park": "Parco",
    "stadium": "Stadio",
    "bus": "Bus",
    "tram": "Tram",
    "metro": "Metro",
    "stop": "Fermata",
    "webcam": "Webcam",
    "poi": "Luogo",
}


def _tag(tags: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = tags.get(key)
        if value:
            return str(value).strip()
    return ""


def _coords(el: dict[str, Any]) -> tuple[float, float] | None:
    lat, lon = el.get("lat"), el.get("lon")
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        return float(lat), float(lon)
    center = el.get("center") or {}
    lat, lon = center.get("lat"), center.get("lon")
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        return float(lat), float(lon)
    return None


def build_around_ql(lat: float, lon: float, radius_m: int, filters: tuple[str, ...], *, timeout: int = 20, limit: int = 80) -> str:
    bits = "\n".join(f"  nwr(around:{int(radius_m)},{lat:.5f},{lon:.5f}){flt};" for flt in filters)
    return f"[out:json][timeout:{timeout}];\n(\n{bits}\n);\nout center {int(limit)};"


def normalize_elements(
    payload: dict[str, Any],
    *,
    lat: float,
    lon: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for el in payload.get("elements") or []:
        if not isinstance(el, dict):
            continue
        coords = _coords(el)
        if coords is None:
            continue
        elat, elon = coords
        tags = el.get("tags") if isinstance(el.get("tags"), dict) else {}
        group = classify(tags)
        name = _tag(tags, "name:it", "name", "official_name", "ref") or LABELS.get(group, "senza nome")
        key = f"{round(elat, 5)}:{round(elon, 5)}:{name.lower()}"
        if key in seen:
            continue
        seen.add(key)
        webcam = _tag(tags, "contact:webcam", "webcam")
        website = _tag(tags, "website", "contact:website", "url")
        rows.append(
            {
                "id": f"{el.get('type')}/{el.get('id')}",
                "name": name,
                "lat": elat,
                "lon": elon,
                "group": group,
                "kind": LABELS.get(group, "Luogo"),
                "distance_km": haversine_km(lat, lon, elat, elon),
                "opening_hours": _tag(tags, "opening_hours"),
                "operator": _tag(tags, "operator", "brand", "network"),
                "capacity": _tag(tags, "capacity"),
                "cuisine": _tag(tags, "cuisine"),
                "website": website,
                "webcam": webcam,
                "phone": _tag(tags, "phone", "contact:phone"),
            }
        )
    rows.sort(key=lambda r: (float(r.get("distance_km") or 9e9), str(r.get("name") or "")))
    return rows


def search_around(lat: float, lon: float, kind: str) -> dict[str, Any]:
    filters = FILTERS.get(kind)
    if not filters:
        return {"ok": False, "code": "unavailable", "rows": [], "kind": kind}
    radius = RADIUS_M.get(kind, 2000)
    cache_key = f"life:{kind}:{lat:.3f}:{lon:.3f}:{radius}"
    hit = _cache.get(cache_key)
    if hit and time.time() - hit[0] < CACHE_TTL:
        return {"ok": True, "kind": kind, "rows": list(hit[1]), "cached": True, "radius_m": radius}
    ql = build_around_ql(lat, lon, radius, filters)
    payload = overpass(ql)
    if not payload.get("ok"):
        log.info("[LIFE] overpass kind=%s fail=%s", kind, payload.get("error"))
        return {
            "ok": False,
            "code": "unavailable",
            "error": payload.get("error"),
            "rows": [],
            "kind": kind,
            "radius_m": radius,
        }
    rows = normalize_elements(payload, lat=lat, lon=lon)
    _cache[cache_key] = (time.time(), rows)
    log.info("[LIFE] overpass kind=%s n=%s radius_m=%s", kind, len(rows), radius)
    return {"ok": True, "kind": kind, "rows": rows, "radius_m": radius, "cached": False}
