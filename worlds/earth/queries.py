"""Query EARTH."""

from __future__ import annotations

from typing import Any

from worlds.earth.service import run_earth

QUERIES = (
    {"id": "earthquakes", "emoji": "🌋", "title": "Terremoti"},
    {"id": "wildfires", "emoji": "🔥", "title": "Incendi"},
    {"id": "events", "emoji": "🌪️", "title": "Eventi naturali"},
    {"id": "flood", "emoji": "🌊", "title": "Fiumi / alluvioni"},
)
BY_ID = {item["id"]: item for item in QUERIES}


def get_query(query_id: str | None) -> dict[str, Any] | None:
    key = (query_id or "").strip().lower().split(":")[0]
    aliases = {"eq24": "earthquakes", "eq7": "earthquakes", "eqm4": "earthquakes", "fire": "wildfires"}
    key = aliases.get(key, key)
    return BY_ID.get(key)


def run_query(city: dict[str, Any], query_id: str) -> dict[str, Any]:
    return run_earth(city, query_id)
