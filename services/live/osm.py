"""OSM WORLD: Overpass per categoria, dopo il geocoder. Nessuna query gigante sulla città."""

from __future__ import annotations

import html
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

from services.live import cache as osm_cache

TELEGRAM_MAX_LEN = 3900

OVERPASS_URL = "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
USER_AGENT = "WARBOT/1.0 (OSM WORLD; Overpass)"
DEFAULT_TIMEOUT = osm_cache.int_env("OSM_OVERPASS_TIMEOUT", 18, lo=8, hi=30)
QUERY_TIMEOUT = osm_cache.int_env("OSM_OVERPASS_QL_TIMEOUT", 14, lo=6, hi=25)
OVERPASS_RETRIES = osm_cache.int_env("OSM_OVERPASS_RETRIES", 2, lo=1, hi=3)
OUT_LIMIT = osm_cache.int_env("OSM_OVERPASS_LIMIT", 40, lo=8, hi=120)
LIST_LIMIT = 12
QUERY_VER = "3"
OSM_NOTE = "OpenStreetMap via Overpass. Copertura volontaria, non un elenco ufficiale."

BBox = tuple[float, float, float, float]

AcceptFn = Callable[[dict[str, Any]], bool]
RankFn = Callable[[dict[str, Any]], tuple]


def e(text: Any) -> str:
    return html.escape(str(text), quote=False)


def clip(text: str, limit: int = TELEGRAM_MAX_LEN) -> str:
    text = str(text)
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def osm_url(lat: float, lon: float, zoom: int = 7) -> str:
    return f"https://www.openstreetmap.org/?mlat={lat:.4f}&mlon={lon:.4f}#map={zoom}/{lat:.4f}/{lon:.4f}"


def _tag(tags: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = tags.get(key)
        if value:
            return str(value).strip()
    return ""


def _yes(tags: dict[str, Any], *keys: str) -> bool:
    return any(str(tags.get(k) or "").lower() in {"yes", "1", "true"} for k in keys)


def accept_aerodrome(tags: dict[str, Any]) -> bool:
    if tags.get("aeroway") != "aerodrome":
        return False
    kind = str(tags.get("aerodrome") or "").lower()
    return kind not in {"heliport", "airstrip", "helipad"}


def rank_aerodrome(row: dict[str, Any]) -> tuple:
    return (
        0 if row.get("iata") else 1,
        0 if row.get("icao") else 1,
        0 if row.get("wikidata") else 1,
        row["name"].lower(),
    )


def accept_rail(tags: dict[str, Any]) -> bool:
    """Rete di sicurezza: la query Overpass è già selettiva."""
    railway = str(tags.get("railway") or "")
    station = str(tags.get("station") or "").lower()
    public = str(tags.get("public_transport") or "")
    if railway in {"halt", "tram_stop", "subway_entrance", "platform", "stop", "halt_position", "tram"}:
        return False
    if public in {"stop_position", "platform", "stop_area"}:
        return False
    if tags.get("highway") == "bus_stop":
        return False
    if tags.get("amenity") == "bus_station" and not (_yes(tags, "train") or railway == "station"):
        return False
    if station in {"subway", "light_rail", "tram", "monorail"}:
        return False
    if _yes(tags, "subway") and not _yes(tags, "train"):
        return False
    if _yes(tags, "tram", "light_rail") and not _yes(tags, "train"):
        return False
    if _yes(tags, "bus") and not _yes(tags, "train") and railway != "station":
        return False
    train_station = _yes(tags, "train") or tags.get("building") == "train_station" or bool(_tag(tags, "uic_ref"))
    if not train_station:
        return False
    name = _tag(tags, "name:it", "name", "official_name").lower()
    if any(bit in name for bit in ("bivio", "cabina", "deposito", "scalo merci", "terminali italia")):
        return False
    if str(tags.get("usage") or "").lower() in {"industrial", "military", "freight"}:
        return False
    return True


def rank_rail(row: dict[str, Any]) -> tuple:
    tags = row.get("tags") or {}
    return (
        0 if _tag(tags, "uic_ref") else 1,
        0 if _yes(tags, "train") else 1,
        0 if tags.get("building") == "train_station" else 1,
        0 if row.get("wikidata") or row.get("wikipedia") else 1,
        row["name"].lower(),
    )


def accept_named(tags: dict[str, Any]) -> bool:
    return bool(_tag(tags, "name:it", "name", "official_name"))


def rank_wiki(row: dict[str, Any]) -> tuple:
    return (
        0 if row.get("wikidata") else 1,
        0 if row.get("wikipedia") else 1,
        0 if row.get("website") else 1,
        row["name"].lower(),
    )


# Filtri Overpass: una categoria per tap. south,west,north,east nel QL.
# nw (niente relations) + tag selettivi + out center LIMIT. Niente download-tutto.
CATEGORIES: dict[str, dict[str, Any]] = {
    "aero": {
        "id": "aero",
        "emoji": "✈️",
        "title": "Aeroporti",
        "filters": (
            'nw["aeroway"="aerodrome"]["iata"]',
            'nw["aeroway"="aerodrome"]["name"]',
        ),
        "accept": accept_aerodrome,
        "rank": rank_aerodrome,
        "out_limit": 24,
    },
    "rail": {
        "id": "rail",
        "emoji": "🚆",
        "title": "Stazioni principali",
        "filters": (
            'nw["railway"="station"]["train"="yes"]',
            'nw["building"="train_station"]["name"]',
        ),
        "accept": accept_rail,
        "rank": rank_rail,
        "out_limit": 40,
    },
    "hosp": {
        "id": "hosp",
        "emoji": "🏥",
        "title": "Ospedali",
        "filters": ('nw["amenity"="hospital"]["name"]',),
        "accept": accept_named,
        "rank": rank_wiki,
        "out_limit": 40,
    },
    "port": {
        "id": "port",
        "emoji": "⚓",
        "title": "Porti",
        "filters": (
            'nw["industrial"="port"]["name"]',
            'nw["landuse"="harbour"]["name"]',
            'nw["harbour"="yes"]["name"]',
        ),
        "accept": accept_named,
        "rank": rank_wiki,
        "out_limit": 24,
    },
    "stad": {
        "id": "stad",
        "emoji": "🏟️",
        "title": "Stadi",
        "filters": ('nw["leisure"="stadium"]["name"]',),
        "accept": accept_named,
        "rank": rank_wiki,
        "out_limit": 30,
    },
    "mall": {
        "id": "mall",
        "emoji": "🏬",
        "title": "Centri commerciali",
        "filters": (
            'nw["shop"="mall"]["name"]',
            'nw["shop"="department_store"]["name"]',
        ),
        "accept": accept_named,
        "rank": rank_wiki,
        "out_limit": 30,
    },
    "land": {
        "id": "land",
        "emoji": "🏛️",
        "title": "Luoghi principali",
        "filters": (
            'nw["tourism"="attraction"]["wikidata"]["name"]',
            'nw["historic"="castle"]["name"]',
            'nw["historic"="palace"]["name"]',
            'nw["historic"="monument"]["wikidata"]',
            'nw["amenity"="townhall"]["name"]',
            'nw["building"="cathedral"]["name"]',
        ),
        "accept": accept_named,
        "rank": rank_wiki,
        "out_limit": 40,
    },
}

WORLD_CATEGORIES = ("aero", "rail", "hosp", "port", "stad", "mall", "land")

_ALIASES = {
    "aero": "aero",
    "aerodrome": "aero",
    "aeroporti": "aero",
    "aeroporto": "aero",
    "airport": "aero",
    "rail": "rail",
    "railway": "rail",
    "railway_station": "rail",
    "station": "rail",
    "stazioni": "rail",
    "stazione": "rail",
    "hosp": "hosp",
    "hospital": "hosp",
    "ospedali": "hosp",
    "ospedale": "hosp",
    "port": "port",
    "porti": "port",
    "porto": "port",
    "harbour": "port",
    "stad": "stad",
    "stadi": "stad",
    "stadio": "stad",
    "stadium": "stad",
    "land": "land",
    "luoghi": "land",
    "monumenti": "land",
    "mall": "mall",
    "centri": "mall",
    "shopping": "mall",
}


def resolve_category(raw: str | None) -> str | None:
    key = (raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    return _ALIASES.get(key) if key in _ALIASES else (key if key in CATEGORIES else None)


def parse_bbox(bbox: BBox | str | tuple[float, ...] | list[float]) -> BBox:
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


def _cache_key(bbox: BBox, cat: str) -> str:
    south, west, north, east = bbox
    return f"osm:{QUERY_VER}:{south:.4f},{west:.4f},{north:.4f},{east:.4f}:{cat}"


def _copy_bundle(bundle: dict[str, Any], *, cached: bool) -> dict[str, Any]:
    rows = list(bundle.get("rows") or [])
    out = dict(bundle)
    out["rows"] = rows
    out["cached"] = cached
    return out


def peek(bbox: BBox | str, category: str) -> dict[str, Any] | None:
    """Risultato categoria in cache, senza Overpass. None se assente o scaduto."""
    cat = resolve_category(category)
    if not cat:
        return None
    try:
        box = parse_bbox(bbox)
    except (TypeError, ValueError):
        return None
    hit = osm_cache.get(_cache_key(box, cat))
    if isinstance(hit, dict) and hit.get("ok"):
        return _copy_bundle(hit, cached=True)
    return None


def overpass(query: str, *, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """POST application/x-www-form-urlencoded, parametro data=."""
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
            time.sleep(0.6 * (attempt + 1))
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


def wikipedia_url(tag: str) -> str:
    if not tag:
        return ""
    if ":" in tag:
        lang, title = tag.split(":", 1)
        slug = urllib.parse.quote(title.replace(" ", "_"))
        return f"https://{lang}.wikipedia.org/wiki/{slug}"
    return f"https://en.wikipedia.org/wiki/{urllib.parse.quote(tag.replace(' ', '_'))}"


def wikidata_url(qid: str) -> str:
    if not qid:
        return ""
    return f"https://www.wikidata.org/wiki/{urllib.parse.quote(qid)}"


def normalize_element(el: dict[str, Any], *, category: str) -> dict[str, Any] | None:
    coords = _element_coords(el)
    if coords is None:
        return None
    lat, lon = coords
    tags = el.get("tags") or {}
    if not isinstance(tags, dict):
        tags = {}
    meta = CATEGORIES.get(category) or {}
    accept: AcceptFn = meta.get("accept") or (lambda _t: True)
    if not accept(tags):
        return None
    name = _tag(tags, "name:it", "name", "official_name", "alt_name") or "senza nome"
    wiki = _tag(tags, "wikipedia")
    qid = _tag(tags, "wikidata")
    site = _tag(tags, "website", "contact:website", "url")
    return {
        "id": f"{el.get('type')}/{el.get('id')}",
        "osm_type": str(el.get("type") or ""),
        "osm_id": el.get("id"),
        "name": name,
        "lat": lat,
        "lon": lon,
        "type": category,
        "category": category,
        "operator": _tag(tags, "operator"),
        "website": site,
        "wikipedia": wiki,
        "wikipedia_url": wikipedia_url(wiki),
        "wikidata": qid,
        "wikidata_url": wikidata_url(qid),
        "iata": _tag(tags, "iata"),
        "icao": _tag(tags, "icao"),
        "uic": _tag(tags, "uic_ref"),
        "building": _tag(tags, "building"),
        "train": _tag(tags, "train"),
        "map": osm_url(lat, lon, 15),
        "tags": tags,
    }


def _build_query(bbox: BBox, filters: tuple[str, ...], *, timeout: int, limit: int) -> str:
    area = _bbox_ql(bbox)
    union = "\n  ".join(f"{flt}{area};" for flt in filters)
    return (
        f"[out:json][timeout:{timeout}][maxsize:8388608];\n"
        f"(\n  {union}\n);\n"
        f"out center {limit};"
    )


def search(bbox: BBox | str, category: str, *, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """Una sola categoria Overpass nel bounding box (south, west, north, east)."""
    cat = resolve_category(category)
    if not cat:
        return {"ok": False, "error": f"categoria sconosciuta: {category}", "rows": [], "total": 0}
    try:
        box = parse_bbox(bbox)
    except (TypeError, ValueError) as exc:
        return {"ok": False, "error": str(exc), "rows": [], "total": 0}

    hit = peek(box, cat)
    if hit is not None:
        return hit

    meta = CATEGORIES[cat]
    filters = tuple(meta["filters"])
    rank: RankFn = meta.get("rank") or (lambda r: (r["name"].lower(),))
    limit = int(meta.get("out_limit") or OUT_LIMIT)
    query = _build_query(box, filters, timeout=QUERY_TIMEOUT, limit=limit)
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
            "cached": False,
        }
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for el in payload.get("elements") or []:
        if not isinstance(el, dict):
            continue
        item = normalize_element(el, category=cat)
        if not item or item["id"] in seen:
            continue
        seen.add(item["id"])
        rows.append(item)
    merged: dict[tuple, dict[str, Any]] = {}
    for item in rows:
        key = (item["name"].lower(), round(item["lat"], 3), round(item["lon"], 3))
        prev = merged.get(key)
        if prev is None:
            merged[key] = item
            continue

        def score(r: dict[str, Any]) -> tuple:
            return (
                bool(r.get("uic")),
                bool(r.get("iata")),
                bool(r.get("wikidata")),
                bool(r.get("website")),
                r.get("osm_type") == "way",
            )

        if score(item) > score(prev):
            merged[key] = item
    rows = list(merged.values())
    rows.sort(key=rank)
    for item in rows:
        item.pop("tags", None)
    bundle = {
        "ok": True,
        "category": cat,
        "title": meta["title"],
        "emoji": meta["emoji"],
        "bbox": box,
        "rows": rows,
        "total": len(rows),
        "source": "OpenStreetMap / Overpass",
        "ts": time.time(),
        "query": query,
        "cached": False,
    }
    osm_cache.put(_cache_key(box, cat), {k: v for k, v in bundle.items() if k != "cached"}, osm_cache.OVERPASS_TTL)
    return bundle


def format_osm_world() -> str:
    return (
        "🌍 <b>OSM WORLD</b>\n\n"
        "🔎 Scrivi una città, paese o località:\n\n"
        "<i>Tokyo</i>\n"
        "<i>Parigi</i>\n"
        "<i>New York</i>\n"
        "<i>Milano</i>\n"
        "<i>Buenos Aires</i>\n"
        "<i>Singapore</i>\n\n"
        "Poi scegli una categoria. Overpass parte solo a quel punto.\n\n"
        f"<i>{OSM_NOTE}</i>"
    )


def format_osm_hits(query: str, hits: list[dict[str, Any]]) -> str:
    lines = [
        "🌍 <b>OSM WORLD</b>",
        f"🔎 {e(query)} — più di un risultato. Tocca il luogo.",
        "",
    ]
    for i, hit in enumerate(hits[:5], 1):
        lines.append(f"{i}. <b>{e(hit['display'])}</b>")
        lines.append(f"{hit['lat']:.3f}, {hit['lon']:.3f}")
    lines.append("")
    lines.append(f"<i>{OSM_NOTE}</i>")
    return clip("\n".join(lines))


def format_osm_place(place: dict[str, Any]) -> str:
    note = place.get("bbox_note") or ""
    lines = [
        "🌍 <b>OSM WORLD</b>",
        f"📍 <b>{e(place.get('display') or place.get('name'))}</b>",
        f"{place['lat']:.4f}, {place['lon']:.4f}",
        "",
        "Tocca una categoria. Overpass parte solo allora.",
    ]
    if note:
        lines.append("")
        lines.append(f"<i>{e(note)}</i>")
    lines += ["", f"<i>{OSM_NOTE}</i>"]
    return clip("\n".join(lines))


def _row_line(row: dict[str, Any]) -> str:
    extra: list[str] = []
    if row.get("iata") or row.get("icao"):
        extra.append(" / ".join(p for p in (row.get("iata"), row.get("icao")) if p))
    if row.get("uic"):
        extra.append(f"UIC {row['uic']}")
    if row.get("operator"):
        extra.append(row["operator"])
    codes = f" · {e(' · '.join(extra))}" if extra else ""
    return f"• <b>{e(row['name'])}</b>{codes}"


def format_osm_category(bundle: dict[str, Any], place: dict[str, Any] | None = None, *, limit: int = LIST_LIMIT) -> str:
    if not bundle.get("ok"):
        return (
            "🌍 <b>OSM WORLD</b>\n\n"
            "Overpass non ha risposto.\n"
            f"<i>{e(bundle.get('error') or 'timeout')}</i>"
        )
    where = ""
    if place:
        where = f" · {e(place.get('display') or place.get('name'))}"
    cached = " · cache" if bundle.get("cached") else ""
    lines = [
        f"{bundle.get('emoji', '🗺️')} <b>{e(bundle.get('title'))}</b>{where}",
        f"{bundle.get('total', 0)} elementi{cached} · tocca una scheda",
        "",
    ]
    rows = bundle.get("rows") or []
    if not rows:
        lines.append("Niente in questa categoria nel riquadro.")
    for row in rows[:limit]:
        lines.append(_row_line(row))
    if len(rows) > limit:
        lines.append(f"… +{len(rows) - limit}")
    lines += ["", f"<i>{OSM_NOTE}</i>"]
    return clip("\n".join(lines))


def format_osm_item(row: dict[str, Any], place: dict[str, Any] | None = None) -> str:
    cat = CATEGORIES.get(row.get("category") or "", {})
    head = f"{cat.get('emoji', '📍')} <b>{e(row['name'])}</b>"
    lines = ["🌍 <b>OSM WORLD</b>", head]
    if place:
        lines.append(f"📍 {e(place.get('display') or place.get('name'))}")
    lines.append(f"{row['lat']:.5f}, {row['lon']:.5f}")
    bits = []
    if row.get("iata"):
        bits.append(f"IATA {e(row['iata'])}")
    if row.get("icao"):
        bits.append(f"ICAO {e(row['icao'])}")
    if row.get("uic"):
        bits.append(f"UIC {e(row['uic'])}")
    if row.get("operator"):
        bits.append(e(row["operator"]))
    if row.get("building"):
        bits.append(e(row["building"]))
    if row.get("train") == "yes":
        bits.append("train=yes")
    if bits:
        lines.append(" · ".join(bits))
    if row.get("website"):
        lines.append(f'<a href="{html.escape(row["website"], quote=True)}">sito</a>')
    if row.get("wikipedia_url"):
        lines.append(f'<a href="{html.escape(row["wikipedia_url"], quote=True)}">Wikipedia</a> · {e(row["wikipedia"])}')
    if row.get("wikidata_url"):
        lines.append(f'<a href="{html.escape(row["wikidata_url"], quote=True)}">Wikidata {e(row["wikidata"])}</a>')
    lines.append(f'<a href="{row["map"]}">mappa OpenStreetMap</a>')
    lines += ["", f"<i>{OSM_NOTE}</i>"]
    return clip("\n".join(lines))


def format_osm_map(place: dict[str, Any]) -> str:
    lat, lon = place["lat"], place["lon"]
    south, west, north, east = place["bbox"]
    overview = f"https://www.openstreetmap.org/#map=12/{lat:.4f}/{lon:.4f}"
    marker = osm_url(lat, lon, 12)
    return clip(
        "\n".join(
            [
                "🗺️ <b>MAPPA</b>",
                f"📍 <b>{e(place.get('display') or place.get('name'))}</b>",
                f"{lat:.4f}, {lon:.4f}",
                f"bbox {south:.3f},{west:.3f},{north:.3f},{east:.3f}",
                f'<a href="{overview}">apri la zona</a>',
                f'<a href="{marker}">segnaposto sul centro</a>',
                "",
                "Le categorie restano liste e schede. La mappa è il foglio OSM del luogo.",
                f"<i>{OSM_NOTE}</i>",
            ]
        )
    )
