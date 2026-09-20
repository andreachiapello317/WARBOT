"""Utility geografiche condivise. Un solo Haversine per tutti i mondi."""

from __future__ import annotations

import math
from datetime import datetime, timezone

EARTH_RADIUS_KM = 6371.0
KM_PER_DEG_LAT = 111.32
KT_TO_KMH = 1.852


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def bbox_from_radius(lat: float, lon: float, radius_km: float) -> tuple[float, float, float, float]:
    """(south, west, north, east)."""
    lat = max(-89.9, min(89.9, float(lat)))
    lon = float(lon)
    radius = max(1.0, float(radius_km))
    dlat = radius / KM_PER_DEG_LAT
    safe_cos = max(0.08, abs(math.cos(math.radians(lat))))
    dlon = radius / (KM_PER_DEG_LAT * safe_cos)
    return (
        max(-90.0, lat - dlat),
        max(-180.0, lon - dlon),
        min(90.0, lat + dlat),
        min(180.0, lon + dlon),
    )


def km_to_nm(radius_km: float) -> int:
    return max(1, min(250, int(round(float(radius_km) / KT_TO_KMH))))


def heading_from_velocity(vx: float, vy: float) -> float | None:
    if vx == 0 and vy == 0:
        return None
    ang = math.degrees(math.atan2(vx, vy)) % 360.0
    return ang


def solar_elevation_deg(lat: float, lon: float, when: datetime | None = None) -> float:
    """Elevazione solare approssimata (gradi). Calcolo locale, non un'API."""
    dt = when or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    n = dt.timetuple().tm_yday
    hour = dt.hour + dt.minute / 60.0 + dt.second / 3600.0
    decl = 23.44 * math.sin(math.radians(360.0 / 365.0 * (n - 81)))
    lst = (hour - 12.0) * 15.0 + lon
    lat_r = math.radians(lat)
    dec_r = math.radians(decl)
    ha_r = math.radians(lst)
    sin_el = math.sin(lat_r) * math.sin(dec_r) + math.cos(lat_r) * math.cos(dec_r) * math.cos(ha_r)
    return math.degrees(math.asin(max(-1.0, min(1.0, sin_el))))
