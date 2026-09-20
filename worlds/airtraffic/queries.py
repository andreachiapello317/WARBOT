"""Query AIR TRAFFIC. Una sola: Aerei LIVE via ADSB.lol."""

from __future__ import annotations

from typing import Any

from worlds.airtraffic.service import get_aircraft_in_area

QUERIES = (
    {
        "id": "aircraft",
        "emoji": "✈️",
        "title": "Aerei LIVE",
        "description": "Aerei sopra la zona",
        "radius_km": None,
        "mode": "list",
    },
)

BY_ID = {item["id"]: item for item in QUERIES}


def get_query(query_id: str | None) -> dict[str, Any] | None:
    key = (query_id or "").strip().lower()
    if key in {"live", "aerei", "zona"}:
        key = "aircraft"
    return BY_ID.get(key)


def run_aircraft(city: dict[str, Any], query_id: str = "aircraft") -> dict[str, Any]:
    meta = get_query(query_id) or BY_ID["aircraft"]
    radius = meta.get("radius_km")
    bundle = get_aircraft_in_area(float(city["lat"]), float(city["lon"]), radius)
    bundle["query"] = meta["id"]
    bundle["mode"] = meta["mode"]
    bundle["title"] = meta["title"]
    return bundle
