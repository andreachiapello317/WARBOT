"""Client HTTP pubblico ADSB.lol. Nessuna credenziale.

Documentazione: https://api.adsb.lol/api/openapi.json
Endpoint geografico:
  GET /v2/lat/{lat}/lon/{lon}/dist/{radius}
  radius intero in miglia nautiche, 0–250.
"""

from __future__ import annotations

import logging
import socket
import time
import urllib.error
import urllib.request
from typing import Any

log = logging.getLogger("warbot.airtraffic")

ADSB_ROOT = "https://api.adsb.lol"
USER_AGENT = "WARBOT/1.0 (AIR TRAFFIC; adsb.lol public API)"
TIMEOUT_DEFAULT = 10
MAX_RETRY_WAIT = 4.0
TIMEOUT_S = TIMEOUT_DEFAULT


def _int_env(name: str, default: int, *, lo: int | None = None, hi: int | None = None) -> int:
    import os

    raw = (os.getenv(name) or "").strip()
    try:
        value = int(raw) if raw else default
    except ValueError:
        value = default
    if lo is not None:
        value = max(lo, value)
    if hi is not None:
        value = min(hi, value)
    return value


TIMEOUT_S = _int_env("AIRTRAFFIC_TIMEOUT", TIMEOUT_DEFAULT, lo=5, hi=20)


def _retry_after_s(headers: dict[str, str]) -> float:
    raw = (headers.get("retry-after") or "").strip()
    if not raw:
        return 0.0
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 0.0


def http_request(url: str, *, timeout: int = TIMEOUT_S) -> tuple[int, bytes, dict[str, str]]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            hdrs = {str(k).lower(): str(v) for k, v in resp.headers.items()}
            return int(getattr(resp, "status", 200) or 200), body, hdrs
    except TimeoutError:
        return 0, b"", {}
    except socket.timeout:
        return 0, b"", {}
    except urllib.error.HTTPError as exc:
        body = b""
        try:
            body = exc.read() or b""
        except Exception:
            body = b""
        hdrs = {str(k).lower(): str(v) for k, v in (exc.headers.items() if exc.headers else [])}
        return int(exc.code), body, hdrs
    except urllib.error.URLError as exc:
        reason = exc.reason
        text = str(reason).lower()
        if isinstance(reason, (TimeoutError, socket.timeout)) or "timed out" in text:
            return 0, b"", {}
        return -1, b"", {}
    except Exception:
        return -1, b"", {}


def point_url(lat: float, lon: float, radius_nm: int) -> str:
    radius = max(0, min(250, int(radius_nm)))
    lat = max(-90.0, min(90.0, float(lat)))
    lon = max(-180.0, min(180.0, float(lon)))
    return f"{ADSB_ROOT}/v2/lat/{lat:.5f}/lon/{lon:.5f}/dist/{radius}"


def get_nearby(lat: float, lon: float, radius_nm: int) -> tuple[int, bytes, dict[str, str], float]:
    """GET geografica. Un solo retry su 429 se Retry-After è breve. Nessun polling."""
    url = point_url(lat, lon, radius_nm)
    t0 = time.perf_counter()
    http, body, hdrs = http_request(url)
    if http == 429:
        wait = _retry_after_s(hdrs)
        if wait <= 0:
            wait = 1.0
        if wait <= MAX_RETRY_WAIT:
            log.info("[AIRTRAFFIC] rate wait=%.1fs", wait)
            time.sleep(wait)
            http, body, hdrs = http_request(url)
        else:
            log.info("[AIRTRAFFIC] rate no_wait retry_after=%.1fs", wait)
    ms = (time.perf_counter() - t0) * 1000.0
    return http, body, hdrs, ms


def reset_adsb_client() -> None:
    """Hook per i test. Il client è stateless (niente token)."""
    return None
