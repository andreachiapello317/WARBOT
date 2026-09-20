"""Query OSM WORLD: wrapper sul motore Overpass esistente. Nessun ADSB.lol."""

from __future__ import annotations

from typing import Any

from services.live.osm import (
    CATEGORIES,
    WORLD_CATEGORIES,
    build_airport_query,
    build_hospital_query,
    build_osm_query,
    build_port_query,
    build_query,
    peek,
    resolve_category,
    search,
    search_near,
)

# Callback pubblici → chiave motore già esistente.
QUERY_IDS = (
    ("airports", "aero"),
    ("rail", "rail"),
    ("hospitals", "hosp"),
    ("ports", "port"),
    ("stadiums", "stad"),
    ("shopping", "mall"),
    ("important", "land"),
)

PUBLIC_TO_ENGINE = {public: engine for public, engine in QUERY_IDS}
ENGINE_TO_PUBLIC = {engine: public for public, engine in QUERY_IDS}


def public_id(raw: str | None) -> str | None:
    key = (raw or "").strip().lower()
    if key in PUBLIC_TO_ENGINE:
        return key
    engine = resolve_category(key)
    if engine and engine in ENGINE_TO_PUBLIC:
        return ENGINE_TO_PUBLIC[engine]
    return None


def engine_id(raw: str | None) -> str | None:
    pub = public_id(raw)
    if pub:
        return PUBLIC_TO_ENGINE[pub]
    return resolve_category(raw)


def menu_queries() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for public, engine in QUERY_IDS:
        meta = CATEGORIES[engine]
        items.append(
            {
                "id": public,
                "engine": engine,
                "emoji": meta["emoji"],
                "title": meta["title"],
                "callback": f"osm:{public}",
            }
        )
    return items


def build_rail_query(bbox: Any, **kwargs: Any) -> str:
    return build_osm_query("rail", bbox, **kwargs)


def build_shopping_query(bbox: Any, **kwargs: Any) -> str:
    return build_osm_query("mall", bbox, **kwargs)


def build_important_query(bbox: Any, **kwargs: Any) -> str:
    return build_osm_query("land", bbox, **kwargs)


def build_stadium_query(bbox: Any, **kwargs: Any) -> str:
    return build_osm_query("stad", bbox, **kwargs)


def run_query(
    city: dict[str, Any],
    query_id: str,
    *,
    extra: str = "",
    radius_m: int | None = None,
    min_score: int | None = None,
) -> dict[str, Any]:
    cat = engine_id(query_id)
    if not cat:
        return {"ok": False, "error": f"query OSM sconosciuta: {query_id}", "rows": []}
    return search(
        city["bbox"],
        cat,
        center=(city["lat"], city["lon"]),
        hint=str(city.get("name") or ""),
        extra=extra,
        radius_m=radius_m,
        min_score=min_score,
    )


def peek_query(
    city: dict[str, Any],
    query_id: str,
    *,
    extra: str = "",
    radius_m: int | None = None,
) -> dict[str, Any] | None:
    cat = engine_id(query_id)
    if not cat:
        return None
    return peek(
        city["bbox"],
        cat,
        center=(city["lat"], city["lon"]),
        extra=extra,
        radius_m=radius_m,
    )


def run_near(lat: float, lon: float, query_id: str, *, hint: str = "") -> dict[str, Any]:
    cat = engine_id(query_id) or resolve_category(query_id)
    if not cat:
        return {"ok": False, "error": f"query OSM sconosciuta: {query_id}", "rows": []}
    return search_near(lat, lon, cat, hint=hint)


__all__ = [
    "QUERY_IDS",
    "WORLD_CATEGORIES",
    "build_airport_query",
    "build_hospital_query",
    "build_important_query",
    "build_osm_query",
    "build_port_query",
    "build_query",
    "build_rail_query",
    "build_shopping_query",
    "build_stadium_query",
    "engine_id",
    "menu_queries",
    "peek_query",
    "public_id",
    "run_near",
    "run_query",
]
