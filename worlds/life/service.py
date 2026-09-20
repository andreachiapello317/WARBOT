"""CITY LIFE: OSM intorno alla città + Open-Meteo + Meteoalarm. Nessuna API key."""

from __future__ import annotations

import logging
from typing import Any

from core.geo import bbox_from_radius, haversine_km
from core.pagination import DEFAULT_PAGE_SIZE
from services.live.osm import clip, e, osm_url
from worlds.life.alerts import fetch_meteoalarm, filter_for_city
from worlds.life.hours import city_now, is_open_now
from worlds.life.overpass import LABELS, search_around
from worlds.sky.service import fetch_air, fetch_weather

log = logging.getLogger("warbot.life")

STREET_VIEW = "https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat:.5f},{lon:.5f}"


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt(value: Any, unit: str = "", digits: int = 0) -> str | None:
    number = _num(value)
    if number is None:
        return None
    text = str(int(round(number))) if digits == 0 else f"{number:.{digits}f}"
    return f"{text}{unit}"


def _open_label(row: dict[str, Any], now) -> str:
    flag = is_open_now(row.get("opening_hours"), now)
    if flag is True:
        return "aperto ora"
    if flag is False:
        return "chiuso ora"
    if row.get("opening_hours"):
        return str(row["opening_hours"])[:40]
    return "orario n/d"


def _pin(row: dict[str, Any]) -> str:
    return osm_url(float(row["lat"]), float(row["lon"]), zoom=17)


def _street(row: dict[str, Any]) -> str:
    return STREET_VIEW.format(lat=float(row["lat"]), lon=float(row["lon"]))


def _line_poi(row: dict[str, Any], now, *, extra: bool = True) -> list[str]:
    dist = row.get("distance_km")
    dist_s = f"{dist * 1000:.0f} m" if isinstance(dist, (int, float)) and dist < 1 else (
        f"{dist:.1f} km" if isinstance(dist, (int, float)) else ""
    )
    bits = [e(str(row.get("kind") or "Luogo"))]
    if dist_s:
        bits.append(dist_s)
    bits.append(_open_label(row, now))
    lines = [f"• {e(str(row.get('name') or 'senza nome'))}", "   " + " · ".join(bits)]
    if extra:
        more = []
        if row.get("operator"):
            more.append(e(str(row["operator"])))
        if row.get("cuisine"):
            more.append(e(str(row["cuisine"]).replace(";", ", ")))
        if row.get("capacity"):
            more.append(f"capienza {e(str(row['capacity']))}")
        if more:
            lines.append("   " + " · ".join(more))
        if row.get("webcam"):
            lines.append(f"   📷 {e(str(row['webcam']))}")
        elif row.get("website"):
            lines.append(f"   🔗 {e(str(row['website']))}")
        lines.append(f"   🗺️ {e(_pin(row))}")
    return lines


def _snapshot_air(city: dict[str, Any]) -> dict[str, Any]:
    try:
        return fetch_air(float(city["lat"]), float(city["lon"]))
    except Exception:
        log.exception("air snapshot")
        return {"ok": False, "current": {}}


def _pollen_bits(cur: dict[str, Any]) -> list[str]:
    mapping = (
        ("Erba", "grass_pollen"),
        ("Betulla", "birch_pollen"),
        ("Ontano", "alder_pollen"),
        ("Artemisia", "mugwort_pollen"),
        ("Olivo", "olive_pollen"),
        ("Ambrosia", "ragweed_pollen"),
    )
    bits = []
    any_val = False
    for label, key in mapping:
        val = _num(cur.get(key))
        if val is None:
            continue
        any_val = True
        bits.append(f"{label} {val:.1f}")
    if not any_val:
        return []
    return bits


def run_near(city: dict[str, Any]) -> dict[str, Any]:
    lat, lon = float(city["lat"]), float(city["lon"])
    osm = search_around(lat, lon, "near")
    air = _snapshot_air(city)
    rows = list(osm.get("rows") or [])
    return {
        "ok": bool(osm.get("ok") or air.get("ok")),
        "kind": "near",
        "rows": rows,
        "air": air.get("current") or {},
        "air_ok": bool(air.get("ok")),
        "radius_m": osm.get("radius_m") or 1200,
        "osm_ok": bool(osm.get("ok")),
    }


def run_osm_kind(city: dict[str, Any], kind: str) -> dict[str, Any]:
    lat, lon = float(city["lat"]), float(city["lon"])
    bundle = search_around(lat, lon, kind)
    bundle["kind"] = kind
    return bundle


def run_safety(city: dict[str, Any]) -> dict[str, Any]:
    osm = run_osm_kind(city, "safety")
    cc = str(city.get("country_code") or "").lower()
    alerts = fetch_meteoalarm(cc)
    local = filter_for_city(list(alerts.get("rows") or []), city) if alerts.get("ok") else []
    return {
        "ok": bool(osm.get("ok") or alerts.get("ok")),
        "kind": "safety",
        "rows": list(osm.get("rows") or []),
        "alerts": local,
        "alerts_ok": bool(alerts.get("ok")),
        "alerts_supported": bool(alerts.get("supported", True)),
        "radius_m": osm.get("radius_m") or 3500,
        "osm_ok": bool(osm.get("ok")),
    }


def run_history(city: dict[str, Any]) -> dict[str, Any]:
    lat, lon = float(city["lat"]), float(city["lon"])
    air = fetch_air(lat, lon, past_days=7, forecast_days=1)
    weather = fetch_weather(lat, lon, past_days=7)
    return {
        "ok": bool(air.get("ok") or weather.get("ok")),
        "kind": "history",
        "rows": [],
        "air": air,
        "weather": weather,
    }


def run_compare(city: dict[str, Any], other: dict[str, Any] | None) -> dict[str, Any]:
    if not other:
        return {"ok": True, "kind": "compare", "rows": [], "other": None, "a": None, "b": None}
    a_air = fetch_air(float(city["lat"]), float(city["lon"]))
    b_air = fetch_air(float(other["lat"]), float(other["lon"]))
    a_wx = fetch_weather(float(city["lat"]), float(city["lon"]))
    b_wx = fetch_weather(float(other["lat"]), float(other["lon"]))
    dist = haversine_km(float(city["lat"]), float(city["lon"]), float(other["lat"]), float(other["lon"]))
    return {
        "ok": True,
        "kind": "compare",
        "rows": [],
        "other": other,
        "distance_km": dist,
        "a": {"air": a_air, "weather": a_wx},
        "b": {"air": b_air, "weather": b_wx},
    }


def run_life(city: dict[str, Any], query_id: str, *, other: dict[str, Any] | None = None) -> dict[str, Any]:
    qid = (query_id or "near").split(":")[0]
    if qid == "near":
        bundle = run_near(city)
    elif qid == "safety":
        bundle = run_safety(city)
    elif qid == "history":
        bundle = run_history(city)
    elif qid == "compare":
        bundle = run_compare(city, other)
    elif qid in {"mobility", "culture", "services", "walk"}:
        bundle = run_osm_kind(city, qid)
        if qid == "culture":
            now = city_now(city)
            rows = list(bundle.get("rows") or [])
            open_rows = [r for r in rows if is_open_now(r.get("opening_hours"), now) is True]
            rest = [r for r in rows if r not in open_rows]
            bundle["rows"] = open_rows + rest
    else:
        bundle = {"ok": False, "kind": "error", "rows": []}
    bundle["query"] = query_id
    return bundle


def _aqi_line(cur: dict[str, Any]) -> list[str]:
    lines = []
    aqi = _fmt(cur.get("european_aqi"))
    if aqi:
        lines.append(f"🌬️ AQI (EEA) {aqi}")
    for label, key, unit, dig in (
        ("PM2.5", "pm2_5", " μg/m³", 1),
        ("PM10", "pm10", " μg/m³", 1),
        ("NO₂", "nitrogen_dioxide", " μg/m³", 0),
        ("O₃", "ozone", " μg/m³", 0),
    ):
        val = _fmt(cur.get(key), unit, dig)
        if val:
            lines.append(f"{label}: {val}")
    pollen = _pollen_bits(cur)
    if pollen:
        lines.append("🌾 " + " · ".join(pollen[:4]))
    return lines


def _group_rows(rows: list[dict[str, Any]], groups: tuple[str, ...], *, n: int = 3) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for group in groups:
        chunk = [r for r in rows if r.get("group") == group][:n]
        out.extend(chunk)
    return out


def format_life(bundle: dict[str, Any], city: dict[str, Any], *, offset: int = 0, limit: int = DEFAULT_PAGE_SIZE) -> str:
    name = (city.get("name") or "qui").split(",")[0]
    now = city_now(city)
    kind = bundle.get("kind") or "near"
    if not bundle.get("ok") and kind not in {"compare"}:
        return clip(
            f"🏙️ <b>CITY LIFE — {e(name.upper())}</b>\n\n"
            "⚠️ Servizio temporaneamente non disponibile.\nRiprova tra poco."
        )
    if kind == "near":
        return _format_near(bundle, city, name, now, offset, limit)
    if kind == "mobility":
        return _format_mobility(bundle, name, now, offset, limit)
    if kind == "safety":
        return _format_safety(bundle, name, now, offset, limit)
    if kind == "culture":
        return _format_culture(bundle, name, now, offset, limit)
    if kind == "services":
        return _format_services(bundle, name, now, offset, limit)
    if kind == "walk":
        return _format_walk(bundle, city, name, now, offset, limit)
    if kind == "history":
        return _format_history(bundle, name)
    if kind == "compare":
        return _format_compare(bundle, city, name)
    return clip(f"🏙️ <b>CITY LIFE — {e(name.upper())}</b>\n\n🔎 Query sconosciuta.")


def _format_near(bundle: dict, city: dict, name: str, now, offset: int, limit: int) -> str:
    lat, lon = float(city["lat"]), float(city["lon"])
    lines = [
        f"📍 <b>VICINO A ME — {e(name.upper())}</b>",
        f"Raggio {int(bundle.get('radius_m') or 1200)} m",
        "",
    ]
    if bundle.get("air_ok"):
        air_lines = _aqi_line(bundle.get("air") or {})
        lines.extend(air_lines or ["🌬️ Qualità dell'aria: n/d"])
        lines.append("")
    else:
        lines.append("🌬️ Qualità dell'aria non disponibile in questo momento.")
        lines.append("")
    rows = list(bundle.get("rows") or [])
    if not rows:
        if bundle.get("osm_ok"):
            lines.append("🔎 Nessun servizio OSM in questo raggio.")
        else:
            lines.append("⚠️ Mappa OSM temporaneamente non disponibile.")
        lines.append("")
        lines.append("ℹ️ Traffico TomTom/Google, ritardi GTFS-RT e mezzi sharing occupati non sono su questo piano (servono chiavi o feed locali).")
        lines.append(f"🗺️ {e(osm_url(lat, lon, 15))}")
        lines.append(f"👁️ Street View: {e(STREET_VIEW.format(lat=lat, lon=lon))}")
        return clip("\n".join(lines))
    pick = _group_rows(
        rows,
        ("metro", "tram", "bus", "parking", "bike", "pharmacy", "hospital", "water", "wifi", "restaurant", "museum", "market"),
        n=2,
    )
    chunk = pick if offset == 0 else rows[offset : offset + limit]
    if offset == 0:
        for row in chunk:
            lines.extend(_line_poi(row, now, extra=False))
        lines.append("")
        lines.append(f"🗺️ {e(osm_url(lat, lon, 15))}")
        lines.append(f"👁️ Street View: {e(STREET_VIEW.format(lat=lat, lon=lon))}")
        lines.append("")
        lines.append("ℹ️ Traffico live, ritardi bus e posti sharing reali richiedono API locali/a pagamento. Qui: OSM + Open-Meteo.")
        return clip("\n".join(lines))
    for row in chunk:
        lines.extend(_line_poi(row, now))
        lines.append("")
    return clip("\n".join(lines).rstrip())


def _format_mobility(bundle: dict, name: str, now, offset: int, limit: int) -> str:
    rows = list(bundle.get("rows") or [])
    lines = [
        f"🚦 <b>MOBILITÀ — {e(name.upper())}</b>",
        f"Raggio {int(bundle.get('radius_m') or 2500)} m · OSM",
        "ℹ️ Niente congestione TomTom/Google né ritardi GTFS-RT su questo piano.",
        "",
    ]
    chunk = rows[offset : offset + limit]
    if not chunk:
        lines.append("🔎 Nessuna fermata, sharing, parcheggio o webcam OSM in zona.")
        return clip("\n".join(lines))
    for row in chunk:
        lines.extend(_line_poi(row, now))
        if row.get("group") == "parking" and not row.get("capacity"):
            lines.append("   🅿️ posti liberi: n/d (OSM non ha l'occupazione live)")
        if row.get("group") in {"bike", "car", "scooter"}:
            lines.append("   🚲 veicoli liberi: n/d (serve API dell'operatore)")
        lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    if len(rows) > limit:
        lines.append("")
        lines.append(f"{offset + 1}–{min(offset + limit, len(rows))} di {len(rows)}")
    return clip("\n".join(lines))


def _format_safety(bundle: dict, name: str, now, offset: int, limit: int) -> str:
    lines = [
        f"🏥 <b>SICUREZZA — {e(name.upper())}</b>",
        "",
    ]
    alerts = list(bundle.get("alerts") or [])
    if not bundle.get("alerts_supported"):
        lines.append("ℹ️ Allerte Meteoalarm non coperte per questo paese.")
        lines.append("")
    elif not bundle.get("alerts_ok"):
        lines.append("⚠️ Allerte Meteoalarm non disponibili in questo momento.")
        lines.append("")
    elif not alerts:
        lines.append("✅ Nessuna allerta gialla/arancione Meteoalarm per la zona.")
        lines.append("")
    else:
        lines.append("🚨 <b>Allerte</b> (Meteoalarm / Protezione civile nazionale)")
        for row in alerts[:8]:
            sev = e(str(row.get("severity") or ""))
            lines.append(f"• {e(str(row.get('event') or 'allerta'))} · {sev}")
            areas = ", ".join(row.get("areas") or [])
            if areas:
                lines.append(f"   📍 {e(areas)}")
            if row.get("onset") or row.get("expires"):
                lines.append(f"   🕐 {e(str(row.get('onset') or ''))} → {e(str(row.get('expires') or ''))}")
        lines.append("")
    lines.append("🏥 Ospedali e farmacie OSM. Tempi di attesa PS e farmacie di turno: API regionali, non su questo piano.")
    rows = list(bundle.get("rows") or [])
    chunk = rows[offset : offset + limit]
    if not chunk:
        lines.append("🔎 Nessun ospedale/farmacia OSM in zona.")
        return clip("\n".join(lines))
    for row in chunk:
        lines.extend(_line_poi(row, now))
        lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    if len(rows) > limit:
        lines.append("")
        lines.append(f"{offset + 1}–{min(offset + limit, len(rows))} di {len(rows)}")
    return clip("\n".join(lines))


def _format_culture(bundle: dict, name: str, now, offset: int, limit: int) -> str:
    rows = list(bundle.get("rows") or [])
    open_n = sum(1 for r in rows if is_open_now(r.get("opening_hours"), now) is True)
    lines = [
        f"🎭 <b>VITA IN CITTÀ — {e(name.upper())}</b>",
        "Cinema, teatri, mercati, musei, ristoranti OSM.",
        "ℹ️ Programmazione, sagre e posti in sala non sono su un feed libero globale.",
        "",
    ]
    if open_n:
        lines.append(f"✅ Aperti ora (orario OSM): {open_n}")
        lines.append("")
    chunk = rows[offset : offset + limit]
    if not chunk:
        lines.append("🔎 Nessun luogo di questo tipo in zona.")
        return clip("\n".join(lines))
    for row in chunk:
        lines.extend(_line_poi(row, now))
        lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    if len(rows) > limit:
        lines.append("")
        lines.append(f"{offset + 1}–{min(offset + limit, len(rows))} di {len(rows)}")
    return clip("\n".join(lines))


def _format_services(bundle: dict, name: str, now, offset: int, limit: int) -> str:
    rows = list(bundle.get("rows") or [])
    lines = [
        f"⛲ <b>SERVIZI — {e(name.upper())}</b>",
        "Fontanelle, WiFi, bagni, webcam OSM.",
        "ℹ️ Audio live della città non è su questo piano.",
        "",
    ]
    chunk = rows[offset : offset + limit]
    if not chunk:
        lines.append("🔎 Nessun servizio di questo tipo in zona.")
        return clip("\n".join(lines))
    for row in chunk:
        lines.extend(_line_poi(row, now))
        lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    if len(rows) > limit:
        lines.append("")
        lines.append(f"{offset + 1}–{min(offset + limit, len(rows))} di {len(rows)}")
    return clip("\n".join(lines))


def _format_walk(bundle: dict, city: dict, name: str, now, offset: int, limit: int) -> str:
    rows = list(bundle.get("rows") or [])
    lat, lon = float(city["lat"]), float(city["lon"])
    lines = [
        f"🚶 <b>PASSEGGIATA — {e(name.upper())}</b>",
        f"Punti entro {int(bundle.get('radius_m') or 1200)} m, dal più vicino.",
        "Non è un routing turn-by-turn: è un elenco lungo il raggio a piedi.",
        "",
    ]
    chunk = rows[offset : offset + limit]
    if not chunk:
        lines.append("🔎 Nessun punto utile per una passeggiata in questo raggio.")
        return clip("\n".join(lines))
    for i, row in enumerate(chunk, start=offset + 1):
        prefix = [f"{i}. {e(str(row.get('name') or 'luogo'))}"]
        lines.extend(prefix)
        extra = _line_poi(row, now)
        lines.extend(extra[1:])
        lines.append("")
    lines.append(f"🗺️ Partenza: {e(osm_url(lat, lon, 16))}")
    lines.append(f"👁️ Street View: {e(STREET_VIEW.format(lat=lat, lon=lon))}")
    if len(rows) > limit:
        lines.append(f"{offset + 1}–{min(offset + limit, len(rows))} di {len(rows)}")
    return clip("\n".join(lines).rstrip())


def _daily_pairs(block: dict[str, Any], key: str) -> list[tuple[str, Any]]:
    daily = block.get("daily") if isinstance(block.get("daily"), dict) else {}
    times = list(daily.get("time") or [])
    values = list(daily.get(key) or [])
    out = []
    for i, day in enumerate(times):
        out.append((str(day), values[i] if i < len(values) else None))
    return out


def _hourly_mean_by_day(hourly: dict[str, Any], key: str) -> dict[str, float]:
    times = list(hourly.get("time") or [])
    values = list(hourly.get(key) or [])
    buckets: dict[str, list[float]] = {}
    for i, stamp in enumerate(times):
        day = str(stamp)[:10]
        val = _num(values[i] if i < len(values) else None)
        if val is None:
            continue
        buckets.setdefault(day, []).append(val)
    return {day: sum(vals) / len(vals) for day, vals in buckets.items() if vals}


def _format_history(bundle: dict, name: str) -> str:
    lines = [
        f"📊 <b>STORICO — {e(name.upper())}</b>",
        "Open-Meteo: ieri e ultimi 7 giorni (modello CAMS / forecast, non stazioni ARPA).",
        "",
    ]
    weather = bundle.get("weather") or {}
    air = bundle.get("air") or {}
    if weather.get("ok"):
        tmin = dict(_daily_pairs(weather, "temperature_2m_min"))
        tmax = dict(_daily_pairs(weather, "temperature_2m_max"))
        rain = dict(_daily_pairs(weather, "precipitation_sum"))
        days = [d for d, _ in _daily_pairs(weather, "temperature_2m_max")]
        lines.append("🌤️ Meteo")
        for day in days:
            hi = _fmt(tmax.get(day), "°")
            lo = _fmt(tmin.get(day), "°")
            pr = _fmt(rain.get(day), " mm", 1)
            bits = " · ".join(x for x in (hi and f"max {hi}", lo and f"min {lo}", pr and f"pioggia {pr}") if x)
            lines.append(f"{day}: {bits or 'n/d'}")
        lines.append("")
    hourly = (air.get("hourly") or {}) if air.get("ok") else {}
    if hourly:
        aqi = _hourly_mean_by_day(hourly, "european_aqi")
        pm = _hourly_mean_by_day(hourly, "pm2_5")
        lines.append("🌬️ Aria (media giornaliera)")
        for day in sorted(set(aqi) | set(pm)):
            a = _fmt(aqi.get(day), digits=0)
            p = _fmt(pm.get(day), " μg/m³", 1)
            lines.append(f"{day}: AQI {a or 'n/d'} · PM2.5 {p or 'n/d'}")
        lines.append("")
    if len(lines) <= 4:
        lines.append("🔎 Nessuno storico disponibile per questa località.")
    lines.append("ℹ️ Rumore ambientale: nessun feed libero globale.")
    return clip("\n".join(lines).rstrip())


def _format_compare(bundle: dict, city: dict, name: str) -> str:
    other = bundle.get("other")
    if not other:
        return clip(
            f"⚖️ <b>CONFRONTO</b>\n\n"
            f"Ora sei a <b>{e(name)}</b>.\n"
            "Cambia città da 📍 e torna qui: confronto la nuova con la precedente, senza un secondo geocoding extra.\n\n"
            "<i>Niente notifiche push su questo piano (nessun database).</i>"
        )
    other_name = str(other.get("name") or "altra").split(",")[0]
    dist = bundle.get("distance_km")
    dist_s = f"{dist:.0f} km" if isinstance(dist, (int, float)) else ""
    lines = [
        f"⚖️ <b>{e(name.upper())} vs {e(other_name.upper())}</b>",
    ]
    if dist_s:
        lines.append(f"📍 {dist_s} tra i due centri")
    lines.append("")
    a = bundle.get("a") or {}
    b = bundle.get("b") or {}
    a_wx = ((a.get("weather") or {}).get("current") or {})
    b_wx = ((b.get("weather") or {}).get("current") or {})
    a_air = ((a.get("air") or {}).get("current") or {})
    b_air = ((b.get("air") or {}).get("current") or {})

    def pair(label: str, va: Any, vb: Any, unit: str = "", digits: int = 0) -> None:
        sa, sb = _fmt(va, unit, digits), _fmt(vb, unit, digits)
        if sa or sb:
            lines.append(f"{label}: {sa or 'n/d'} vs {sb or 'n/d'}")

    lines.append(f"🌤️ Meteo · {e(name)} vs {e(other_name)}")
    pair("Temperatura", a_wx.get("temperature_2m"), b_wx.get("temperature_2m"), "°C")
    pair("Umidità", a_wx.get("relative_humidity_2m"), b_wx.get("relative_humidity_2m"), "%")
    pair("Vento", a_wx.get("wind_speed_10m"), b_wx.get("wind_speed_10m"), " km/h")
    lines.append("")
    lines.append("🌬️ Aria")
    pair("AQI", a_air.get("european_aqi"), b_air.get("european_aqi"))
    pair("PM2.5", a_air.get("pm2_5"), b_air.get("pm2_5"), " μg/m³", 1)
    pair("NO₂", a_air.get("nitrogen_dioxide"), b_air.get("nitrogen_dioxide"), " μg/m³")
    lines.append("")
    lines.append("ℹ️ Traffico live non è confrontabile senza TomTom/Google.")
    return clip("\n".join(lines))


def location_hit(lat: float, lon: float, reverse: dict[str, Any] | None) -> dict[str, Any]:
    south, west, north, east = bbox_from_radius(lat, lon, 8.0)
    if reverse:
        hit = dict(reverse)
        hit["lat"] = lat
        hit["lon"] = lon
        hit["bbox"] = (south, west, north, east)
        return hit
    return {
        "name": "Qui",
        "display": f"Qui ({lat:.4f}, {lon:.4f})",
        "lat": lat,
        "lon": lon,
        "bbox": (south, west, north, east),
        "source": "telegram-location",
    }
