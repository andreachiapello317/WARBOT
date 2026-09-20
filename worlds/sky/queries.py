"""Query SKY. Open-Meteo, nessuna chiamata sul menu."""

from __future__ import annotations

from typing import Any

from worlds.sky.service import run_sky

QUERIES = (
    {"id": "weather", "emoji": "🌤️", "title": "Meteo"},
    {"id": "air", "emoji": "🌬️", "title": "Qualità dell'aria"},
    {"id": "pollen", "emoji": "🌾", "title": "Pollini"},
    {"id": "marine", "emoji": "🌊", "title": "Mare"},
    {"id": "sun", "emoji": "☀️", "title": "Sole"},
)
BY_ID = {item["id"]: item for item in QUERIES}


def get_query(query_id: str | None) -> dict[str, Any] | None:
    key = (query_id or "").strip().lower().split(":")[0]
    return BY_ID.get(key)


def run_query(city: dict[str, Any], query_id: str) -> dict[str, Any]:
    return run_sky(city, query_id)
