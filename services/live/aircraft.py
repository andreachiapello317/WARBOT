"""LIVE DATA — Aerei via OpenSky Network. Non usa Overpass.

Documentazione ufficiale:
https://openskynetwork.github.io/opensky-api/
https://openskynetwork.github.io/opensky-api/rest.html

Root REST: https://opensky-network.org/api
Operazione: GET /states/all
Bbox: lamin, lomin, lamax, lomax (WGS84, tutti e quattro)

Auth (REST 1.4.0): OAuth2 client credentials via OPENSKY_CLIENT_ID / OPENSKY_CLIENT_SECRET.
Senza quelle variabili OpenSky non parte: niente accesso anonimo.
Basic username/password non è più accettato.

OpenSky può bloccare IP di hyperscaler: da alcuni cloud la GET
fallisce in handshake TLS. Non esiste un endpoint alternativo documentato.
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

from services.live.opensky_client import get_opensky_client
from services.live.osm import LIST_LIMIT, clip, e

log = logging.getLogger("warbot.aircraft")

# Indici state vector OpenSky REST (documentazione ufficiale).
IDX_ICAO24 = 0
IDX_CALLSIGN = 1
IDX_ORIGIN_COUNTRY = 2
IDX_TIME_POSITION = 3
IDX_LAST_CONTACT = 4
IDX_LONGITUDE = 5
IDX_LATITUDE = 6
IDX_BARO_ALTITUDE = 7
IDX_ON_GROUND = 8
IDX_VELOCITY = 9
IDX_TRUE_TRACK = 10
IDX_VERTICAL_RATE = 11
IDX_GEO_ALTITUDE = 13

EARTH_RADIUS_KM = 6371.0
KM_PER_DEG_LAT = 111.32
MS_TO_KMH = 3.6
CACHE_TTL_DEFAULT = 10
RADIUS_KM_DEFAULT = 50.0
TIMEOUT_DEFAULT = 12
MAX_RADIUS_KM = 150.0
MIN_RADIUS_KM = 10.0

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


RADIUS_KM = _float_env("OPENSKY_RADIUS_KM", RADIUS_KM_DEFAULT, lo=MIN_RADIUS_KM, hi=MAX_RADIUS_KM)
TIMEOUT_S = _int_env("OPENSKY_TIMEOUT", TIMEOUT_DEFAULT, lo=5, hi=25)
CACHE_TTL = _int_env("OPENSKY_CACHE_TTL", CACHE_TTL_DEFAULT, lo=0, hi=20)
PAGE_SIZE = _int_env("OPENSKY_PAGE_SIZE", LIST_LIMIT, lo=5, hi=40)


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
    origin_country: str | None = None

    def as_row(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# 1. Bbox intorno a lat/lon (raggio configurabile, default ~50 km)
# ---------------------------------------------------------------------------


def bbox_from_radius(lat: float, lon: float, radius_km: float | None = None) -> tuple[float, float, float, float]:
    """Restituisce (lamin, lomin, lamax, lomax) per OpenSky.

    1° di latitudine ≈ 111.32 km.
    1° di longitudine ≈ 111.32 · cos(lat) km.
    """
    radius = float(RADIUS_KM if radius_km is None else radius_km)
    radius = max(MIN_RADIUS_KM, min(MAX_RADIUS_KM, radius))
    lat = max(-89.9, min(89.9, float(lat)))
    lon = float(lon)
    dlat = radius / KM_PER_DEG_LAT
    cos_lat = math.cos(math.radians(lat))
    # Evita esplosione vicino ai poli senza allargare la bbox oltre il raggio.
    safe_cos = max(0.08, abs(cos_lat))
    dlon = radius / (KM_PER_DEG_LAT * safe_cos)
    lamin = max(-90.0, lat - dlat)
    lamax = min(90.0, lat + dlat)
    lomin = lon - dlon
    lomax = lon + dlon
    if lomin < -180.0:
        lomin = max(-180.0, lomin)
    if lomax > 180.0:
        lomax = min(180.0, lomax)
    if lamin >= lamax or lomin >= lomax:
        raise ValueError("bbox OpenSky non valida")
    return (round(lamin, 6), round(lomin, 6), round(lamax, 6), round(lomax, 6))


# ---------------------------------------------------------------------------
# 2. Distanza geografica (haversine)
# ---------------------------------------------------------------------------


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


# ---------------------------------------------------------------------------
# 3. Normalizzazione state vector
# ---------------------------------------------------------------------------


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
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


def _as_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        low = value.strip().lower()
        if low in {"true", "1", "yes"}:
            return True
        if low in {"false", "0", "no"}:
            return False
    return None


def _valid_coord(lat: float | None, lon: float | None) -> bool:
    if lat is None or lon is None:
        return False
    return -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0


def parse_state(row: Any, *, center_lat: float, center_lon: float) -> Aircraft | None:
    """Normalizza un state vector OpenSky. None se inutilizzabile."""
    if not isinstance(row, (list, tuple)) or len(row) < 7:
        return None
    icao24 = (_as_str(row[IDX_ICAO24]) or "").lower()
    if not icao24:
        return None
    lon = _as_float(row[IDX_LONGITUDE])
    lat = _as_float(row[IDX_LATITUDE])
    if not _valid_coord(lat, lon):
        return None
    callsign = _as_str(row[IDX_CALLSIGN] if len(row) > IDX_CALLSIGN else None)
    origin = _as_str(row[IDX_ORIGIN_COUNTRY] if len(row) > IDX_ORIGIN_COUNTRY else None)
    baro = _as_float(row[IDX_BARO_ALTITUDE] if len(row) > IDX_BARO_ALTITUDE else None)
    geo = _as_float(row[IDX_GEO_ALTITUDE] if len(row) > IDX_GEO_ALTITUDE else None)
    altitude = baro if baro is not None else geo
    on_ground = _as_bool(row[IDX_ON_GROUND] if len(row) > IDX_ON_GROUND else None)
    velocity = _as_float(row[IDX_VELOCITY] if len(row) > IDX_VELOCITY else None)
    heading = _as_float(row[IDX_TRUE_TRACK] if len(row) > IDX_TRUE_TRACK else None)
    vertical_rate = _as_float(row[IDX_VERTICAL_RATE] if len(row) > IDX_VERTICAL_RATE else None)
    ts = _as_int(row[IDX_LAST_CONTACT] if len(row) > IDX_LAST_CONTACT else None)
    if ts is None:
        ts = _as_int(row[IDX_TIME_POSITION] if len(row) > IDX_TIME_POSITION else None)
    distance = haversine_km(center_lat, center_lon, lat, lon)
    return Aircraft(
        icao24=icao24,
        callsign=callsign,
        lat=lat,
        lon=lon,
        altitude=altitude,
        velocity=velocity,
        heading=heading,
        vertical_rate=vertical_rate,
        on_ground=on_ground,
        timestamp=ts,
        distance_km=distance,
        origin_country=origin,
    )


def normalize_states(
    states: Any,
    *,
    center_lat: float,
    center_lon: float,
    radius_km: float,
) -> list[Aircraft]:
    if not isinstance(states, list):
        return []
    by_icao: dict[str, Aircraft] = {}
    for raw in states:
        plane = parse_state(raw, center_lat=center_lat, center_lon=center_lon)
        if plane is None:
            continue
        if plane.distance_km > radius_km + 0.5:
            continue
        prev = by_icao.get(plane.icao24)
        if prev is None:
            by_icao[plane.icao24] = plane
            continue
        prev_ts = prev.timestamp or 0
        new_ts = plane.timestamp or 0
        if new_ts >= prev_ts:
            by_icao[plane.icao24] = plane
    return list(by_icao.values())


def sort_aircraft(planes: list[Aircraft]) -> list[Aircraft]:
    """In volo, poi distanza dal centro, poi quota. Tie-break icao24. Deterministico."""

    def key(plane: Aircraft) -> tuple:
        if plane.on_ground is False:
            ground_rank = 0
        elif plane.on_ground is None:
            ground_rank = 1
        else:
            ground_rank = 2
        dist = round(plane.distance_km, 3)
        alt = plane.altitude
        # Quota mancante in coda al gruppo; a parità di distanza quota più alta prima.
        alt_missing = 1 if alt is None else 0
        alt_order = -float(alt) if alt is not None else 0.0
        return (ground_rank, dist, alt_missing, alt_order, plane.icao24)

    return sorted(planes, key=key)


def velocity_kmh(meters_per_second: float | None) -> int | None:
    if meters_per_second is None:
        return None
    return int(round(meters_per_second * MS_TO_KMH))


def altitude_m(meters: float | None) -> int | None:
    if meters is None:
        return None
    return int(round(meters))


# ---------------------------------------------------------------------------
# 4. Client HTTP OpenSky (OAuth2, sessione unica)
# ---------------------------------------------------------------------------


def _error_code(http: int, *, invalid_json: bool = False) -> str:
    if invalid_json:
        return "bad_json"
    if http == -2:
        return "not_configured"
    if http == 0:
        return "timeout"
    if http in {401, 403}:
        return "auth"
    if http == 429:
        return "rate"
    if http >= 500:
        return "unavailable"
    if http < 0:
        return "network"
    return "unavailable"


def _request_states(bbox: tuple[float, float, float, float]) -> tuple[int, bytes, bool]:
    client = get_opensky_client()
    if not client.configured():
        log.info("[OPENSKY] not_configured")
        return -2, b"", False
    http, body = client.get_states(bbox)
    return http, body, True


def _bundle(
    *,
    ok: bool,
    aircraft: list[Aircraft] | None = None,
    time_unix: int | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    radius_km: float,
    http: int | None = None,
    error: str | None = None,
    code: str | None = None,
    raw_states: int = 0,
) -> dict[str, Any]:
    rows = [plane.as_row() for plane in (aircraft or [])]
    return {
        "ok": ok,
        "aircraft": rows,
        "time": time_unix,
        "bbox": bbox,
        "radius_km": radius_km,
        "http": http,
        "error": error,
        "code": code,
        "raw_states": raw_states,
        "valid": len(rows),
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


def _cache_key(lat: float, lon: float, radius_km: float) -> str:
    return f"air:{lat:.4f}:{lon:.4f}:{radius_km:.1f}"


def _parse_payload(body: bytes) -> tuple[dict[str, Any] | None, bool]:
    if not body:
        return {"time": None, "states": []}, False
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
    """Aerei nell'area intorno a lat/lon. Solo OpenSky, niente Overpass."""
    radius = float(RADIUS_KM if radius_km is None else radius_km)
    radius = max(MIN_RADIUS_KM, min(MAX_RADIUS_KM, radius))
    bbox = bbox_from_radius(lat, lon, radius)
    key = _cache_key(lat, lon, radius)
    if not force:
        cached = _cache_get(key)
        if cached is not None:
            log.info("[AIRCRAFT] cache_hit valid=%s", cached.get("valid"))
            return dict(cached)

    http, body, _used_auth = _request_states(bbox)
    if http != 200:
        code = _error_code(http)
        log.info("[AIRCRAFT] states=0")
        log.info("[AIRCRAFT] valid=0")
        log.info("[AIRCRAFT] error=%s", code)
        return _bundle(ok=False, bbox=bbox, radius_km=radius, http=http, error=code, code=code)

    payload, bad_json = _parse_payload(body)
    if payload is None or bad_json:
        log.info("[AIRCRAFT] states=0")
        log.info("[AIRCRAFT] valid=0")
        return _bundle(
            ok=False,
            bbox=bbox,
            radius_km=radius,
            http=http,
            error="bad_json",
            code="bad_json",
        )

    raw_states = payload.get("states")
    raw_count = len(raw_states) if isinstance(raw_states, list) else 0
    planes = sort_aircraft(
        normalize_states(raw_states, center_lat=float(lat), center_lon=float(lon), radius_km=radius)
    )
    time_unix = _as_int(payload.get("time"))
    log.info("[AIRCRAFT] states=%s", raw_count)
    log.info("[AIRCRAFT] valid=%s", len(planes))
    log.info("[AIRCRAFT] states_ok")
    result = _bundle(
        ok=True,
        aircraft=planes,
        time_unix=time_unix,
        bbox=bbox,
        radius_km=radius,
        http=http,
        raw_states=raw_count,
    )
    _cache_put(key, result)
    return result


# ---------------------------------------------------------------------------
# 5. Presentazione Telegram
# ---------------------------------------------------------------------------


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


def _fmt_distance(km: float) -> str:
    if km < 1:
        return "📍 < 1 km"
    return f"📍 {int(round(km))} km"


def _age_label(unix_ts: int | None) -> str:
    if unix_ts is None:
        return "pochi secondi fa"
    age = max(0, int(time.time()) - int(unix_ts))
    if age < 20:
        return "pochi secondi fa"
    if age < 60:
        return f"{age} secondi fa"
    minutes = age // 60
    if minutes == 1:
        return "1 minuto fa"
    if minutes < 60:
        return f"{minutes} minuti fa"
    return "dati non recenti"


def _plane_lines(row: dict[str, Any]) -> list[str]:
    on_ground = row.get("on_ground")
    mark = "🛬" if on_ground is True else "🛫"
    title = row.get("callsign") or (str(row.get("icao24") or "").upper()) or "n/d"
    lines = [f"{mark} <b>{e(title)}</b>"]
    dist = row.get("distance_km")
    if isinstance(dist, (int, float)):
        lines.append(_fmt_distance(float(dist)))
    alt = altitude_m(_as_float(row.get("altitude")))
    if alt is not None:
        lines.append(f"⬆️ {_fmt_int(alt)} m")
    speed = velocity_kmh(_as_float(row.get("velocity")))
    if speed is not None:
        lines.append(f"💨 {_fmt_int(speed)} km/h")
    heading = _as_float(row.get("heading"))
    if heading is not None:
        lines.append(f"🧭 {int(round(heading)) % 360}°")
    icao = _as_str(row.get("icao24"))
    if icao:
        lines.append(f"🆔 {e(icao.upper())}")
    vrate = _as_float(row.get("vertical_rate"))
    if vrate is not None:
        sign = "+" if vrate > 0 else ""
        lines.append(f"↕️ {sign}{vrate:.1f} m/s")
    return lines


def error_text(bundle: dict[str, Any], place: dict[str, Any] | None = None) -> str:
    code = bundle.get("code") or bundle.get("error")
    title = f"✈️ <b>AEREI LIVE — {e(_place_label(place))}</b>"
    if code == "rate":
        body = "⚠️ OpenSky ha raggiunto il limite di richieste.\nRiprova tra poco."
    elif code == "not_configured":
        body = (
            "⚠️ OpenSky non è configurato.\n"
            "Imposta OPENSKY_CLIENT_ID e OPENSKY_CLIENT_SECRET nelle variabili d'ambiente."
        )
    elif code == "auth":
        body = "⚠️ OpenSky ha rifiutato l'accesso.\nRiprova tra poco."
    elif code == "timeout":
        body = "⚠️ OpenSky non ha risposto in tempo.\nRiprova tra poco."
    else:
        body = "⚠️ OpenSky non è momentaneamente disponibile.\nRiprova tra poco."
    return clip(f"{title}\n\n{body}")


def empty_text(place: dict[str, Any] | None = None) -> str:
    return clip(
        f"✈️ <b>AEREI LIVE — {e(_place_label(place))}</b>\n\n"
        "✈️ Nessun aereo rilevato nell'area."
    )


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
    airborne = [r for r in chunk if r.get("on_ground") is False]
    ground = [r for r in chunk if r.get("on_ground") is True]
    unknown = [r for r in chunk if r.get("on_ground") is None]
    mixed = bool(airborne) and bool(ground)
    lines = [f"✈️ <b>AEREI LIVE — {e(_place_label(place))}</b>", ""]

    def emit(section: str | None, items: list[dict[str, Any]]) -> None:
        if not items:
            return
        if section:
            lines.append(section)
            lines.append("")
        for item in items:
            lines.extend(_plane_lines(item))
            lines.append("")

    if mixed:
        emit("🛫 IN VOLO", airborne)
        emit("🛬 A TERRA", ground)
        emit(None, unknown)
    else:
        emit(None, chunk)

    while lines and lines[-1] == "":
        lines.pop()
    lines.append("")
    lines.append(f"🕐 Aggiornato: {_age_label(_as_int(bundle.get('time')))}")
    total = len(rows)
    shown = min(offset + len(chunk), total)
    if total > limit:
        lines.append(f"{offset + 1}–{shown} di {total}")
    return clip("\n".join(lines))
