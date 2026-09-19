"""Posizioni live da feed pubblici ADS-B / AIS / ISS. Non è un quadro operativo."""

from __future__ import annotations

import gzip
import json
import time
import urllib.error
import urllib.request
from typing import Any

from services.catalog import clip, e

USER_AGENT = "WARBOT/1.0 (educational museum; public ADS-B/AIS)"
LIVE_NOTE = (
    "Dati che aerei e navi trasmettono apertamente (ADS-B / AIS). "
    "Copertura da radioamatori e porti, non un radar militare. "
    "Non è un quadro operativo e non serve a inseguire bersagli."
)

REGIONS: dict[str, dict[str, Any]] = {
    "it": {"emoji": "🇮🇹", "title": "Italia", "lat": 42.5, "lon": 12.5, "dist": 280},
    "med": {"emoji": "🌊", "title": "Mediterraneo", "lat": 38.0, "lon": 15.5, "dist": 320},
    "eu": {"emoji": "🇪🇺", "title": "Europa centrale", "lat": 48.5, "lon": 9.0, "dist": 260},
    "uk": {"emoji": "🇬🇧", "title": "Manica", "lat": 50.7, "lon": 0.2, "dist": 200},
    "us": {"emoji": "🇺🇸", "title": "Costa est USA", "lat": 40.6, "lon": -74.0, "dist": 240},
    "jp": {"emoji": "🇯🇵", "title": "Giappone", "lat": 35.6, "lon": 139.8, "dist": 220},
}

_CACHE: dict[str, tuple[float, Any]] = {}

AIS_TYPE = {
    20: "hovercraft / WIG",
    30: "pesca",
    31: "rimorchiatore",
    33: "dredger",
    34: "immersione",
    35: "nave (categoria AIS 35)",
    36: "nave a vela",
    37: "yacht",
    40: "alta velocità",
    50: "pilota",
    51: "SAR",
    52: "rimorchiatore",
    53: "porto",
    54: "antipollution",
    55: "legge",
    58: "medicale",
    60: "passeggeri",
    70: "cargo",
    80: "tanker",
    90: "altro",
}


def _cached(key: str, ttl: float, loader):
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    value = loader()
    _CACHE[key] = (now, value)
    return value


def _get_json(url: str, headers: dict[str, str] | None = None, timeout: int = 18) -> Any:
    hdrs = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        encoding = (resp.headers.get("Content-Encoding") or "").lower()
        if encoding == "gzip" or raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        return json.loads(raw.decode("utf-8"))


def compass(deg: float | None) -> str:
    if deg is None:
        return "—"
    names = ("N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSO", "SO", "OSO", "O", "ONO", "NO", "NNO")
    return names[int((float(deg) + 11.25) % 360 // 22.5)]


def osm_url(lat: float, lon: float, zoom: int = 7) -> str:
    return f"https://www.openstreetmap.org/?mlat={lat:.4f}&mlon={lon:.4f}#map={zoom}/{lat:.4f}/{lon:.4f}"


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.replace(".", "", 1).replace("-", "", 1).isdigit():
        return float(value)
    return None


def fetch_aircraft(region: str = "it") -> dict[str, Any]:
    cfg = REGIONS.get(region) or REGIONS["it"]

    def load() -> dict[str, Any]:
        url = (
            f"https://opendata.adsb.fi/api/v2/lat/{cfg['lat']}/lon/{cfg['lon']}/dist/{cfg['dist']}"
        )
        try:
            payload = _get_json(url)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            return {"ok": False, "error": str(exc), "region": region, "rows": [], "total": 0}
        rows_raw = payload.get("aircraft") or payload.get("ac") or []
        rows: list[dict[str, Any]] = []
        for item in rows_raw:
            lat, lon = _num(item.get("lat")), _num(item.get("lon"))
            if lat is None or lon is None:
                continue
            alt = item.get("alt_baro")
            on_ground = alt == "ground" or alt == 0
            alt_n = _num(alt) if alt != "ground" else 0.0
            gs = _num(item.get("gs"))
            track = _num(item.get("track") or item.get("true_heading") or item.get("mag_heading"))
            cat = str(item.get("category") or "")
            desc = str(item.get("desc") or item.get("t") or "aereo")
            heli = cat.upper() in {"A7", "B6"} or "HELI" in desc.upper()
            rows.append(
                {
                    "hex": str(item.get("hex") or ""),
                    "flight": str(item.get("flight") or item.get("r") or "").strip() or "senza nominativo",
                    "reg": str(item.get("r") or "").strip(),
                    "type": str(item.get("t") or "").strip(),
                    "desc": desc.strip(),
                    "lat": lat,
                    "lon": lon,
                    "alt_ft": alt_n,
                    "gs_kt": gs,
                    "track": track,
                    "on_ground": bool(on_ground),
                    "heli": heli,
                    "map": osm_url(lat, lon, 8),
                }
            )
        rows.sort(key=lambda r: (r["on_ground"], -(r["alt_ft"] or 0)))
        return {
            "ok": True,
            "region": region,
            "title": cfg["title"],
            "emoji": cfg["emoji"],
            "center": {"lat": cfg["lat"], "lon": cfg["lon"], "dist": cfg["dist"]},
            "total": len(rows),
            "airborne": sum(1 for r in rows if not r["on_ground"]),
            "heli": sum(1 for r in rows if r["heli"]),
            "rows": rows,
            "source": "adsb.fi (ADS-B pubblico)",
            "ts": time.time(),
        }

    return _cached(f"ac:{region}", 20, load)


def fetch_iss() -> dict[str, Any]:
    def load() -> dict[str, Any]:
        try:
            data = _get_json("https://api.wheretheiss.at/v1/satellites/25544")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}
        lat, lon = _num(data.get("latitude")), _num(data.get("longitude"))
        if lat is None or lon is None:
            return {"ok": False, "error": "payload ISS incompleto"}
        place = ""
        try:
            geo = _get_json(f"https://api.wheretheiss.at/v1/coordinates/{lat},{lon}")
            code = str(geo.get("country_code") or "").strip()
            tz = str(geo.get("timezone_id") or "").strip()
            if code and code not in {"??", "None"}:
                place = code
            elif tz:
                place = f"acque internazionali ({tz})"
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
            place = ""
        return {
            "ok": True,
            "name": "ISS",
            "lat": lat,
            "lon": lon,
            "alt_km": _num(data.get("altitude")),
            "vel_kmh": _num(data.get("velocity")),
            "visibility": str(data.get("visibility") or ""),
            "place": place,
            "map": osm_url(lat, lon, 3),
            "source": "wheretheiss.at",
            "ts": time.time(),
        }

    return _cached("iss", 12, load)


def _ship_kind(code: Any) -> str:
    n = int(code or 0)
    if n in AIS_TYPE:
        return AIS_TYPE[n]
    base = (n // 10) * 10
    return AIS_TYPE.get(base, f"tipo AIS {n}" if n else "sconosciuto")


def fetch_ships() -> dict[str, Any]:
    def load_meta() -> dict[int, dict[str, Any]]:
        data = _get_json(
            "https://meri.digitraffic.fi/api/ais/v1/vessels",
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "Digitraffic-User": "WARBOT/1.0",
            },
            timeout=25,
        )
        out: dict[int, dict[str, Any]] = {}
        if isinstance(data, list):
            for row in data:
                mmsi = int(row.get("mmsi") or 0)
                if mmsi:
                    out[mmsi] = row
        return out

    def load() -> dict[str, Any]:
        try:
            meta = _cached("ais-meta", 600, load_meta)
            payload = _get_json(
                "https://meri.digitraffic.fi/api/ais/v1/locations",
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "Digitraffic-User": "WARBOT/1.0",
                },
                timeout=25,
            )
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            return {"ok": False, "error": str(exc), "rows": [], "total": 0}
        features = payload.get("features") if isinstance(payload, dict) else []
        rows: list[dict[str, Any]] = []
        for feat in features or []:
            geom = feat.get("geometry") or {}
            coords = geom.get("coordinates") or []
            if len(coords) < 2:
                continue
            lon, lat = _num(coords[0]), _num(coords[1])
            if lat is None or lon is None:
                continue
            props = feat.get("properties") or {}
            mmsi = int(feat.get("mmsi") or props.get("mmsi") or 0)
            info = meta.get(mmsi) or {}
            sog = _num(props.get("sog"))
            cog = _num(props.get("cog") or props.get("heading"))
            rows.append(
                {
                    "mmsi": mmsi,
                    "name": str(info.get("name") or "").strip() or f"MMSI {mmsi}",
                    "call": str(info.get("callSign") or "").strip(),
                    "kind": _ship_kind(info.get("shipType")),
                    "dest": str(info.get("destination") or "").strip(),
                    "lat": lat,
                    "lon": lon,
                    "sog_kn": sog,
                    "cog": cog,
                    "nav": int(props.get("navStat") or 0),
                    "map": osm_url(lat, lon, 8),
                }
            )
        moving = [r for r in rows if (r["sog_kn"] or 0) >= 0.5]
        moving.sort(key=lambda r: -(r["sog_kn"] or 0))
        return {
            "ok": True,
            "title": "Mar Baltico (AIS aperto Finlandia)",
            "emoji": "⚓",
            "total": len(rows),
            "moving": len(moving),
            "rows": moving or rows,
            "source": "Digitraffic / Traficom (AIS pubblico, acque finlandesi)",
            "updated": payload.get("dataUpdatedTime") if isinstance(payload, dict) else "",
            "ts": time.time(),
        }

    return _cached("ships", 25, load)


def format_live_hub() -> str:
    return (
        "📡 <b>LIVE</b>\n\n"
        "Posizioni vere, adesso, da radio aperte.\n\n"
        "✈️ <b>Aerei</b> — ADS-B pubblico (adsb.fi), zone a scelta\n"
        "🚁 <b>Elicotteri</b> — stesso feed, solo categoria eli\n"
        "⚓ <b>Navi</b> — AIS aperto del Baltico finlandese\n"
        "🛰️ <b>ISS</b> — stazione spaziale, lat/lon/altezza\n\n"
        f"<i>{LIVE_NOTE}</i>"
    )


def format_aircraft(bundle: dict[str, Any], *, heli_only: bool = False) -> str:
    if not bundle.get("ok"):
        return (
            "✈️ <b>AEREI</b>\n\n"
            "Il feed ADS-B non ha risposto. Riprova tra qualche secondo.\n"
            f"<i>{e(bundle.get('error') or 'timeout')}</i>"
        )
    rows = [r for r in bundle.get("rows") or [] if (r["heli"] if heli_only else True)]
    title = "ELICOTTERI" if heli_only else "AEREI"
    lines = [
        f"{bundle.get('emoji', '✈️')} <b>{title} · {e(bundle.get('title'))}</b>",
        f"In zona: {bundle.get('total', 0)} tracciati, {bundle.get('airborne', 0)} in volo"
        + (f", {bundle.get('heli', 0)} eli" if not heli_only else ""),
        f"Fonte: {e(bundle.get('source'))}",
        "",
    ]
    shown = [r for r in rows if not r["on_ground"]][:10] or rows[:10]
    if not shown:
        lines.append("Nessun contatto in questa finestra.")
    for row in shown:
        alt = "al suolo" if row["on_ground"] else f"{int(row['alt_ft'] or 0)} ft"
        spd = f"{int(row['gs_kt'] or 0)} kt" if row["gs_kt"] else "—"
        icon = "🚁" if row["heli"] else "✈️"
        lines.append(
            f"{icon} <b>{e(row['flight'])}</b> · {e(row['desc'])}\n"
            f"{alt} · {spd} · {compass(row['track'])} · "
            f"{row['lat']:.2f}, {row['lon']:.2f}"
        )
        lines.append(f"<a href=\"{row['map']}\">mappa</a>")
        lines.append("")
    lines.append(f"<i>{LIVE_NOTE}</i>")
    return clip("\n".join(lines))


def format_ships(bundle: dict[str, Any]) -> str:
    if not bundle.get("ok"):
        return (
            "⚓ <b>NAVI</b>\n\n"
            "Il feed AIS non ha risposto.\n"
            f"<i>{e(bundle.get('error') or 'timeout')}</i>\n\n"
            "Il feed aperto che usiamo copre le acque finlandesi (Digitraffic)."
        )
    lines = [
        f"⚓ <b>NAVI LIVE</b>",
        e(bundle.get("title") or ""),
        f"Contatti: {bundle.get('total', 0)} · in moto: {bundle.get('moving', 0)}",
        f"Fonte: {e(bundle.get('source'))}",
        "",
    ]
    for row in (bundle.get("rows") or [])[:10]:
        spd = f"{row['sog_kn']:.1f} kn" if row.get("sog_kn") is not None else "—"
        dest = f" → {e(row['dest'])}" if row.get("dest") else ""
        lines.append(
            f"🚢 <b>{e(row['name'])}</b> · {e(row['kind'])}{dest}\n"
            f"{spd} · {compass(row['cog'])} · {row['lat']:.2f}, {row['lon']:.2f}"
        )
        lines.append(f"<a href=\"{row['map']}\">mappa</a>")
        lines.append("")
    lines.append(
        "Non esiste un AIS mondiale gratis e stabile senza chiave: "
        "qui mostriamo un mare vero, in diretta, da un ente pubblico."
    )
    lines.append("")
    lines.append(f"<i>{LIVE_NOTE}</i>")
    return clip("\n".join(lines))


def format_iss(bundle: dict[str, Any]) -> str:
    if not bundle.get("ok"):
        return f"🛰️ <b>ISS</b>\n\nNon riesco a interrogare la stazione.\n<i>{e(bundle.get('error') or '')}</i>"
    vis = {"daylight": "al sole", "eclipsed": "in ombra", "visible": "visibile"}.get(
        bundle.get("visibility") or "", bundle.get("visibility") or "—"
    )
    place = bundle.get("place") or "posizione non etichettata"
    return clip(
        "\n".join(
            [
                "🛰️ <b>STAZIONE SPAZIALE INTERNAZIONALE</b>",
                f"📍 {bundle['lat']:.2f}, {bundle['lon']:.2f} · {e(place)}",
                f"📏 Altitudine {bundle.get('alt_km') or 0:.0f} km",
                f"💨 {bundle.get('vel_kmh') or 0:.0f} km/h",
                f"☀️ {e(vis)}",
                f"<a href=\"{bundle['map']}\">mappa</a>",
                "",
                "Fonte: wheretheiss.at",
                f"<i>{LIVE_NOTE}</i>",
            ]
        )
    )
