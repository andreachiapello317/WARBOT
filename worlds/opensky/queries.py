"""Query OpenSky. Solo API documentate: GET /states/all con bbox."""

from __future__ import annotations

from typing import Any

from services.live.aircraft import get_aircraft_nearby

# Query realmente supportate da OpenSky REST (state vectors in bbox).
# /flights/arrival e /flights/departure richiedono ICAO aeroporto, non lat/lon città:
# non sono esposte.
QUERIES = (
    {
        "id": "aircraft",
        "emoji": "✈️",
        "title": "Aerei LIVE",
        "description": "Aerei sopra la zona",
        "radius_km": None,
        "mode": "list",
    },
    {
        "id": "nearby",
        "emoji": "📍",
        "title": "Aerei vicini",
        "description": "Stesso endpoint, raggio 20 km",
        "radius_km": 20.0,
        "mode": "list",
    },
    {
        "id": "traffic",
        "emoji": "📡",
        "title": "Traffico aereo",
        "description": "Conteggio in volo / a terra sulla stessa risposta",
        "radius_km": None,
        "mode": "summary",
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
    bundle = get_aircraft_nearby(float(city["lat"]), float(city["lon"]), radius)
    bundle["query"] = meta["id"]
    bundle["mode"] = meta["mode"]
    bundle["title"] = meta["title"]
    return bundle
