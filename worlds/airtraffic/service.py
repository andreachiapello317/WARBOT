"""Servizio AIR TRAFFIC. Il client HTTP sta in services/live/adsb_client.py."""

from __future__ import annotations

from typing import Any

from services.live.aircraft import get_aircraft_nearby


def get_aircraft_in_area(lat: float, lon: float, radius_km: float | None = None) -> dict[str, Any]:
    return get_aircraft_nearby(lat, lon, radius_km)
