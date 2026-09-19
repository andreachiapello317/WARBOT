"""Servizio OpenSky per il mondo Telegram. Nessuna logica di auth qui."""

from __future__ import annotations

from typing import Any

from services.live.aircraft import get_aircraft_nearby
from services.live.opensky_client import get_opensky_client


def client():
    return get_opensky_client()


def get_aircraft_in_bbox(lat: float, lon: float, radius_km: float | None = None) -> dict[str, Any]:
    return get_aircraft_nearby(lat, lon, radius_km)
