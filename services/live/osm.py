"""Query Overpass su OpenStreetMap. Nessun radar, solo mappa pubblica."""

from __future__ import annotations

import html
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from services.live.feeds import clip, e, osm_url

OVERPASS_URL = "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
USER_AGENT = "WARBOT/1.0 (live OSM; Overpass)"
DEFAULT_TIMEOUT = 45
QUERY_TIMEOUT = 25
OVERPASS_RETRIES = 3
OSM_NOTE = "Punti da OpenStreetMap via Overpass. Copertura volontaria, non un elenco ufficiale."

# south, west, north, east — Overpass (lat_min, lon_min, lat_max, lon_max)
BBox = tuple[float, float, float, float]

PLACES: dict[str, dict[str, Any]] = {
    "milano": {
        "id": "milano",
        "title": "Milano",
        "bbox": (45.3, 9.0, 45.6, 9.4),
    },
}

CATEGORIES: dict[str, dict[str, Any]] = {
    "aerodrome": {
        "id": "aerodrome",
        "emoji": "✈️",
        "title": "Aeroporti",
        "filters": ('nwr["aeroway"="aerodrome"]',),
    },
    "railway_station": {
        "id": "railway_station",
        "emoji": "🚉",
        "title": "Stazioni ferroviarie",
        "filters": ('nwr["railway"="station"]',),
    },
    "subway_station": {
        "id": "subway_station",
        "emoji": "🚇",
        "title": "Stazioni metro",
        "filters": ('nwr["station"="subway"]',),
    },
    "hospital": {
        "id": "hospital",
        "emoji": "🏥",
        "title": "Ospedali",
        "filters": ('nwr["amenity"="hospital"]',),
    },
}

# Gruppi Telegram: stazioni = ferrovia + metro
GROUPS: dict[str, dict[str, Any]] = {
    "aerodrome": {
        "id": "aerodrome",
        "emoji": "✈️",
        "title": "Aeroporti",
        "categories": ("aerodrome",),
    },
    "station": {
        "id": "station",
        "emoji": "🚉",
        "title": "Stazioni",
        "categories": ("railway_station", "subway_station"),
    },
    "hospital": {
        "id": "hospital",
        "emoji": "🏥",
        "title": "Ospedali",
        "categories": ("hospital",),
    },
}

_ALIASES = {
    "aerodrome": "aerodrome",
    "aeroporti": "aerodrome",
    "aeroporto": "aerodrome",
    "airport": "aerodrome",
    "aero": "aerodrome",
    "railway_station": "railway_station",
    "railway": "railway_station",
    "rail": "railway_station",
    "subway_station": "subway_station",
    "subway": "subway_station",
    "metro": "subway_station",
    "hospital": "hospital",
    "ospedali": "hospital",
    "ospedale": "hospital",
    "hosp": "hospital",
    "station": "station",
    "stazioni": "station",
    "stazione": "station",
}

_CACHE: dict[str, tuple[float, Any]] = {}


def resolve_place(raw: str | None) -> dict[str, Any] | None:
    key = (raw or "").strip().lower()
    aliases = {"milan": "milano", "mi": "milano"}
    key = aliases.get(key, key)
    return PLACES.get(key)


def resolve_category(raw: str | None) -> str | None:
    key = (raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    return _ALIASES.get(key)


def parse_bbox(bbox: BBox | str | tuple[float, ...]) -> BBox:
    if isinstance(bbox, str):
        parts = [p.strip() for p in bbox.replace(";", ",").split(",") if p.strip()]
        if len(parts) != 4:
            raise ValueError("bbox deve essere south,west,north,east")
        south, west, north, east = (float(p) for p in parts)
    else:
        if len(bbox) != 4:
            raise ValueError("bbox deve essere south,west,north,east")
        south, west, north, east = (float(v) for v in bbox)
    if south >= north or west >= east:
        raise ValueError("bbox invertito")
    return (south, west, north, east)


def _bbox_ql(bbox: BBox) -> str:
    south, west, north, east = bbox
    return f"({south},{west},{north},{east})"


def _cached(key: str, ttl: float, loader):
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    value = loader()
    if isinstance(value, dict) and value.get("ok"):
        _CACHE[key] = (now, value)
    return value


def overpass(query: str, *, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """Esegue una query Overpass in POST application/x-www-form-urlencoded."""
    body = urllib.parse.urlencode({"data": query}).encode("utf-8")
    last_error = "Overpass non ha risposto"
    last_detail = ""
    for attempt in range(OVERPASS_RETRIES):
        req = urllib.request.Request(
            OVERPASS_URL,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
        except TimeoutError as exc:
            last_error = f"timeout Overpass ({timeout}s)"
            last_detail = str(exc)
        except urllib.error.HTTPError as exc:
            last_error = f"HTTP {exc.code}"
            last_detail = str(exc)
            if exc.code not in {429, 502, 503, 504}:
                return {"ok": False, "error": last_error, "detail": last_detail, "elements": []}
        except urllib.error.URLError as exc:
            last_error = "Overpass non raggiungibile"
            last_detail = str(exc.reason or exc)
        else:
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                return {"ok": False, "error": "JSON Overpass non valido", "detail": str(exc), "elements": []}
            if not isinstance(payload, dict):
                return {"ok": False, "error": "payload Overpass inatteso", "elements": []}
            payload["ok"] = True
            payload.setdefault("elements", [])
            return payload
        if attempt < OVERPASS_RETRIES - 1:
            time.sleep(1.5 * (attempt + 1))
    return {"ok": False, "error": last_error, "detail": last_detail, "elements": []}


def _element_coords(el: dict[str, Any]) -> tuple[float, float] | None:
    lat, lon = el.get("lat"), el.get("lon")
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        return float(lat), float(lon)
    center = el.get("center") or {}
    lat, lon = center.get("lat"), center.get("lon")
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        return float(lat), float(lon)
    return None


def _tag(tags: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = tags.get(key)
        if value:
            return str(value).strip()
    return ""


def _classify(tags: dict[str, Any]) -> str:
    if tags.get("aeroway") == "aerodrome":
        return "aerodrome"
    if tags.get("amenity") == "hospital":
        return "hospital"
    if tags.get("station") == "subway" or (tags.get("subway") == "yes" and tags.get("railway") == "station"):
        return "subway_station"
    if tags.get("railway") == "station":
        return "railway_station"
    return ""


def normalize_element(el: dict[str, Any], *, category: str = "") -> dict[str, Any] | None:
    coords = _element_coords(el)
    if coords is None:
        return None
    lat, lon = coords
    tags = el.get("tags") or {}
    if not isinstance(tags, dict):
        tags = {}
    cat = _classify(tags) or category
    if not cat:
        return None
    name = _tag(tags, "name:it", "name", "official_name") or "senza nome"
    return {
        "id": f"{el.get('type')}/{el.get('id')}",
        "osm_type": str(el.get("type") or ""),
        "osm_id": el.get("id"),
        "name": name,
        "lat": lat,
        "lon": lon,
        "type": cat,
        "category": cat,
        "operator": _tag(tags, "operator"),
        "website": _tag(tags, "website", "contact:website"),
        "wikipedia": _tag(tags, "wikipedia"),
        "wikidata": _tag(tags, "wikidata"),
        "iata": _tag(tags, "iata"),
        "icao": _tag(tags, "icao"),
        "map": osm_url(lat, lon, 14),
    }


def _build_query(bbox: BBox, filters: tuple[str, ...], *, timeout: int = QUERY_TIMEOUT) -> str:
    area = _bbox_ql(bbox)
    union = "\n  ".join(f"{flt}{area};" for flt in filters)
    return f"[out:json][timeout:{timeout}];\n(\n  {union}\n);\nout center;"


def _filters_for(category: str) -> tuple[str, ...] | None:
    if category in GROUPS:
        filters: list[str] = []
        for cat in GROUPS[category]["categories"]:
            filters.extend(CATEGORIES[cat]["filters"])
        return tuple(filters)
    meta = CATEGORIES.get(category)
    if not meta:
        return None
    return tuple(meta["filters"])


def search(bbox: BBox | str, category: str, *, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """Cerca una categoria OSM in un bounding box (south, west, north, east)."""
    cat = resolve_category(category) or (category if category in CATEGORIES or category in GROUPS else "")
    if not cat:
        return {"ok": False, "error": f"categoria sconosciuta: {category}", "rows": [], "total": 0}
    try:
        box = parse_bbox(bbox)
    except (TypeError, ValueError) as exc:
        return {"ok": False, "error": str(exc), "rows": [], "total": 0}
    filters = _filters_for(cat)
    if not filters:
        return {"ok": False, "error": f"categoria sconosciuta: {category}", "rows": [], "total": 0}

    def load() -> dict[str, Any]:
        query = _build_query(box, filters)
        payload = overpass(query, timeout=timeout)
        if not payload.get("ok"):
            return {
                "ok": False,
                "error": payload.get("error") or "Overpass fallito",
                "detail": payload.get("detail") or "",
                "category": cat,
                "bbox": box,
                "rows": [],
                "total": 0,
                "query": query,
            }
        wanted = set(GROUPS[cat]["categories"]) if cat in GROUPS else {cat}
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for el in payload.get("elements") or []:
            if not isinstance(el, dict):
                continue
            item = normalize_element(el, category=cat if cat in CATEGORIES else "")
            if not item or item["category"] not in wanted:
                continue
            if item["id"] in seen:
                continue
            seen.add(item["id"])
            rows.append(item)
        rows.sort(key=lambda r: (r["name"].lower(), r["lat"], r["lon"]))
        label = GROUPS[cat] if cat in GROUPS else CATEGORIES[cat]
        return {
            "ok": True,
            "category": cat,
            "title": label["title"],
            "emoji": label["emoji"],
            "bbox": box,
            "rows": rows,
            "total": len(rows),
            "source": "OpenStreetMap / Overpass",
            "ts": time.time(),
            "query": query,
        }

    return _cached(f"osm:{box}:{cat}", 90, load)


def search_place(place: str, category: str | None = None, *, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    meta = resolve_place(place)
    if not meta:
        return {"ok": False, "error": f"luogo OSM non in mappa: {place}", "rows": [], "groups": {}}
    if category:
        bundle = search(meta["bbox"], category, timeout=timeout)
        bundle["place"] = meta["id"]
        bundle["place_title"] = meta["title"]
        return bundle

    groups: dict[str, list[dict[str, Any]]] = {}
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futs = {gkey: pool.submit(search, meta["bbox"], gkey, timeout=timeout) for gkey in GROUPS}
        bundles = {gkey: fut.result() for gkey, fut in futs.items()}
    for gkey, bundle in bundles.items():
        if bundle.get("ok"):
            groups[gkey] = list(bundle.get("rows") or [])
        else:
            groups[gkey] = []
            errors.append(f"{gkey}: {bundle.get('error') or 'errore'}")
    total = sum(len(rows) for rows in groups.values())
    if total == 0 and errors:
        return {
            "ok": False,
            "error": "; ".join(errors),
            "place": meta["id"],
            "place_title": meta["title"],
            "bbox": meta["bbox"],
            "groups": groups,
            "total": 0,
        }
    return {
        "ok": True,
        "place": meta["id"],
        "place_title": meta["title"],
        "bbox": meta["bbox"],
        "groups": groups,
        "total": total,
        "source": "OpenStreetMap / Overpass",
        "ts": time.time(),
        "partial": bool(errors),
        "errors": errors,
    }


def _row_line(row: dict[str, Any]) -> str:
    extra: list[str] = []
    if row.get("iata") or row.get("icao"):
        extra.append(" / ".join(p for p in (row.get("iata"), row.get("icao")) if p))
    if row.get("operator"):
        extra.append(row["operator"])
    codes = f" · {e(' · '.join(extra))}" if extra else ""
    return (
        f"• <b>{e(row['name'])}</b>{codes}\n"
        f"{row['lat']:.4f}, {row['lon']:.4f} · <a href=\"{row['map']}\">mappa</a>"
    )


def format_osm_place(bundle: dict[str, Any], *, per_group: int = 5) -> str:
    if not bundle.get("ok"):
        return (
            "🗺️ <b>LIVE OSM</b>\n\n"
            "Overpass non ha risposto.\n"
            f"<i>{e(bundle.get('error') or 'timeout')}</i>"
        )
    south, west, north, east = bundle["bbox"]
    lines = [
        f"🗺️ <b>LIVE OSM · {e(bundle.get('place_title') or bundle.get('place'))}</b>",
        f"bbox {south},{west},{north},{east}",
        f"{bundle.get('total', 0)} punti · OpenStreetMap",
        "",
    ]
    for key, group in GROUPS.items():
        rows = (bundle.get("groups") or {}).get(key) or []
        lines.append(f"{group['emoji']} <b>{group['title']}</b> ({len(rows)})")
        if not rows:
            lines.append("nessun punto in questo riquadro")
        for row in rows[:per_group]:
            lines.append(_row_line(row))
        if len(rows) > per_group:
            lines.append(f"… +{len(rows) - per_group}")
        lines.append("")
    lines.append(f"<i>{OSM_NOTE}</i>")
    return clip("\n".join(lines))


def format_osm_category(bundle: dict[str, Any], *, limit: int = 12) -> str:
    if not bundle.get("ok"):
        return (
            "🗺️ <b>LIVE OSM</b>\n\n"
            "Overpass non ha risposto.\n"
            f"<i>{e(bundle.get('error') or 'timeout')}</i>"
        )
    title = bundle.get("place_title") or ""
    head = f"{bundle.get('emoji', '🗺️')} <b>{e(bundle.get('title'))}</b>"
    if title:
        head += f" · {e(title)}"
    lines = [
        head,
        f"{bundle.get('total', 0)} punti · OpenStreetMap",
        "",
    ]
    rows = bundle.get("rows") or []
    if not rows:
        lines.append("Nessun punto in questo riquadro.")
    for row in rows[:limit]:
        lines.append(_row_line(row))
        extra = []
        if row.get("website"):
            extra.append(f'<a href="{html.escape(row["website"], quote=True)}">sito</a>')
        if row.get("wikidata"):
            extra.append(e(row["wikidata"]))
        if extra:
            lines.append(" · ".join(extra))
        lines.append("")
    if len(rows) > limit:
        lines.append(f"… +{len(rows) - limit}")
        lines.append("")
    lines.append(f"<i>{OSM_NOTE}</i>")
    return clip("\n".join(lines))
