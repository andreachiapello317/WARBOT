"""LIVE DATA — Aerei via ADSB.lol. Non usa Overpass.

Documentazione ufficiale:
https://api.adsb.lol/docs
https://api.adsb.lol/api/openapi.json

GET /v2/lat/{lat}/lon/{lon}/dist/{radius}
radius: miglia nautiche intere, 0–250. Nessuna autenticazione sull'API pubblica.
"""

from __future__ import annotations

import json
import logging
import math
import os
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any

from core.geo import EARTH_RADIUS_KM, KM_PER_DEG_LAT, KT_TO_KMH, haversine_km, km_to_nm
from services.live.adsb_client import fetch_nearby
from services.live.osm import LIST_LIMIT, clip, e

log = logging.getLogger("warbot.airtraffic")

FT_TO_M = 0.3048
FTMIN_TO_MS = 0.00508
CACHE_TTL_DEFAULT = 8
RADIUS_KM_DEFAULT = 50.0
MAX_RADIUS_KM = 460.0
MIN_RADIUS_KM = 5.0

_cache_lock = threading.Lock()
_mem_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _int_env(name: str, default: int, *, lo: int | None = None, hi: int | None = None) -> int:
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


def _float_env(name: str, default: float, *, lo: float | None = None, hi: float | None = None) -> float:
    raw = (os.getenv(name) or "").strip()
    try:
        value = float(raw) if raw else default
    except ValueError:
        value = default
    if lo is not None:
        value = max(lo, value)
    if hi is not None:
        value = min(hi, value)
    return value


RADIUS_KM = _float_env("AIRTRAFFIC_RADIUS_KM", RADIUS_KM_DEFAULT, lo=MIN_RADIUS_KM, hi=MAX_RADIUS_KM)
CACHE_TTL = _int_env("AIRTRAFFIC_CACHE_TTL", CACHE_TTL_DEFAULT, lo=0, hi=20)
PAGE_SIZE = _int_env("AIRTRAFFIC_PAGE_SIZE", LIST_LIMIT, lo=5, hi=40)


@dataclass(frozen=True)
class Aircraft:
    icao24: str
    callsign: str | None
    lat: float
    lon: float
    altitude: float | None
    velocity: float | None
    heading: float | None
    vertical_rate: float | None
    on_ground: bool | None
    timestamp: int | None
    distance_km: float
    registration: str | None = None
    ac_type: str | None = None

    def as_row(self) -> dict[str, Any]:
        return asdict(self)


def bbox_from_radius(lat: float, lon: float, radius_km: float | None = None) -> tuple[float, float, float, float]:
    """Bbox approssimata (lamin, lomin, lamax, lomax). L'API usa il raggio in NM, non questa bbox."""
    radius = float(RADIUS_KM if radius_km is None else radius_km)
    radius = max(MIN_RADIUS_KM, min(MAX_RADIUS_KM, radius))
    lat = max(-89.9, min(89.9, float(lat)))
    lon = float(lon)
    dlat = radius / KM_PER_DEG_LAT
    cos_lat = math.cos(math.radians(lat))
    safe_cos = max(0.08, abs(cos_lat))
    dlon = radius / (KM_PER_DEG_LAT * safe_cos)
    lamin = max(-90.0, lat - dlat)
    lamax = min(90.0, lat + dlat)
    lomin = max(-180.0, lon - dlon)
    lomax = min(180.0, lon + dlon)
    return (round(lamin, 6), round(lomin, 6), round(lamax, 6), round(lomax, 6))


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, str) and value.strip().lower() == "ground":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _as_int(value: Any) -> int | None:
    number = _as_float(value)
    if number is None:
        return None
    return int(number)


def _valid_coord(lat: float | None, lon: float | None) -> bool:
    if lat is None or lon is None:
        return False
    return -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0


def _coords(raw: dict[str, Any]) -> tuple[float | None, float | None]:
    lat = _as_float(raw.get("lat"))
    lon = _as_float(raw.get("lon"))
    if _valid_coord(lat, lon):
        return lat, lon
    last = raw.get("lastPosition")
    if isinstance(last, dict):
        lat = _as_float(last.get("lat"))
        lon = _as_float(last.get("lon"))
        if _valid_coord(lat, lon):
            return lat, lon
    return None, None


def _altitude_m(raw: dict[str, Any]) -> tuple[float | None, bool | None]:
    alt_baro = raw.get("alt_baro")
    if isinstance(alt_baro, str) and alt_baro.strip().lower() == "ground":
        return 0.0, True
    alt_ft = _as_float(alt_baro)
    if alt_ft is None:
        alt_ft = _as_float(raw.get("alt_geom"))
    if alt_ft is None:
        return None, None
    return alt_ft * FT_TO_M, False


def _heading(raw: dict[str, Any]) -> float | None:
    for key in ("track", "true_heading", "mag_heading", "calc_track"):
        value = _as_float(raw.get(key))
        if value is not None:
            return value % 360.0
    return None


def _timestamp(raw: dict[str, Any], now_ms: int | None) -> int | None:
    seen = _as_float(raw.get("seen"))
    if now_ms is None:
        if seen is None:
            return None
        return int(time.time() - max(0.0, seen))
    now = float(now_ms)
    if now > 1e12:
        now = now / 1000.0
    if seen is not None:
        now -= max(0.0, seen)
    return int(now)


def parse_ac(raw: Any, *, center_lat: float, center_lon: float) -> Aircraft | None:
    """Normalizza un oggetto aircraft ADSB.lol. None se inutilizzabile."""
    if not isinstance(raw, dict):
        return None
    icao24 = (_as_str(raw.get("hex")) or "").lower()
    if not icao24:
        return None
    lat, lon = _coords(raw)
    if lat is None or lon is None:
        return None
    altitude, on_ground = _altitude_m(raw)
    gs_kt = _as_float(raw.get("gs"))
    velocity = gs_kt * KT_TO_KMH if gs_kt is not None else None
    vrate_ftmin = _as_float(raw.get("baro_rate"))
    if vrate_ftmin is None:
        vrate_ftmin = _as_float(raw.get("geom_rate"))
    vertical_rate = vrate_ftmin * FTMIN_TO_MS if vrate_ftmin is not None else None
    distance = haversine_km(center_lat, center_lon, lat, lon)
    return Aircraft(
        icao24=icao24,
        callsign=_as_str(raw.get("flight")),
        lat=lat,
        lon=lon,
        altitude=altitude,
        velocity=velocity,
        heading=_heading(raw),
        vertical_rate=vertical_rate,
        on_ground=on_ground,
        timestamp=_timestamp(raw, _as_int(raw.get("_now"))),
        distance_km=distance,
        registration=_as_str(raw.get("r")),
        ac_type=_as_str(raw.get("t")),
    )


def normalize_aircraft(
    rows: Any,
    *,
    center_lat: float,
    center_lon: float,
    radius_km: float,
    now_ms: int | None = None,
) -> list[Aircraft]:
    if not isinstance(rows, list):
        return []
    by_icao: dict[str, Aircraft] = {}
    for raw in rows:
        item = raw
        if isinstance(raw, dict) and now_ms is not None and "_now" not in raw:
            item = dict(raw)
            item["_now"] = now_ms
        plane = parse_ac(item, center_lat=center_lat, center_lon=center_lon)
        if plane is None:
            continue
        if plane.distance_km > radius_km + 0.5:
            continue
        prev = by_icao.get(plane.icao24)
        if prev is None or (plane.timestamp or 0) >= (prev.timestamp or 0):
            by_icao[plane.icao24] = plane
    return list(by_icao.values())


def sort_aircraft(planes: list[Aircraft]) -> list[Aircraft]:
    """Distanza dalla città, poi in volo prima di terra, tie-break icao24."""

    def key(plane: Aircraft) -> tuple:
        dist = round(plane.distance_km, 3)
        if plane.on_ground is False:
            ground_rank = 0
        elif plane.on_ground is None:
            ground_rank = 1
        else:
            ground_rank = 2
        return (dist, ground_rank, plane.icao24)

    return sorted(planes, key=key)


def velocity_kmh(kmh: float | None) -> int | None:
    if kmh is None:
        return None
    return int(round(kmh))


def altitude_m(meters: float | None) -> int | None:
    if meters is None:
        return None
    return int(round(meters))


def _error_code(http: int, *, invalid_json: bool = False) -> str:
    if invalid_json:
        return "bad_json"
    if http == 0:
        return "timeout"
    if http == 429:
        return "rate"
    if http >= 500:
        return "unavailable"
    if 400 <= http < 500:
        return "unavailable"
    if http < 0:
        return "network"
    return "unavailable"


def _bundle(
    *,
    ok: bool,
    aircraft: list[Aircraft] | None = None,
    time_unix: int | None = None,
    radius_km: float,
    radius_nm: int | None = None,
    http: int | None = None,
    error: str | None = None,
    code: str | None = None,
    raw_count: int = 0,
    request_ms: float | None = None,
    provider: str | None = None,
) -> dict[str, Any]:
    rows = [plane.as_row() for plane in (aircraft or [])]
    return {
        "ok": ok,
        "aircraft": rows,
        "time": time_unix,
        "radius_km": radius_km,
        "radius_nm": radius_nm,
        "http": http,
        "error": error,
        "code": code,
        "raw_count": raw_count,
        "valid": len(rows),
        "request_ms": request_ms,
        "provider": provider or "adsb.lol",
    }


def _cache_get(key: str) -> dict[str, Any] | None:
    if CACHE_TTL <= 0:
        return None
    now = time.time()
    with _cache_lock:
        hit = _mem_cache.get(key)
        if not hit:
            return None
        ts, value = hit
        if now - ts >= CACHE_TTL:
            _mem_cache.pop(key, None)
            return None
        return value


def _cache_put(key: str, value: dict[str, Any]) -> None:
    if CACHE_TTL <= 0 or not value.get("ok"):
        return
    with _cache_lock:
        _mem_cache[key] = (time.time(), value)
        if len(_mem_cache) > 64:
            oldest = sorted(_mem_cache.items(), key=lambda item: item[1][0])[:16]
            for stale, _ in oldest:
                _mem_cache.pop(stale, None)


def _cache_key(lat: float, lon: float, radius_km: float) -> str:
    return f"adsb:{lat:.4f}:{lon:.4f}:{radius_km:.1f}"


def clear_aircraft_cache() -> None:
    with _cache_lock:
        _mem_cache.clear()


def _parse_payload(body: bytes) -> tuple[dict[str, Any] | None, bool]:
    if not body:
        return {"ac": [], "now": None, "total": 0}, False
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, True
    if not isinstance(payload, dict):
        return None, True
    return payload, False


def get_aircraft_nearby(
    lat: float,
    lon: float,
    radius_km: float | None = None,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Aerei nell'area intorno a lat/lon. airplanes.live, fallback ADSB.lol."""
    radius = float(RADIUS_KM if radius_km is None else radius_km)
    radius = max(MIN_RADIUS_KM, min(MAX_RADIUS_KM, radius))
    radius_nm = km_to_nm(radius)
    key = _cache_key(lat, lon, radius)
    if not force:
        cached = _cache_get(key)
        if cached is not None:
            log.info("[AIRTRAFFIC] cache_hit valid=%s", cached.get("valid"))
            return dict(cached)

    log.info("[AIRTRAFFIC] city=lat=%.5f lon=%.5f", lat, lon)
    http, body, _hdrs, request_ms, provider = fetch_nearby(lat, lon, radius_nm)
    log.info("[AIRTRAFFIC] provider=%s request_ms=%.0f", provider, request_ms)
    if http != 200:
        code = _error_code(http)
        log.info("[AIRTRAFFIC] aircraft_count=0 error=%s http=%s", code, http if http > 0 else "000")
        return _bundle(
            ok=False,
            radius_km=radius,
            radius_nm=radius_nm,
            http=http,
            error=code,
            code=code,
            request_ms=request_ms,
            provider=provider,
        )

    payload, bad_json = _parse_payload(body)
    if payload is None or bad_json:
        log.info("[AIRTRAFFIC] aircraft_count=0 error=bad_json")
        return _bundle(
            ok=False,
            radius_km=radius,
            radius_nm=radius_nm,
            http=http,
            error="bad_json",
            code="bad_json",
            request_ms=request_ms,
            provider=provider,
        )

    raw_rows = payload.get("ac")
    raw_count = len(raw_rows) if isinstance(raw_rows, list) else 0
    now_ms = _as_int(payload.get("now"))
    planes = sort_aircraft(
        normalize_aircraft(
            raw_rows,
            center_lat=float(lat),
            center_lon=float(lon),
            radius_km=radius,
            now_ms=now_ms,
        )
    )
    time_unix = now_ms
    if time_unix is not None and time_unix > 1e12:
        time_unix = int(time_unix / 1000)
    log.info("[AIRTRAFFIC] aircraft_count=%s", raw_count)
    log.info("[AIRTRAFFIC] results=%s", min(PAGE_SIZE, len(planes)))
    result = _bundle(
        ok=True,
        aircraft=planes,
        time_unix=time_unix,
        radius_km=radius,
        radius_nm=radius_nm,
        http=http,
        raw_count=raw_count,
        request_ms=request_ms,
        provider=provider,
    )
    _cache_put(key, result)
    return result


def _place_label(place: dict[str, Any] | None) -> str:
    if not place:
        return "QUI"
    raw = str(place.get("name") or place.get("display") or "qui")
    return raw.split(",")[0].strip().upper() or "QUI"


def _place_title(place: dict[str, Any] | None) -> str:
    if not place:
        return "qui"
    return str(place.get("name") or place.get("display") or "qui").split(",")[0].strip() or "qui"


def wait_text(place: dict[str, Any] | None) -> str:
    name = e(_place_title(place))
    return f"⏳ Ricerca aerei sopra {name}..."


def _fmt_int(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _fmt_dist_km(km: float) -> str:
    if km < 0.1:
        return "< 0.1 km"
    return f"{km:.1f} km"


def _plane_block(index: int, row: dict[str, Any]) -> list[str]:
    title = row.get("callsign") or (str(row.get("icao24") or "").upper()) or "n/d"
    lines = [f"{index}. <b>{e(title)}</b>"]
    icao = _as_str(row.get("icao24"))
    if icao:
        lines.append(f"   ICAO: {e(icao.upper())}")
    if row.get("on_ground") is True:
        lines.append("   Alt: a terra")
    else:
        alt = altitude_m(_as_float(row.get("altitude")))
        if alt is not None:
            lines.append(f"   Alt: {_fmt_int(alt)} m")
    speed = velocity_kmh(_as_float(row.get("velocity")))
    if speed is not None:
        lines.append(f"   Speed: {_fmt_int(speed)} km/h")
    heading = _as_float(row.get("heading"))
    if heading is not None:
        lines.append(f"   Heading: {int(round(heading)) % 360}°")
    dist = row.get("distance_km")
    if isinstance(dist, (int, float)):
        lines.append(f"   Distanza: {_fmt_dist_km(float(dist))}")
    return lines


def error_text(bundle: dict[str, Any], place: dict[str, Any] | None = None) -> str:
    title = f"✈️ <b>AEREI LIVE — {e(_place_label(place))}</b>"
    return clip(
        f"{title}\n\n"
        "⚠️ Servizio traffico aereo temporaneamente non disponibile.\n"
        "Riprova tra poco."
    )


def empty_text(place: dict[str, Any] | None = None) -> str:
    name = _place_title(place)
    return clip(f"✈️ Nessun aereo rilevato nell'area di {e(name)}.")


def format_aircraft(
    bundle: dict[str, Any],
    place: dict[str, Any] | None = None,
    *,
    offset: int = 0,
    limit: int = PAGE_SIZE,
) -> str:
    if not bundle.get("ok"):
        return error_text(bundle, place)
    rows = list(bundle.get("aircraft") or [])
    if not rows:
        return empty_text(place)
    chunk = rows[offset : offset + limit]
    radius = bundle.get("radius_km")
    lines = [
        f"✈️ <b>AEREI LIVE — {e(_place_label(place))}</b>",
        f"📍 {e(_place_title(place))}",
    ]
    if isinstance(radius, (int, float)):
        lines.append(f"📡 Raggio: {int(round(radius))} km")
    lines.append(f"✈️ {len(rows)} aircraft rilevati")
    lines.append("")
    for i, item in enumerate(chunk):
        lines.extend(_plane_block(offset + i + 1, item))
        lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    total = len(rows)
    shown = min(offset + len(chunk), total)
    if total > limit:
        page = offset // max(1, limit) + 1
        pages = max(1, (total + limit - 1) // limit)
        lines.append("")
        lines.append(f"{offset + 1}–{shown} di {total} · pagina {page}/{pages}")
    return clip("\n".join(lines))
