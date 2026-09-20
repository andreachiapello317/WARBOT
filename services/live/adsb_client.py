"""Client ADS-B pubblico: airplanes.live primario, ADSB.lol fallback.

Documentazione:
  https://airplanes.live/api-docs/
  GET https://api.airplanes.live/v2/point/{lat}/{lon}/{radius}  radius NM 0–250
  https://api.adsb.lol/api/openapi.json
  GET https://api.adsb.lol/v2/lat/{lat}/lon/{lon}/dist/{radius}  radius NM 0–250

Nessuna credenziale. Se airplanes.live risponde 403/timeout, si usa ADSB.lol.
"""

from __future__ import annotations

import logging
from typing import Any

from core.http import http_get_retry

log = logging.getLogger("warbot.airtraffic")

AIRPLANES_ROOT = "https://api.airplanes.live"
ADSB_ROOT = "https://api.adsb.lol"
USER_AGENT = "WARBOT/1.0 (AIR TRAFFIC; public ADS-B)"
TIMEOUT_S = 10


def point_url(lat: float, lon: float, radius_nm: int) -> str:
    """URL ADSB.lol (usato nei test e come fallback)."""
    return adsb_url(lat, lon, radius_nm)


def airplanes_url(lat: float, lon: float, radius_nm: int) -> str:
    radius = max(0, min(250, int(radius_nm)))
    lat = max(-90.0, min(90.0, float(lat)))
    lon = max(-180.0, min(180.0, float(lon)))
    return f"{AIRPLANES_ROOT}/v2/point/{lat:.5f}/{lon:.5f}/{radius}"


def adsb_url(lat: float, lon: float, radius_nm: int) -> str:
    radius = max(0, min(250, int(radius_nm)))
    lat = max(-90.0, min(90.0, float(lat)))
    lon = max(-180.0, min(180.0, float(lon)))
    return f"{ADSB_ROOT}/v2/lat/{lat:.5f}/lon/{lon:.5f}/dist/{radius}"


def _one(url: str) -> tuple[int, bytes, dict[str, str], float]:
    return http_get_retry(url, timeout=TIMEOUT_S, user_agent=USER_AGENT)


def fetch_nearby(lat: float, lon: float, radius_nm: int) -> tuple[int, bytes, dict[str, str], float, str]:
    """Prova airplanes.live, poi ADSB.lol. Un solo fallback. Nessun polling."""
    primary = airplanes_url(lat, lon, radius_nm)
    http, body, hdrs, ms = _one(primary)
    if http == 200 and body:
        log.info("[AIRTRAFFIC] provider=airplanes.live")
        return http, body, hdrs, ms, "airplanes.live"
    log.info("[AIRTRAFFIC] fallback=adsb.lol primary_http=%s", http if http > 0 else "000")
    secondary = adsb_url(lat, lon, radius_nm)
    http2, body2, hdrs2, ms2 = _one(secondary)
    return http2, body2, hdrs2, ms + ms2, "adsb.lol"


def get_nearby(lat: float, lon: float, radius_nm: int) -> tuple[int, bytes, dict[str, str], float]:
    http, body, hdrs, ms, _provider = fetch_nearby(lat, lon, radius_nm)
    return http, body, hdrs, ms


def reset_adsb_client() -> None:
    return None
