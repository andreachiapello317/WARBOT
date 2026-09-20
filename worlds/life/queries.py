"""Query CITY LIFE. Menu senza chiamate API."""

from __future__ import annotations

from typing import Any

from worlds.life.service import run_life

QUERIES = (
    {"id": "near", "emoji": "📍", "title": "Vicino a me"},
    {"id": "mobility", "emoji": "🚦", "title": "Mobilità"},
    {"id": "safety", "emoji": "🏥", "title": "Sicurezza"},
    {"id": "culture", "emoji": "🎭", "title": "Vita in città"},
    {"id": "services", "emoji": "⛲", "title": "Servizi"},
    {"id": "walk", "emoji": "🚶", "title": "Passeggiata"},
    {"id": "history", "emoji": "📊", "title": "Storico"},
    {"id": "compare", "emoji": "⚖️", "title": "Confronta"},
)
BY_ID = {item["id"]: item for item in QUERIES}


def get_query(query_id: str | None) -> dict[str, Any] | None:
    key = (query_id or "").strip().lower().split(":")[0]
    aliases = {
        "vicino": "near",
        "traffico": "mobility",
        "allerte": "safety",
        "eventi": "culture",
        "fontanelle": "services",
        "passeggiata": "walk",
        "storico": "history",
        "confronto": "compare",
    }
    key = aliases.get(key, key)
    return BY_ID.get(key)


def run_query(city: dict[str, Any], query_id: str, *, other: dict[str, Any] | None = None) -> dict[str, Any]:
    return run_life(city, query_id, other=other)
