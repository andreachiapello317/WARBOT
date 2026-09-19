"""LIVE DATA: fonti dinamiche, separate da OSM WORLD (luoghi e infrastrutture).

Aggiungere navi, satelliti, meteo, ecc. qui — senza toccare OpenSky né Overpass.
"""

from __future__ import annotations

from typing import Any

# Callback Telegram: live:ow:<id>
LIVE_FEEDS: tuple[dict[str, str], ...] = (
    {
        "id": "air",
        "emoji": "✈️",
        "title": "Aerei LIVE",
        "callback": "live:ow:air",
    },
)


def live_feed(feed_id: str) -> dict[str, str] | None:
    key = (feed_id or "").strip().lower()
    for item in LIVE_FEEDS:
        if item["id"] == key:
            return item
    return None


def live_menu_lines() -> list[str]:
    return [f"{item['emoji']} {item['title']}" for item in LIVE_FEEDS]


def live_menu_items() -> list[dict[str, Any]]:
    return [dict(item) for item in LIVE_FEEDS]
