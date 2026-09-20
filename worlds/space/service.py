"""SPACE: ISS (WhereTheISS.at + CelesTrak TLE), Starlink e satelliti visibili."""

from __future__ import annotations

import logging
import math
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from sgp4.api import Satrec, jday

from core.geo import azimuth_deg, cardinal_it, haversine_km, solar_elevation_deg
from core.http import error_code, http_get_retry, parse_json
from core.pagination import DEFAULT_PAGE_SIZE
from services.live.osm import clip, e

log = logging.getLogger("warbot.space")

ISS_URL = "https://api.wheretheiss.at/v1/satellites/25544"
CELESTRAK_TLE = "https://celestrak.org/NORAD/elements/gp.php?GROUP={group}&FORMAT=tle"
KP_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
FIREBALL_URL = "https://ssd-api.jpl.nasa.gov/fireball.api?limit=20"
TIMEOUT_S = 15
TLE_TTL = 6 * 3600
ISS_TTL = 20
KP_TTL = 300
FIREBALL_TTL = 1800
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
    aos_ll: tuple[float, float] | None = None
    max_ll: tuple[float, float] | None = None
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
            aos_ll = (slat, slon)
            max_ll = (slat, slon)
        elif above:
            if el > max_el:
                max_el = el
                max_t = when
                max_ll = (slat, slon)
            if el < 10:
                mins = int((aos - start).total_seconds() // 60) if aos else None
                az = azimuth_deg(lat, lon, aos_ll[0], aos_ll[1]) if aos_ll else None
                az_max = azimuth_deg(lat, lon, max_ll[0], max_ll[1]) if max_ll else None
                sun_el = solar_elevation_deg(lat, lon, aos) if aos else None
                return {
                    "in_minutes": max(0, mins or 0),
                    "aos": aos.isoformat() if aos else None,
                    "max_el": max_el,
                    "culmination": max_t.isoformat() if max_t else None,
                    "aos_az": az,
                    "max_az": az_max,
                    "aos_dir": cardinal_it(az) if az is not None else None,
                    "max_dir": cardinal_it(az_max) if az_max is not None else None,
                    "sun_el": sun_el,
                }
    if above and aos:
        mins = int((aos - start).total_seconds() // 60)
        az = azimuth_deg(lat, lon, aos_ll[0], aos_ll[1]) if aos_ll else None
        az_max = azimuth_deg(lat, lon, max_ll[0], max_ll[1]) if max_ll else None
        sun_el = solar_elevation_deg(lat, lon, aos)
        return {
            "in_minutes": max(0, mins),
            "aos": aos.isoformat(),
            "max_el": max_el,
            "culmination": None,
            "aos_az": az,
            "max_az": az_max,
            "aos_dir": cardinal_it(az) if az is not None else None,
            "max_dir": cardinal_it(az_max) if az_max is not None else None,
            "sun_el": sun_el,
        }
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


def _signed(value: Any, direction: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    letter = str(direction or "").strip().upper()
    if letter in {"S", "W"}:
        return -abs(number)
    return number


def fetch_kp() -> dict[str, Any]:
    key = "kp"
    hit = _bundle_cache.get(key)
    if hit and time.time() - hit[0] < KP_TTL:
        return dict(hit[1])
    http, body, _hdrs, ms = http_get_retry(KP_URL, timeout=TIMEOUT_S)
    log.info("[SPACE] provider=noaa-swpc request_ms=%.0f http=%s", ms, http if http > 0 else "000")
    if http != 200:
        return _fail(error_code(http), http, ms)
    payload, bad = parse_json(body)
    if bad or not isinstance(payload, list) or not payload:
        return _fail(error_code(http, invalid_json=bad), http, ms)
    rows = [r for r in payload if isinstance(r, dict) and r.get("time_tag")]
    last = rows[-1] if rows else {}
    recent = rows[-8:] if len(rows) >= 8 else rows
    kps = []
    for row in recent:
        try:
            kps.append(float(row.get("Kp")))
        except (TypeError, ValueError):
            continue
    bundle = {
        "ok": True,
        "kind": "aurora",
        "provider": "noaa-swpc",
        "request_ms": ms,
        "http": http,
        "rows": [],
        "kp": last.get("Kp"),
        "time_tag": last.get("time_tag"),
        "kp_max": max(kps) if kps else last.get("Kp"),
        "series": recent,
    }
    _bundle_cache[key] = (time.time(), bundle)
    return dict(bundle)


def aurora_chance(lat: float, kp: float | None) -> str:
    if kp is None:
        return "n/d"
    threshold = 66.5 - 2.0 * float(kp)
    glat = abs(float(lat))
    if glat >= threshold - 1:
        return "possibile a occhio nudo (cielo scuro, orizzonte nord)"
    if glat >= threshold - 7:
        return "improbabile: al massimo un bagliore basso a nord"
    return "non visibile a questa latitudine"


def fetch_fireballs(lat: float, lon: float) -> dict[str, Any]:
    key = f"fireball:{lat:.2f}:{lon:.2f}"
    hit = _bundle_cache.get(key)
    if hit and time.time() - hit[0] < FIREBALL_TTL:
        return dict(hit[1])
    http, body, _hdrs, ms = http_get_retry(FIREBALL_URL, timeout=TIMEOUT_S)
    log.info("[SPACE] provider=jpl-fireball request_ms=%.0f http=%s", ms, http if http > 0 else "000")
    if http != 200:
        return _fail(error_code(http), http, ms)
    payload, bad = parse_json(body)
    if bad or not isinstance(payload, dict):
        return _fail(error_code(http, invalid_json=bad), http, ms)
    fields = list(payload.get("fields") or [])
    idx = {name: i for i, name in enumerate(fields)}
    rows: list[dict[str, Any]] = []
    for raw in payload.get("data") or []:
        if not isinstance(raw, list):
            continue
        def col(name: str) -> Any:
            i = idx.get(name)
            return raw[i] if i is not None and i < len(raw) else None

        elat = _signed(col("lat"), col("lat-dir"))
        elon = _signed(col("lon"), col("lon-dir"))
        dist = haversine_km(lat, lon, elat, elon) if elat is not None and elon is not None else None
        rows.append(
            {
                "date": col("date"),
                "energy": col("energy"),
                "lat": elat,
                "lon": elon,
                "alt": col("alt"),
                "vel": col("vel"),
                "distance_km": dist,
            }
        )
    rows.sort(key=lambda r: (r.get("distance_km") is None, r.get("distance_km") or 9e9))
    bundle = {
        "ok": True,
        "kind": "meteors",
        "provider": "jpl-ssd",
        "request_ms": ms,
        "http": http,
        "rows": rows,
    }
    _bundle_cache[key] = (time.time(), bundle)
    return dict(bundle)


def run_space(city: dict[str, Any], query_id: str) -> dict[str, Any]:
    qid = (query_id or "iss").strip().lower()
    lat, lon = float(city["lat"]), float(city["lon"])
    if qid == "iss":
        return run_iss(city)
    if qid == "aurora":
        bundle = fetch_kp()
        kp = None
        try:
            kp = float(bundle.get("kp_max") if bundle.get("kp_max") is not None else bundle.get("kp"))
        except (TypeError, ValueError):
            kp = None
        bundle["chance"] = aurora_chance(lat, kp)
        bundle["query"] = qid
        bundle["lat"] = lat
        return bundle
    if qid == "meteors":
        bundle = fetch_fireballs(lat, lon)
        bundle["query"] = qid
        return bundle
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
            if nxt.get("aos"):
                stamp = str(nxt["aos"])
                hh = stamp[11:16] if "T" in stamp else stamp
                lines.append(f"🕐 {hh} UTC")
            if nxt.get("aos_dir"):
                az = nxt.get("aos_az")
                az_s = f" (az {az:.0f}°)" if isinstance(az, (int, float)) else ""
                extra = ""
                if nxt.get("max_dir") and nxt.get("max_dir") != nxt.get("aos_dir"):
                    extra = f" → {nxt['max_dir']}"
                lines.append(f"🧭 Compare da {nxt['aos_dir']}{az_s}{extra}")
            sun_el = nxt.get("sun_el")
            if isinstance(sun_el, (int, float)):
                if sun_el < -6:
                    lines.append("🌙 Notturno — visibile a occhio nudo se cielo sereno")
                elif sun_el < 0:
                    lines.append("🌇 Crepuscolo — visibilità bassa")
                else:
                    lines.append("☀️ Diurno — difficile da vedere")
        elif nxt is None:
            lines.append("")
            lines.append("ℹ️ Nessun passaggio visibile calcolato nelle prossime 24 ore, oppure TLE non disponibile.")
        src = iss.get("provider")
        if src:
            lines.append("")
            lines.append(f"<i>{e(str(src))}</i>")
        return clip("\n".join(lines))
    if kind == "aurora":
        lines = ["🌌 <b>AURORA / ATTIVITÀ SOLARE</b>", f"📍 {e(name)}", ""]
        kp = bundle.get("kp")
        kp_max = bundle.get("kp_max")
        if kp is not None:
            lines.append(f"Kp ora: {kp}")
        if kp_max is not None and kp_max != kp:
            lines.append(f"Kp max recente: {kp_max}")
        if bundle.get("time_tag"):
            lines.append(f"🕐 {e(str(bundle['time_tag']))}")
        chance = bundle.get("chance")
        if chance:
            lines.append(f"👁️ {e(str(chance))}")
        lines.append("")
        lines.append("<i>NOAA SWPC planetary K-index. A latitudini italiane serve Kp molto alto.</i>")
        return clip("\n".join(lines))
    if kind == "meteors":
        rows = list(bundle.get("rows") or [])
        lines = [
            "☄️ <b>METEORE / BOLIDI</b>",
            f"📍 rispetto a {e(name)}",
            "ℹ️ NASA JPL fireball: eventi già avvenuti, non un allarme in tempo reale.",
            "",
        ]
        nearby = [r for r in rows if isinstance(r.get("distance_km"), (int, float)) and r["distance_km"] <= 2500]
        chunk = (nearby or rows)[offset : offset + limit]
        if not chunk:
            lines.append("🔎 Nessun bolide catalogato di recente.")
            return clip("\n".join(lines))
        if not nearby:
            lines.append("Nessun bolide vicino. Ultimi eventi globali:")
            lines.append("")
        for row in chunk:
            lines.append(f"• {e(str(row.get('date') or 'evento'))}")
            bits = []
            if row.get("energy") is not None:
                bits.append(f"{row['energy']} kt")
            if isinstance(row.get("distance_km"), (int, float)):
                bits.append(f"{row['distance_km']:.0f} km")
            if isinstance(row.get("alt"), (int, float, str)) and row.get("alt") not in {None, ""}:
                bits.append(f"alt {row['alt']} km")
            if bits:
                lines.append("   " + " · ".join(str(b) for b in bits))
            lines.append("")
        while lines and lines[-1] == "":
            lines.pop()
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
