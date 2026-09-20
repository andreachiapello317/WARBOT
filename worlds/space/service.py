"""SPACE: ISS (WhereTheISS.at + CelesTrak TLE), Starlink e satelliti visibili."""

from __future__ import annotations

import logging
import math
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from sgp4.api import Satrec, jday

from core.geo import haversine_km
from core.http import error_code, http_get_retry, parse_json
from core.pagination import DEFAULT_PAGE_SIZE
from services.live.osm import clip, e

log = logging.getLogger("warbot.space")

ISS_URL = "https://api.wheretheiss.at/v1/satellites/25544"
CELESTRAK_TLE = "https://celestrak.org/NORAD/elements/gp.php?GROUP={group}&FORMAT=tle"
TIMEOUT_S = 15
TLE_TTL = 6 * 3600
ISS_TTL = 20
RE_KM = 6378.137

_tle_cache: dict[str, tuple[float, list[tuple[str, Satrec]]]] = {}
_bundle_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _fail(code: str, http: int | None = None, ms: float | None = None) -> dict[str, Any]:
    return {"ok": False, "code": code, "http": http, "request_ms": ms, "rows": []}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _gmst_rad(jd: float) -> float:
    t = (jd - 2451545.0) / 36525.0
    gmst_sec = 67310.54841 + (876600.0 * 3600 + 8640184.812866) * t + 0.093104 * t * t - 6.2e-6 * t**3
    return math.radians((gmst_sec / 240.0) % 360.0)


def teme_to_lla(r: tuple[float, float, float], jd: float) -> tuple[float, float, float]:
    x, y, z = r
    theta = _gmst_rad(jd)
    xg = x * math.cos(theta) + y * math.sin(theta)
    yg = -x * math.sin(theta) + y * math.cos(theta)
    lon = math.degrees(math.atan2(yg, xg))
    hyp = math.hypot(xg, yg)
    lat = math.degrees(math.atan2(z, hyp))
    alt = math.sqrt(x * x + y * y + z * z) - RE_KM
    if lon > 180:
        lon -= 360
    if lon < -180:
        lon += 360
    return lat, lon, alt


def llh_ecef(lat: float, lon: float, alt_km: float) -> tuple[float, float, float]:
    latr, lonr = math.radians(lat), math.radians(lon)
    r = RE_KM + alt_km
    return (r * math.cos(latr) * math.cos(lonr), r * math.cos(latr) * math.sin(lonr), r * math.sin(latr))


def elevation_deg(olat: float, olon: float, slat: float, slon: float, salt: float) -> float:
    ox, oy, oz = llh_ecef(olat, olon, 0.0)
    sx, sy, sz = llh_ecef(slat, slon, salt)
    rx, ry, rz = sx - ox, sy - oy, sz - oz
    latr, lonr = math.radians(olat), math.radians(olon)
    ux, uy, uz = math.cos(latr) * math.cos(lonr), math.cos(latr) * math.sin(lonr), math.sin(latr)
    norm = math.sqrt(rx * rx + ry * ry + rz * rz)
    if norm <= 0:
        return 90.0
    return math.degrees(math.asin(max(-1.0, min(1.0, (rx * ux + ry * uy + rz * uz) / norm))))


def _propagate(sat: Satrec, when: datetime) -> tuple[float, float, float, float, float] | None:
    frac = when.second + when.microsecond / 1e6
    jd, fr = jday(when.year, when.month, when.day, when.hour, when.minute, frac)
    err, r, v = sat.sgp4(jd, fr)
    if err != 0:
        return None
    lat, lon, alt = teme_to_lla((r[0], r[1], r[2]), jd + fr)
    speed = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
    heading = (math.degrees(math.atan2(v[0], v[1])) + 360.0) % 360.0
    return lat, lon, alt, speed, heading


def load_group(group: str) -> list[tuple[str, Satrec]]:
    now = time.time()
    hit = _tle_cache.get(group)
    if hit and now - hit[0] < TLE_TTL:
        return hit[1]
    url = CELESTRAK_TLE.format(group=group)
    http, body, _hdrs, ms = http_get_retry(url, timeout=TIMEOUT_S)
    log.info("[SPACE] provider=celestrak group=%s request_ms=%.0f http=%s", group, ms, http if http > 0 else "000")
    if http != 200 or not body:
        return hit[1] if hit else []
    text = body.decode("utf-8", errors="replace").splitlines()
    sats: list[tuple[str, Satrec]] = []
    i = 0
    while i + 2 < len(text):
        name = text[i].strip()
        l1 = text[i + 1].strip()
        l2 = text[i + 2].strip()
        if l1.startswith("1 ") and l2.startswith("2 "):
            try:
                sats.append((name, Satrec.twoline2rv(l1, l2)))
            except Exception:
                pass
            i += 3
        else:
            i += 1
    if sats:
        _tle_cache[group] = (now, sats)
    return sats


def fetch_iss_now() -> dict[str, Any] | None:
    http, body, _hdrs, ms = http_get_retry(ISS_URL, timeout=TIMEOUT_S)
    log.info("[SPACE] provider=wheretheiss.at request_ms=%.0f http=%s", ms, http if http > 0 else "000")
    if http != 200:
        return None
    payload, bad = parse_json(body)
    if bad or not isinstance(payload, dict):
        return None
    try:
        return {
            "lat": float(payload["latitude"]),
            "lon": float(payload["longitude"]),
            "altitude": float(payload.get("altitude") or 0),
            "velocity": float(payload.get("velocity") or 0),
            "visibility": payload.get("visibility"),
            "request_ms": ms,
            "provider": "wheretheiss.at",
        }
    except (KeyError, TypeError, ValueError):
        return None


def _next_pass(sat: Satrec, lat: float, lon: float, hours: int = 12) -> dict[str, Any] | None:
    start = _now()
    above = False
    aos = None
    max_el = -90.0
    max_t = None
    for step in range(0, hours * 60, 1):
        when = start + timedelta(minutes=step)
        state = _propagate(sat, when)
        if state is None:
            continue
        slat, slon, salt, _spd, _hdg = state
        el = elevation_deg(lat, lon, slat, slon, salt)
        if el >= 10 and not above:
            above = True
            aos = when
            max_el = el
            max_t = when
        elif above:
            if el > max_el:
                max_el = el
                max_t = when
            if el < 10:
                mins = int((aos - start).total_seconds() // 60) if aos else None
                return {
                    "in_minutes": max(0, mins or 0),
                    "aos": aos.isoformat() if aos else None,
                    "max_el": max_el,
                    "culmination": max_t.isoformat() if max_t else None,
                }
    if above and aos:
        mins = int((aos - start).total_seconds() // 60)
        return {"in_minutes": max(0, mins), "aos": aos.isoformat(), "max_el": max_el, "culmination": None}
    return None


def run_iss(city: dict[str, Any]) -> dict[str, Any]:
    lat, lon = float(city["lat"]), float(city["lon"])
    key = f"iss:{lat:.3f}:{lon:.3f}"
    hit = _bundle_cache.get(key)
    if hit and time.time() - hit[0] < ISS_TTL:
        return dict(hit[1])
    now = fetch_iss_now()
    stations = load_group("stations")
    iss_sat = None
    for name, sat in stations:
        if "ISS" in name.upper():
            iss_sat = sat
            break
    if now is None and iss_sat is not None:
        state = _propagate(iss_sat, _now())
        if state:
            slat, slon, salt, spd, hdg = state
            now = {
                "lat": slat,
                "lon": slon,
                "altitude": salt,
                "velocity": spd * 3600.0,
                "heading": hdg,
                "provider": "celestrak",
                "request_ms": None,
            }
    if now is None:
        bundle = _fail("unavailable")
        bundle["kind"] = "iss"
        return bundle
    nxt = _next_pass(iss_sat, lat, lon, hours=24) if iss_sat is not None else None
    dist = haversine_km(lat, lon, now["lat"], now["lon"])
    bundle = {
        "ok": True,
        "kind": "iss",
        "provider": now.get("provider"),
        "rows": [],
        "iss": now,
        "distance_km": dist,
        "next_pass": nxt,
        "http": 200,
    }
    _bundle_cache[key] = (time.time(), bundle)
    return bundle


def _overheads(group: str, lat: float, lon: float, *, limit: int = 20, name_filter: str | None = None) -> dict[str, Any]:
    sats = load_group(group)
    if not sats:
        return _fail("unavailable")
    when = _now()
    rows: list[dict[str, Any]] = []
    for name, sat in sats:
        if name_filter and name_filter.lower() not in name.lower():
            continue
        state = _propagate(sat, when)
        if state is None:
            continue
        slat, slon, salt, spd, hdg = state
        dist = haversine_km(lat, lon, slat, slon)
        el = elevation_deg(lat, lon, slat, slon, salt)
        if el < 0 and dist > 2500:
            continue
        rows.append(
            {
                "name": name,
                "lat": slat,
                "lon": slon,
                "altitude": salt,
                "velocity_kms": spd,
                "heading": hdg,
                "distance_km": dist,
                "elevation": el,
            }
        )
    rows.sort(key=lambda r: (-float(r.get("elevation") or -90), float(r.get("distance_km") or 9e9)))
    return {
        "ok": True,
        "kind": group,
        "provider": "celestrak",
        "rows": rows[: max(limit * 3, 60)],
        "http": 200,
        "computed_at": when.isoformat(),
    }


def run_space(city: dict[str, Any], query_id: str) -> dict[str, Any]:
    qid = (query_id or "iss").strip().lower()
    lat, lon = float(city["lat"]), float(city["lon"])
    if qid == "iss":
        return run_iss(city)
    if qid == "starlink":
        bundle = _overheads("starlink", lat, lon, limit=20)
        bundle["kind"] = "starlink"
        bundle["query"] = qid
        return bundle
    bundle = _overheads("visual", lat, lon, limit=20)
    bundle["kind"] = "satellites"
    bundle["query"] = qid
    return bundle


def format_space(bundle: dict[str, Any], city: dict[str, Any], *, offset: int = 0, limit: int = DEFAULT_PAGE_SIZE) -> str:
    name = (city.get("name") or "qui").split(",")[0]
    if not bundle.get("ok"):
        return clip(
            f"🛰️ <b>SPACE — {e(name.upper())}</b>\n\n"
            "⚠️ Servizio temporaneamente non disponibile.\nRiprova tra poco."
        )
    kind = bundle.get("kind")
    if kind == "iss":
        iss = bundle.get("iss") or {}
        lines = ["🛰️ <b>ISS</b>", f"📍 rispetto a {e(name)}", ""]
        if iss.get("lat") is not None:
            lines.append(f"🌎 {iss['lat']:.2f}°, {iss['lon']:.2f}°")
        if iss.get("altitude") is not None:
            lines.append(f"⬆️ {iss['altitude']:.0f} km")
        vel = iss.get("velocity")
        if isinstance(vel, (int, float)):
            lines.append(f"🚀 {vel:.0f} km/h" if vel > 50 else f"🚀 {vel:.2f} km/s")
        hdg = iss.get("heading")
        if isinstance(hdg, (int, float)):
            lines.append(f"🧭 {hdg:.0f}°")
        dist = bundle.get("distance_km")
        if isinstance(dist, (int, float)):
            lines.append(f"📍 nadir a {dist:.0f} km da {e(name)}")
        nxt = bundle.get("next_pass")
        if nxt and nxt.get("in_minutes") is not None:
            lines.append("")
            lines.append(f"📍 Prossimo passaggio su {e(name)}:")
            lines.append(f"{int(nxt['in_minutes'])} min (elev. max {nxt.get('max_el', 0):.0f}°)")
        elif nxt is None:
            lines.append("")
            lines.append("ℹ️ Nessun passaggio visibile calcolato nelle prossime 24 ore, oppure TLE non disponibile.")
        src = iss.get("provider")
        if src:
            lines.append("")
            lines.append(f"<i>{e(str(src))}</i>")
        return clip("\n".join(lines))
    title = "⭐ <b>STARLINK</b>" if kind == "starlink" else "🛰️ <b>SATELLITI VISIBILI</b>"
    rows = list(bundle.get("rows") or [])
    visible = [r for r in rows if (r.get("elevation") or -90) >= 0]
    pool = visible or rows
    chunk = pool[offset : offset + limit]
    lines = [title, f"📍 {e(name)}", ""]
    if not chunk:
        lines.append("🔎 Nessun satellite rilevante sopra l'orizzonte in questo momento.")
        return clip("\n".join(lines))
    for row in chunk:
        el = row.get("elevation")
        mark = "⬆️" if isinstance(el, (int, float)) and el >= 10 else "•"
        lines.append(f"{mark} {e(str(row.get('name') or 'sat'))}")
        bits = []
        if isinstance(row.get("altitude"), (int, float)):
            bits.append(f"{row['altitude']:.0f} km")
        if isinstance(el, (int, float)):
            bits.append(f"el {el:.0f}°")
        if isinstance(row.get("distance_km"), (int, float)):
            bits.append(f"{row['distance_km']:.0f} km nadir")
        if bits:
            lines.append("   " + " · ".join(bits))
        lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    lines.append("")
    lines.append("<i>TLE CelesTrak · posizione calcolata ora (SGP4)</i>")
    if len(pool) > limit:
        lines.append(f"{offset + 1}–{min(offset + limit, len(pool))} di {len(pool)}")
    return clip("\n".join(lines))
