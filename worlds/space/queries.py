"""Query SPACE."""

from __future__ import annotations

from typing import Any

from worlds.space.service import run_space

QUERIES = (
    {"id": "satellites", "emoji": "🛰️", "title": "Satelliti"},
    {"id": "iss", "emoji": "🌍", "title": "ISS"},
    {"id": "starlink", "emoji": "⭐", "title": "Starlink"},
    {"id": "aurora", "emoji": "🌌", "title": "Aurora"},
    {"id": "meteors", "emoji": "☄️", "title": "Meteore"},
)
BY_ID = {item["id"]: item for item in QUERIES}


def get_query(query_id: str | None) -> dict[str, Any] | None:
    key = (query_id or "").strip().lower().split(":")[0]
    aliases = {"kp": "aurora", "bolidi": "meteors", "fireball": "meteors"}
    key = aliases.get(key, key)
    return BY_ID.get(key)


def run_query(city: dict[str, Any], query_id: str) -> dict[str, Any]:
    return run_space(city, query_id)
