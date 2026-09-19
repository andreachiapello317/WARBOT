"""OSM WORLD: Overpass per categoria, dopo il geocoder. Nessuna query gigante sulla città."""

from __future__ import annotations

import html
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

from services.live.feeds import clip, e, osm_url

OVERPASS_URL = "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
USER_AGENT = "WARBOT/1.0 (OSM WORLD; Overpass)"
DEFAULT_TIMEOUT = 45
QUERY_TIMEOUT = 25
OVERPASS_RETRIES = 3
LIST_LIMIT = 12
OSM_NOTE = "OpenStreetMap via Overpass. Copertura volontaria, non un elenco ufficiale."

BBox = tuple[float, float, float, float]
_CACHE: dict[str, tuple[float, Any]] = {}

AcceptFn = Callable[[dict[str, Any]], bool]
RankFn = Callable[[dict[str, Any]], tuple]


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
    return kind not in {"heliport"}


def rank_aerodrome(row: dict[str, Any]) -> tuple:
    return (
        0 if row.get("iata") else 1,
        0 if row.get("icao") else 1,
        0 if row.get("wikidata") else 1,
        row["name"].lower(),
    )


def accept_rail(tags: dict[str, Any]) -> bool:
    railway = str(tags.get("railway") or "")
    station = str(tags.get("station") or "")
    public = str(tags.get("public_transport") or "")
    if railway in {"halt", "tram_stop", "subway_entrance", "platform", "stop", "halt_position"}:
        return False
    if public in {"stop_position", "platform"}:
        return False
    if tags.get("highway") == "bus_stop":
        return False
    if tags.get("amenity") == "bus_station" and not (_yes(tags, "train") or railway == "station"):
        return False
    if railway == "platform" or tags.get("railway") == "subway_entrance":
        return False
    subway_only = station == "subway" or (_yes(tags, "subway") and not _yes(tags, "train"))
    light = station in {"light_rail", "tram"} or (_yes(tags, "tram") and not _yes(tags, "train"))
    if subway_only or light:
        return False
    if _yes(tags, "bus") and not _yes(tags, "train") and railway != "station":
        return False
    train_station = _yes(tags, "train") or tags.get("building") == "train_station" or bool(_tag(tags, "uic_ref"))
    if train_station:
        return True
    return railway == "station" and station not in {"subway", "light_rail", "monorail", "tram"} and not _yes(tags, "subway")


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
CATEGORIES: dict[str, dict[str, Any]] = {
    "aero": {
        "id": "aero",
        "emoji": "✈️",
        "title": "Aeroporti",
        "filters": ('nwr["aeroway"="aerodrome"]',),
        "accept": accept_aerodrome,
        "rank": rank_aerodrome,
    },
    "rail": {
        "id": "rail",
        "emoji": "🚆",
        "title": "Stazioni ferroviarie",
        "filters": (
            'nwr["railway"="station"]',
            'nwr["building"="train_station"]',
        ),
        "accept": accept_rail,
        "rank": rank_rail,
    },
    "hosp": {
        "id": "hosp",
        "emoji": "🏥",
        "title": "Ospedali",
        "filters": ('nwr["amenity"="hospital"]',),
        "accept": accept_named,
        "rank": rank_wiki,
    },
    "port": {
        "id": "port",
        "emoji": "⚓",
        "title": "Porti",
        "filters": (
            'nwr["landuse"="harbour"]',
            'nwr["industrial"="port"]',
            'nwr["harbour"="yes"]',
        ),
        "accept": lambda tags: True,
        "rank": rank_wiki,
    },
    "stad": {
        "id": "stad",
        "emoji": "🏟️",
        "title": "Stadi",
        "filters": ('nwr["leisure"="stadium"]',),
        "accept": accept_named,
        "rank": rank_wiki,
    },
    "land": {
        "id": "land",
        "emoji": "🏛️",
        "title": "Luoghi principali",
        "filters": (
            'nwr["tourism"="attraction"]["wikidata"]',
            'nwr["historic"="monument"]',
            'nwr["historic"="castle"]',
            'nwr["historic"="palace"]',
            'nwr["tourism"="museum"]',
            'nwr["amenity"="townhall"]',
            'nwr["building"="cathedral"]',
        ),
        "accept": accept_named,
        "rank": rank_wiki,
    },
    "mall": {
        "id": "mall",
        "emoji": "🛍️",
        "title": "Centri commerciali",
        "filters": (
            'nwr["shop"="mall"]',
            'nwr["shop"="department_store"]',
        ),
        "accept": accept_named,
        "rank": rank_wiki,
    },
}

WORLD_CATEGORIES = ("aero", "rail", "hosp", "port", "stad", "land", "mall")

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


def _build_query(bbox: BBox, filters: tuple[str, ...], *, timeout: int = QUERY_TIMEOUT) -> str:
    area = _bbox_ql(bbox)
    union = "\n  ".join(f"{flt}{area};" for flt in filters)
    return f"[out:json][timeout:{timeout}];\n(\n  {union}\n);\nout center;"


def search(bbox: BBox | str, category: str, *, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """Una sola categoria Overpass nel bounding box (south, west, north, east)."""
    cat = resolve_category(category)
    if not cat:
        return {"ok": False, "error": f"categoria sconosciuta: {category}", "rows": [], "total": 0}
    try:
        box = parse_bbox(bbox)
    except (TypeError, ValueError) as exc:
        return {"ok": False, "error": str(exc), "rows": [], "total": 0}
    meta = CATEGORIES[cat]
    filters = tuple(meta["filters"])
    rank: RankFn = meta.get("rank") or (lambda r: (r["name"].lower(),))

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
            score = lambda r: (
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
        return {
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
        }

    return _cached(f"osm:{box}:{cat}", 180, load)


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
        "Tocca una categoria. Non scarico tutta la città in un colpo.",
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
    lines = [
        f"{bundle.get('emoji', '🗺️')} <b>{e(bundle.get('title'))}</b>{where}",
        f"{bundle.get('total', 0)} elementi · tocca una scheda",
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
