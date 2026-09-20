"""SKY: Open-Meteo weather, air quality, marine, sun. Nessuna API key."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

from core.geo import haversine_km, solar_elevation_deg
from core.http import error_code, http_get_retry, parse_json
from services.live.osm import clip, e

log = logging.getLogger("warbot.sky")

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
TIMEOUT_S = 12
CACHE_TTL = 600
MARINE_MAX_KM = 80.0

_cache: dict[str, tuple[float, dict[str, Any]]] = {}

WMO = {
    0: "sereno",
    1: "prevalentemente sereno",
    2: "parzialmente nuvoloso",
    3: "coperto",
    45: "nebbia",
    48: "nebbia con brina",
    51: "pioviggine debole",
    53: "pioviggine",
    55: "pioviggine intensa",
    61: "pioggia debole",
    63: "pioggia",
    65: "pioggia intensa",
    71: "neve debole",
    73: "neve",
    75: "neve intensa",
    80: "rovesci deboli",
    81: "rovesci",
    82: "rovesci intensi",
    95: "temporale",
    96: "temporale con grandine",
    99: "temporale con grandine forte",
}


def _cache_get(key: str) -> dict[str, Any] | None:
    hit = _cache.get(key)
    if not hit:
        return None
    ts, value = hit
    if time.time() - ts >= CACHE_TTL:
        _cache.pop(key, None)
        return None
    return dict(value)


def _cache_put(key: str, value: dict[str, Any]) -> None:
    if value.get("ok"):
        _cache[key] = (time.time(), value)


def _fail(code: str, http: int | None = None, ms: float | None = None) -> dict[str, Any]:
    return {"ok": False, "code": code, "http": http, "request_ms": ms, "rows": [], "kind": "error"}


def _get(url: str) -> tuple[int, Any | None, bool, float]:
    http, body, _hdrs, ms = http_get_retry(url, timeout=TIMEOUT_S)
    if http != 200:
        return http, None, False, ms
    payload, bad = parse_json(body)
    return http, payload, bad, ms


def _num(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def fetch_weather(lat: float, lon: float) -> dict[str, Any]:
    params = {
        "latitude": f"{lat:.5f}",
        "longitude": f"{lon:.5f}",
        "current": ",".join(
            [
                "temperature_2m",
                "apparent_temperature",
                "relative_humidity_2m",
                "precipitation",
                "precipitation_probability",
                "weather_code",
                "cloud_cover",
                "pressure_msl",
                "wind_speed_10m",
                "wind_gusts_10m",
                "wind_direction_10m",
                "is_day",
            ]
        ),
        "daily": ",".join(
            [
                "weather_code",
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
                "precipitation_probability_max",
                "sunrise",
                "sunset",
                "uv_index_max",
                "wind_speed_10m_max",
            ]
        ),
        "timezone": "auto",
        "forecast_days": "7",
    }
    url = FORECAST_URL + "?" + urlencode(params)
    http, payload, bad, ms = _get(url)
    log.info("[API] provider=open-meteo request_ms=%.0f http=%s", ms, http if http > 0 else "000")
    if http != 200 or bad or not isinstance(payload, dict):
        return _fail(error_code(http, invalid_json=bad), http, ms)
    current = payload.get("current") if isinstance(payload.get("current"), dict) else {}
    daily = payload.get("daily") if isinstance(payload.get("daily"), dict) else {}
    tz = str(payload.get("timezone") or "")
    return {
        "ok": True,
        "kind": "weather",
        "provider": "open-meteo",
        "request_ms": ms,
        "timezone": tz,
        "current": current,
        "daily": daily,
        "rows": [],
        "http": http,
    }


def fetch_air(lat: float, lon: float) -> dict[str, Any]:
    params = {
        "latitude": f"{lat:.5f}",
        "longitude": f"{lon:.5f}",
        "current": ",".join(
            [
                "european_aqi",
                "us_aqi",
                "pm2_5",
                "pm10",
                "carbon_monoxide",
                "nitrogen_dioxide",
                "sulphur_dioxide",
                "ozone",
            ]
        ),
        "timezone": "auto",
        "domains": "auto",
    }
    url = AIR_URL + "?" + urlencode(params)
    http, payload, bad, ms = _get(url)
    log.info("[API] provider=open-meteo-air request_ms=%.0f http=%s", ms, http if http > 0 else "000")
    if http != 200 or bad or not isinstance(payload, dict):
        return _fail(error_code(http, invalid_json=bad), http, ms)
    current = payload.get("current") if isinstance(payload.get("current"), dict) else {}
    return {
        "ok": True,
        "kind": "air",
        "provider": "open-meteo",
        "request_ms": ms,
        "timezone": str(payload.get("timezone") or ""),
        "current": current,
        "rows": [],
        "http": http,
    }


def fetch_marine(lat: float, lon: float) -> dict[str, Any]:
    params = {
        "latitude": f"{lat:.5f}",
        "longitude": f"{lon:.5f}",
        "current": ",".join(
            [
                "wave_height",
                "wave_direction",
                "wave_period",
                "swell_wave_height",
                "sea_surface_temperature",
                "ocean_current_velocity",
                "ocean_current_direction",
            ]
        ),
        "timezone": "auto",
        "cell_selection": "sea",
    }
    url = MARINE_URL + "?" + urlencode(params)
    http, payload, bad, ms = _get(url)
    log.info("[API] provider=open-meteo-marine request_ms=%.0f http=%s", ms, http if http > 0 else "000")
    if http != 200 or bad or not isinstance(payload, dict):
        return _fail(error_code(http, invalid_json=bad), http, ms)
    grid_lat = _num(payload.get("latitude"))
    grid_lon = _num(payload.get("longitude"))
    dist = None
    if grid_lat is not None and grid_lon is not None:
        dist = haversine_km(lat, lon, grid_lat, grid_lon)
    current = payload.get("current") if isinstance(payload.get("current"), dict) else {}
    values = [current.get(k) for k in ("wave_height", "sea_surface_temperature", "swell_wave_height")]
    has_data = any(v is not None for v in values)
    pertinent = bool(has_data) and (dist is None or dist <= MARINE_MAX_KM)
    return {
        "ok": True,
        "kind": "marine",
        "provider": "open-meteo",
        "request_ms": ms,
        "current": current,
        "grid_km": dist,
        "pertinent": pertinent,
        "rows": [],
        "http": http,
    }


def run_sky(city: dict[str, Any], query_id: str) -> dict[str, Any]:
    lat, lon = float(city["lat"]), float(city["lon"])
    qid = (query_id or "weather").split(":")[0]
    key = f"sky:{qid}:{lat:.3f}:{lon:.3f}"
    cached = _cache_get(key)
    if cached is not None:
        cached["query"] = query_id
        return cached
    if qid == "air":
        bundle = fetch_air(lat, lon)
    elif qid == "marine":
        bundle = fetch_marine(lat, lon)
    else:
        bundle = fetch_weather(lat, lon)
        if qid == "sun":
            bundle["kind"] = "sun"
    bundle["query"] = query_id
    _cache_put(key, bundle)
    return bundle


def _fmt(value: Any, unit: str = "", digits: int = 0) -> str | None:
    number = _num(value)
    if number is None:
        return None
    if digits == 0:
        text = str(int(round(number)))
    else:
        text = f"{number:.{digits}f}"
    return f"{text}{unit}"


def _wmo(code: Any) -> str:
    try:
        return WMO.get(int(code), "")
    except (TypeError, ValueError):
        return ""


def format_sky(bundle: dict[str, Any], city: dict[str, Any], *, offset: int = 0, limit: int = 20) -> str:
    name = (city.get("name") or "qui").split(",")[0]
    if not bundle.get("ok"):
        return clip(
            f"🌤️ <b>SKY — {e(name.upper())}</b>\n\n"
            "⚠️ Servizio temporaneamente non disponibile.\nRiprova tra poco."
        )
    kind = bundle.get("kind") or bundle.get("query")
    cur = bundle.get("current") or {}
    daily = bundle.get("daily") or {}
    if kind == "air":
        lines = [f"🌬️ <b>QUALITÀ DELL'ARIA</b>", f"📍 {e(name)}", ""]
        aqi = _fmt(cur.get("european_aqi"))
        if aqi:
            lines.append(f"AQI (EEA): {aqi}")
        us = _fmt(cur.get("us_aqi"))
        if us:
            lines.append(f"AQI (US): {us}")
        for label, key, unit, dig in (
            ("PM2.5", "pm2_5", " μg/m³", 1),
            ("PM10", "pm10", " μg/m³", 1),
            ("NO₂", "nitrogen_dioxide", " μg/m³", 0),
            ("O₃", "ozone", " μg/m³", 0),
            ("SO₂", "sulphur_dioxide", " μg/m³", 0),
            ("CO", "carbon_monoxide", " μg/m³", 0),
        ):
            val = _fmt(cur.get(key), unit, dig)
            if val:
                lines.append(f"{label}: {val}")
        if len(lines) <= 3:
            lines.append("🔎 Nessun dato di qualità dell'aria per questa località.")
        return clip("\n".join(lines))
    if kind == "marine":
        lines = [f"🌊 <b>MARE</b>", f"📍 {e(name)}", ""]
        if not bundle.get("pertinent"):
            dist = bundle.get("grid_km")
            extra = ""
            if isinstance(dist, (int, float)) and dist > 40:
                extra = f" (cella marina a {dist:.0f} km)"
            lines.append(f"🌊 Dati marini non pertinenti per questa località.{extra}")
            return clip("\n".join(lines))
        mapping = (
            ("Altezza onda", "wave_height", " m", 1),
            ("Direzione onda", "wave_direction", "°", 0),
            ("Periodo", "wave_period", " s", 1),
            ("Swell", "swell_wave_height", " m", 1),
            ("Temperatura mare", "sea_surface_temperature", "°C", 1),
            ("Corrente", "ocean_current_velocity", " km/h", 1),
            ("Dir. corrente", "ocean_current_direction", "°", 0),
        )
        for label, key, unit, dig in mapping:
            val = _fmt(cur.get(key), unit, dig)
            if val:
                lines.append(f"{label}: {val}")
        return clip("\n".join(lines))
    if kind == "sun":
        lines = [f"☀️ <b>SOLE — {e(name.upper())}</b>", ""]
        times = list(daily.get("time") or [])
        sunrise = list(daily.get("sunrise") or [])
        sunset = list(daily.get("sunset") or [])
        if sunrise and sunset:
            rise = str(sunrise[0])
            set_ = str(sunset[0])
            lines.append(f"🌅 Alba {rise[11:16] if 'T' in rise else rise}")
            lines.append(f"🌇 Tramonto {set_[11:16] if 'T' in set_ else set_}")
            try:
                r = datetime.fromisoformat(rise)
                s = datetime.fromisoformat(set_)
                mins = int((s - r).total_seconds() // 60)
                lines.append(f"⏱️ Giorno {mins // 60}h {mins % 60}min")
                night = 24 * 60 - mins
                lines.append(f"🌙 Notte {night // 60}h {night % 60}min")
            except ValueError:
                pass
        uv = _fmt((daily.get("uv_index_max") or [None])[0], digits=1)
        if uv:
            lines.append(f"☀️ UV max {uv}")
        el = solar_elevation_deg(float(city["lat"]), float(city["lon"]))
        lines.append(f"📐 Elevazione solare ora: {el:.0f}°")
        if times:
            lines.append("")
            lines.append(f"<i>{e(str(times[0]))} · timezone locale Open-Meteo</i>")
        return clip("\n".join(lines))

    view = (bundle.get("query") or "weather").split(":")
    day = 0
    week = False
    if len(view) > 1 and view[1] == "week":
        week = True
    elif len(view) > 2 and view[1] == "day" and view[2].isdigit():
        day = int(view[2])
    lines = [f"🌤️ <b>METEO — {e(name.upper())}</b>", ""]
    if week:
        dates = list(daily.get("time") or [])
        tmax = list(daily.get("temperature_2m_max") or [])
        tmin = list(daily.get("temperature_2m_min") or [])
        pop = list(daily.get("precipitation_probability_max") or [])
        code = list(daily.get("weather_code") or [])
        for i, date in enumerate(dates[:7]):
            label = str(date)
            hi = _fmt(tmax[i] if i < len(tmax) else None, "°")
            lo = _fmt(tmin[i] if i < len(tmin) else None, "°")
            rain = _fmt(pop[i] if i < len(pop) else None, "%")
            desc = _wmo(code[i] if i < len(code) else None)
            bits = " · ".join(x for x in (hi and f"max {hi}", lo and f"min {lo}", rain and f"pioggia {rain}", desc) if x)
            lines.append(f"{label}: {bits}")
        return clip("\n".join(lines))
    if day == 0:
        temp = _fmt(cur.get("temperature_2m"), "°C")
        if temp:
            lines.append(f"🌡️ {temp}")
        app = _fmt(cur.get("apparent_temperature"), "°C")
        if app:
            lines.append(f"🤒 Percepita {app}")
        hum = _fmt(cur.get("relative_humidity_2m"), "%")
        if hum:
            lines.append(f"💧 Umidità {hum}")
        cloud = _fmt(cur.get("cloud_cover"), "%")
        if cloud:
            lines.append(f"☁️ Nuvolosità {cloud}")
        wind = _fmt(cur.get("wind_speed_10m"), " km/h")
        if wind:
            lines.append(f"💨 Vento {wind}")
        gust = _fmt(cur.get("wind_gusts_10m"), " km/h")
        if gust:
            lines.append(f"🌬️ Raffiche {gust}")
        rain = _fmt(cur.get("precipitation_probability"), "%")
        if rain:
            lines.append(f"🌧️ Pioggia {rain}")
        desc = _wmo(cur.get("weather_code"))
        if desc:
            lines.append(f"ℹ️ {desc}")
        if daily.get("sunrise"):
            rise = str(daily["sunrise"][0])
            set_ = str((daily.get("sunset") or [""])[0])
            lines.append(f"🌅 Alba {rise[11:16] if 'T' in rise else rise}")
            if set_:
                lines.append(f"🌇 Tramonto {set_[11:16] if 'T' in set_ else set_}")
        uv = _fmt((daily.get("uv_index_max") or [None])[0], digits=1)
        if uv:
            lines.append(f"☀️ UV {uv}")
        tz = bundle.get("timezone")
        if tz:
            lines.append("")
            lines.append(f"<i>{e(str(tz))}</i>")
        return clip("\n".join(lines))
    dates = list(daily.get("time") or [])
    idx = min(day, max(0, len(dates) - 1))
    if not dates:
        return clip(f"🌤️ <b>METEO — {e(name.upper())}</b>\n\n🔎 Nessun risultato trovato nell'area selezionata.")
    lines.append(str(dates[idx]))
    tmax = _fmt((daily.get("temperature_2m_max") or [None])[idx] if daily.get("temperature_2m_max") else None, "°C")
    tmin = _fmt((daily.get("temperature_2m_min") or [None])[idx] if daily.get("temperature_2m_min") else None, "°C")
    if tmax:
        lines.append(f"🌡️ Max {tmax}")
    if tmin:
        lines.append(f"🌡️ Min {tmin}")
    pop = _fmt((daily.get("precipitation_probability_max") or [None])[idx] if daily.get("precipitation_probability_max") else None, "%")
    if pop:
        lines.append(f"🌧️ Pioggia {pop}")
    desc = _wmo((daily.get("weather_code") or [None])[idx] if daily.get("weather_code") else None)
    if desc:
        lines.append(f"ℹ️ {desc}")
    return clip("\n".join(lines))
