"""EARTH: USGS earthquakes, NASA EONET, Open-Meteo Flood (previsione portata)."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

from core.geo import haversine_km
from core.http import error_code, http_get_retry, parse_json
from core.pagination import DEFAULT_PAGE_SIZE
from services.live.osm import clip, e

log = logging.getLogger("warbot.earth")

USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
EONET_URL = "https://eonet.gsfc.nasa.gov/api/v3/events"
FLOOD_URL = "https://flood-api.open-meteo.com/v1/flood"
TIMEOUT_S = 15
EQ_TTL = 90
EONET_TTL = 120
FLOOD_TTL = 900
EQ_RADIUS_KM = 500.0

_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _cache_get(key: str, ttl: int) -> dict[str, Any] | None:
    hit = _cache.get(key)
    if not hit:
        return None
    ts, value = hit
    if time.time() - ts >= ttl:
        _cache.pop(key, None)
        return None
    return dict(value)


def _cache_put(key: str, value: dict[str, Any]) -> None:
    if value.get("ok"):
        _cache[key] = (time.time(), value)


def _fail(code: str, http: int | None = None, ms: float | None = None) -> dict[str, Any]:
    return {"ok": False, "code": code, "http": http, "request_ms": ms, "rows": []}


def _get(url: str) -> tuple[int, Any | None, bool, float]:
    http, body, _hdrs, ms = http_get_retry(url, timeout=TIMEOUT_S)
    if http != 200:
        return http, None, False, ms
    payload, bad = parse_json(body)
    return http, payload, bad, ms


def _age(ms: int | None) -> str:
    if ms is None:
        return ""
    delta = max(0, int(time.time() - ms / 1000 if ms > 1e12 else time.time() - ms))
    if delta < 60:
        return f"{delta} s fa"
    if delta < 3600:
        return f"{delta // 60} min fa"
    if delta < 86400:
        h = delta // 3600
        m = (delta % 3600) // 60
        return f"{h}h {m}m fa" if m else f"{h}h fa"
    return f"{delta // 86400}g fa"


def fetch_earthquakes(lat: float, lon: float, *, hours: int = 24, minmag: float | None = None) -> dict[str, Any]:
    start = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S")
    params = {
        "format": "geojson",
        "latitude": f"{lat:.4f}",
        "longitude": f"{lon:.4f}",
        "maxradiuskm": str(int(EQ_RADIUS_KM)),
        "starttime": start,
        "orderby": "time",
        "limit": "50",
        "eventtype": "earthquake",
    }
    if minmag is not None:
        params["minmagnitude"] = str(minmag)
    url = USGS_URL + "?" + urlencode(params)
    http, payload, bad, ms = _get(url)
    log.info("[API] provider=usgs request_ms=%.0f http=%s", ms, http if http > 0 else "000")
    if http != 200 or bad or not isinstance(payload, dict):
        return _fail(error_code(http, invalid_json=bad), http, ms)
    rows: list[dict[str, Any]] = []
    for feat in payload.get("features") or []:
        if not isinstance(feat, dict):
            continue
        props = feat.get("properties") or {}
        geom = feat.get("geometry") or {}
        coords = geom.get("coordinates") or []
        if len(coords) < 2:
            continue
        elon, elat = float(coords[0]), float(coords[1])
        depth = float(coords[2]) if len(coords) > 2 and coords[2] is not None else None
        mag = props.get("mag")
        try:
            mag_f = float(mag) if mag is not None else None
        except (TypeError, ValueError):
            mag_f = None
        rows.append(
            {
                "magnitude": mag_f,
                "place": props.get("place") or "",
                "time_ms": props.get("time"),
                "depth_km": depth,
                "lat": elat,
                "lon": elon,
                "distance_km": haversine_km(lat, lon, elat, elon),
                "url": props.get("url") or "",
            }
        )
    return {
        "ok": True,
        "kind": "earthquakes",
        "provider": "usgs",
        "request_ms": ms,
        "rows": rows,
        "http": http,
        "hours": hours,
        "minmag": minmag,
        "radius_km": EQ_RADIUS_KM,
    }


def _event_point(event: dict[str, Any]) -> tuple[float, float] | None:
    geoms = event.get("geometry") or []
    if not isinstance(geoms, list) or not geoms:
        return None
    last = geoms[-1] if isinstance(geoms[-1], dict) else None
    if not last:
        return None
    coords = last.get("coordinates")
    if isinstance(coords, list) and len(coords) >= 2 and not isinstance(coords[0], list):
        return float(coords[1]), float(coords[0])
    if isinstance(coords, list) and coords and isinstance(coords[0], list) and len(coords[0]) >= 2:
        return float(coords[0][1]), float(coords[0][0])
    return None


def fetch_eonet(lat: float, lon: float, *, category: str | None = None, radius_km: float = 1500.0) -> dict[str, Any]:
    params = {
        "status": "open",
        "limit": "80",
        "days": "20",
    }
    if category:
        params["category"] = category
    url = EONET_URL + "?" + urlencode(params)
    http, payload, bad, ms = _get(url)
    log.info("[API] provider=eonet request_ms=%.0f http=%s", ms, http if http > 0 else "000")
    if http != 200 or bad or not isinstance(payload, dict):
        return _fail(error_code(http, invalid_json=bad), http, ms)
    rows: list[dict[str, Any]] = []
    for event in payload.get("events") or []:
        if not isinstance(event, dict):
            continue
        cats = event.get("categories") or []
        cat_title = ""
        if cats and isinstance(cats[0], dict):
            cat_title = str(cats[0].get("id") or cats[0].get("title") or "")
        if category is None and cat_title in {"earthquakes"}:
            continue
        point = _event_point(event)
        dist = haversine_km(lat, lon, point[0], point[1]) if point else None
        if dist is not None and dist > radius_km:
            continue
        sources = event.get("sources") or []
        src = ""
        if sources and isinstance(sources[0], dict):
            src = str(sources[0].get("url") or "")
        geoms = event.get("geometry") or []
        date = ""
        if geoms and isinstance(geoms[-1], dict):
            date = str(geoms[-1].get("date") or "")
        rows.append(
            {
                "title": event.get("title") or "evento",
                "category": cat_title,
                "lat": point[0] if point else None,
                "lon": point[1] if point else None,
                "distance_km": dist,
                "date": date,
                "url": src,
                "id": event.get("id"),
            }
        )
    rows.sort(key=lambda r: (r.get("distance_km") is None, r.get("distance_km") or 9e9))
    return {
        "ok": True,
        "kind": "events",
        "provider": "eonet",
        "request_ms": ms,
        "rows": rows,
        "http": http,
        "category": category,
        "approx": True,
    }


def fetch_flood(lat: float, lon: float) -> dict[str, Any]:
    params = {
        "latitude": f"{lat:.5f}",
        "longitude": f"{lon:.5f}",
        "daily": "river_discharge,river_discharge_mean,river_discharge_max",
        "forecast_days": "7",
    }
    url = FLOOD_URL + "?" + urlencode(params)
    http, payload, bad, ms = _get(url)
    log.info("[API] provider=open-meteo-flood request_ms=%.0f http=%s", ms, http if http > 0 else "000")
    if http != 200 or bad or not isinstance(payload, dict):
        return _fail(error_code(http, invalid_json=bad), http, ms)
    daily = payload.get("daily") if isinstance(payload.get("daily"), dict) else {}
    times = list(daily.get("time") or [])
    disc = list(daily.get("river_discharge") or [])
    rows = []
    for i, day in enumerate(times[:7]):
        rows.append(
            {
                "date": day,
                "discharge": disc[i] if i < len(disc) else None,
                "mean": (daily.get("river_discharge_mean") or [None] * 7)[i] if daily.get("river_discharge_mean") else None,
                "max": (daily.get("river_discharge_max") or [None] * 7)[i] if daily.get("river_discharge_max") else None,
            }
        )
    return {
        "ok": True,
        "kind": "flood",
        "provider": "open-meteo-flood",
        "request_ms": ms,
        "rows": rows,
        "http": http,
        "forecast": True,
    }


def run_earth(city: dict[str, Any], query_id: str) -> dict[str, Any]:
    lat, lon = float(city["lat"]), float(city["lon"])
    raw = (query_id or "earthquakes").strip().lower()
    key = f"earth:{raw}:{lat:.3f}:{lon:.3f}"
    ttl = EQ_TTL
    if raw.startswith("wildfires") or raw.startswith("events"):
        ttl = EONET_TTL
    elif raw.startswith("flood"):
        ttl = FLOOD_TTL
    cached = _cache_get(key, ttl)
    if cached is not None:
        cached["query"] = raw
        return cached
    if raw in {"earthquakes", "eq24"}:
        bundle = fetch_earthquakes(lat, lon, hours=24)
    elif raw in {"eq7", "earthquakes:7d"}:
        bundle = fetch_earthquakes(lat, lon, hours=24 * 7)
    elif raw in {"eqm4", "earthquakes:m4"}:
        bundle = fetch_earthquakes(lat, lon, hours=24 * 7, minmag=4.0)
    elif raw in {"wildfires", "fire"}:
        bundle = fetch_eonet(lat, lon, category="wildfires")
        bundle["kind"] = "wildfires"
    elif raw in {"flood", "floods"}:
        bundle = fetch_flood(lat, lon)
    else:
        bundle = fetch_eonet(lat, lon, category=None)
        bundle["kind"] = "events"
    bundle["query"] = raw
    _cache_put(key, bundle)
    return bundle


def format_earth(bundle: dict[str, Any], city: dict[str, Any], *, offset: int = 0, limit: int = DEFAULT_PAGE_SIZE) -> str:
    name = (city.get("name") or "qui").split(",")[0]
    if not bundle.get("ok"):
        return clip(
            f"🌋 <b>EARTH — {e(name.upper())}</b>\n\n"
            "⚠️ Servizio temporaneamente non disponibile.\nRiprova tra poco."
        )
    kind = bundle.get("kind")
    rows = list(bundle.get("rows") or [])
    if kind == "flood":
        lines = [
            f"🌊 <b>FIUMI — {e(name.upper())}</b>",
            "ℹ️ Previsione portata (GloFAS / Open-Meteo). Non è un allarme alluvione.",
            "",
        ]
        if not rows:
            lines.append("🔎 Nessun dato di portata per questa cella.")
            return clip("\n".join(lines))
        for row in rows:
            disc = row.get("discharge")
            val = f"{disc:.1f} m³/s" if isinstance(disc, (int, float)) else "n/d"
            lines.append(f"{row.get('date')}: {val}")
        return clip("\n".join(lines))
    if kind == "earthquakes":
        title = f"🌋 <b>TERREMOTI — {int(bundle.get('radius_km') or 500)} km</b>"
        lines = [title, f"📍 {e(name)}", ""]
        chunk = rows[offset : offset + limit]
        if not chunk:
            lines.append("🔎 Nessun terremoto nell'area e nel periodo selezionati.")
            return clip("\n".join(lines))
        for row in chunk:
            mag = row.get("magnitude")
            mag_s = f"M {mag:.1f}" if isinstance(mag, (int, float)) else "M n/d"
            dist = row.get("distance_km")
            dist_s = f"{dist:.0f} km da {name}" if isinstance(dist, (int, float)) else "distanza n/d"
            depth = row.get("depth_km")
            depth_s = f"{depth:.0f} km" if isinstance(depth, (int, float)) else "n/d"
            lines.append(f"🇮🇹 {mag_s}")
            lines.append(f"📍 {e(dist_s)}")
            lines.append(f"📏 Profondità: {depth_s}")
            age = _age(row.get("time_ms") if isinstance(row.get("time_ms"), int) else None)
            if age:
                lines.append(f"🕐 {age}")
            place = row.get("place")
            if place:
                lines.append(f"<i>{e(str(place))}</i>")
            url = row.get("url")
            if url:
                lines.append(f"🔗 {e(str(url))}")
            lines.append("")
        while lines and lines[-1] == "":
            lines.pop()
        if len(rows) > limit:
            lines.append("")
            lines.append(f"{offset + 1}–{min(offset + limit, len(rows))} di {len(rows)}")
        return clip("\n".join(lines))
    title = "🔥 <b>INCENDI</b>" if kind == "wildfires" else "🌪️ <b>EVENTI NATURALI</b>"
    lines = [title, f"📍 {e(name)}", "ℹ️ Posizioni EONET spesso approssimate.", ""]
    chunk = rows[offset : offset + limit]
    if not chunk:
        lines.append("🔎 Nessun evento aperto nell'area selezionata.")
        return clip("\n".join(lines))
    for row in chunk:
        lines.append(f"• {e(str(row.get('title') or 'evento'))}")
        cat = row.get("category")
        if cat:
            lines.append(f"   {e(str(cat))}")
        dist = row.get("distance_km")
        if isinstance(dist, (int, float)):
            lines.append(f"   📍 {dist:.0f} km")
        if row.get("date"):
            lines.append(f"   🕐 {e(str(row['date'])[:16])}")
        if row.get("url"):
            lines.append(f"   🔗 {e(str(row['url']))}")
        lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    return clip("\n".join(lines))
