"""OSM WORLD: Overpass per categoria, dopo il geocoder. Nessuna query gigante sulla città."""

from __future__ import annotations

import html
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

from services.live import cache as osm_cache
from services.live.engine import FALLBACK_MIN, PAGE_CAP, PAGE_SIZE, compile_query, timed

log = logging.getLogger("warbot.osm")

TELEGRAM_MAX_LEN = 3900

OVERPASS_URL = "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
USER_AGENT = "WARBOT/1.0 (OSM WORLD; Overpass)"
DEFAULT_TIMEOUT = osm_cache.int_env("OSM_OVERPASS_TIMEOUT", 18, lo=8, hi=30)
QUERY_TIMEOUT = osm_cache.int_env("OSM_OVERPASS_QL_TIMEOUT", 14, lo=6, hi=25)
OVERPASS_RETRIES = osm_cache.int_env("OSM_OVERPASS_RETRIES", 1, lo=1, hi=3)
OUT_LIMIT = osm_cache.int_env("OSM_OVERPASS_LIMIT", 80, lo=20, hi=120)
RESULT_LIMIT = PAGE_SIZE
LIST_LIMIT = PAGE_SIZE
QUERY_VER = "8"
OSM_NOTE = "OpenStreetMap via Overpass. Copertura volontaria, non un elenco ufficiale."

BBox = tuple[float, float, float, float]

AcceptFn = Callable[[dict[str, Any]], bool]
ScoreFn = Callable[[dict[str, Any], dict[str, Any]], int]


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


def accept_rail(tags: dict[str, Any]) -> bool:
    """Rete di sicurezza: la query Overpass è già selettiva (niente dump railway=station)."""
    railway = str(tags.get("railway") or "")
    station = str(tags.get("station") or "").lower()
    public = str(tags.get("public_transport") or "")
    if railway in {"halt", "tram_stop", "subway_entrance", "platform", "stop", "halt_position", "tram"}:
        return False
    if public in {"stop_position", "platform"}:
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
        if railway != "station" or not accept_named(tags):
            return False
        if _yes(tags, "subway", "tram", "light_rail"):
            return False
    name = _tag(tags, "name:it", "name", "official_name").lower()
    if any(bit in name for bit in ("bivio", "cabina", "deposito", "scalo merci", "terminali italia")):
        return False
    if str(tags.get("usage") or "").lower() in {"industrial", "military", "freight"}:
        return False
    return True


def accept_named(tags: dict[str, Any]) -> bool:
    return bool(_tag(tags, "name:it", "name", "official_name"))


def accept_port(tags: dict[str, Any]) -> bool:
    if tags.get("leisure") == "marina":
        return False
    if tags.get("man_made") in {"pier", "jetty", "quay", "slipway", "breakwater"}:
        return False
    if str(tags.get("harbour") or "").lower() in {"basin", "pier", "marina"}:
        return False
    if tags.get("mooring") and tags.get("industrial") != "port":
        return False
    return accept_named(tags)


def accept_stadium(tags: dict[str, Any]) -> bool:
    return tags.get("leisure") == "stadium" and accept_named(tags)


_GROCERY_MARKERS = (
    "conad",
    "lidl",
    "eurospin",
    "esselunga",
    "penny",
    "aldi",
    "despar",
    "iperal",
    "carrefour express",
    "carrefour market",
    "md discount",
)
_NOT_MALL = (
    "muji",
    "pepco",
    "pylones",
    "koko",
    "io bimbo",
    "altromercato",
    "multistock",
    "upim",
)
_NAME_PREFIXES = (
    "stazione di ",
    "stazione ",
    "ex stazione di ",
    "ex stazione ",
    "centro commerciale ",
    "shopville ",
    "nca ",
    "nuovo complesso aziendale ",
)
_MAJOR_RAIL = (
    ("centrale", 8),
    ("porta nuova", 8),
    ("termini", 8),
    ("porta susa", 7),
    ("porta garibaldi", 7),
    ("lingotto", 7),
    ("cadorna", 5),
    ("lambrate", 4),
)


def _blob(*parts: Any) -> str:
    return " ".join(str(p or "") for p in parts).lower()


def _norm_place_name(name: str) -> str:
    n = " ".join(str(name or "").lower().split())
    changed = True
    while changed:
        changed = False
        for prefix in _NAME_PREFIXES:
            if n.startswith(prefix):
                n = n[len(prefix) :].strip()
                changed = True
    return n


def _prefer_name(left: str, right: str) -> str:
    def rank(n: str) -> tuple:
        nl = n.lower()
        return (
            nl.startswith("ex "),
            nl.startswith("stazione"),
            "complesso aziendale" in nl,
            n.startswith("NCA "),
            len(n),
        )

    return left if rank(left) <= rank(right) else right


def _cluster_key(item: dict[str, Any]) -> tuple:
    name = _norm_place_name(item.get("name") or "")
    return ("g", name, round(float(item["lat"]), 2), round(float(item["lon"]), 2))


def _merge_items(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    tags = {**(left.get("tags") or {}), **(right.get("tags") or {})}
    out = dict(left)
    out["tags"] = tags
    out["name"] = _prefer_name(str(left.get("name") or ""), str(right.get("name") or ""))
    for key in (
        "uic",
        "iata",
        "icao",
        "operator",
        "website",
        "wikipedia",
        "wikipedia_url",
        "wikidata",
        "wikidata_url",
        "building",
        "train",
    ):
        if not out.get(key) and right.get(key):
            out[key] = right[key]
    if not out.get("uic"):
        out["uic"] = _tag(tags, "uic_ref")
    if not out.get("train"):
        out["train"] = _tag(tags, "train")
    if not out.get("building"):
        out["building"] = _tag(tags, "building")
    if not out.get("operator"):
        out["operator"] = _tag(tags, "operator")
    if not out.get("website"):
        out["website"] = _tag(tags, "website", "contact:website")
    if not out.get("wikidata"):
        qid = _tag(tags, "wikidata")
        out["wikidata"] = qid
        out["wikidata_url"] = wikidata_url(qid) if qid else ""
    if not out.get("wikipedia"):
        wiki = _tag(tags, "wikipedia")
        out["wikipedia"] = wiki
        out["wikipedia_url"] = wikipedia_url(wiki) if wiki else ""
    out["score"] = importance_score(out)
    return out


def accept_mall(tags: dict[str, Any]) -> bool:
    shop = tags.get("shop")
    blob = _blob(_tag(tags, "name", "brand", "operator"))
    if any(mark in blob for mark in _GROCERY_MARKERS) or any(mark in blob for mark in _NOT_MALL):
        return False
    if shop == "mall":
        return accept_named(tags)
    if shop == "department_store":
        if _tag(tags, "wikipedia", "wikidata"):
            return accept_named(tags)
        brand = _blob(_tag(tags, "brand", "name"))
        return "rinascente" in brand or brand.strip() == "coin"
    return False


def score_aero(_row: dict[str, Any], tags: dict[str, Any]) -> int:
    extra = 0
    kind = str(tags.get("aerodrome") or tags.get("aerodrome:type") or "").lower()
    if "international" in kind:
        extra += 3
    if _tag(tags, "wikidata"):
        extra += 2
    return extra


def score_rail(row: dict[str, Any], tags: dict[str, Any]) -> int:
    extra = 0
    if _tag(tags, "platforms"):
        extra += 2
        try:
            if int(str(_tag(tags, "platforms")).split(";")[0]) >= 5:
                extra += 2
        except ValueError:
            pass
    if tags.get("public_transport") == "station":
        extra += 2
    if row.get("wikidata") or _tag(tags, "wikidata"):
        extra += 4
    if row.get("wikipedia") or _tag(tags, "wikipedia"):
        extra += 3
    name = _blob(row.get("name"), _tag(tags, "name:it", "name"))
    if name.startswith("ex ") or "ex stazione" in name:
        extra -= 12
    for hint, pts in _MAJOR_RAIL:
        if hint in name:
            extra += pts
            break
    clat, clon = row.get("_clat"), row.get("_clon")
    if isinstance(clat, (int, float)) and isinstance(clon, (int, float)):
        dist = ((float(row["lat"]) - float(clat)) ** 2 + (float(row["lon"]) - float(clon)) ** 2) ** 0.5
        extra += max(0, 5 - int(dist * 80))
    return extra


def score_hosp(_row: dict[str, Any], tags: dict[str, Any]) -> int:
    extra = 0
    if _yes(tags, "emergency") or str(tags.get("emergency") or "").lower() == "yes":
        extra += 4
    if _tag(tags, "beds"):
        extra += 3
    if _tag(tags, "wikidata"):
        extra += 2
    return extra


def score_port(_row: dict[str, Any], tags: dict[str, Any]) -> int:
    extra = 0
    if tags.get("industrial") == "port":
        extra += 4
    if tags.get("landuse") in {"port", "harbour"}:
        extra += 3
    if _yes(tags, "harbour") or tags.get("harbour") == "yes":
        extra += 2
    if _tag(tags, "wikidata"):
        extra += 2
    return extra


def score_stad(_row: dict[str, Any], tags: dict[str, Any]) -> int:
    extra = 0
    if _tag(tags, "capacity"):
        extra += 3
    if _tag(tags, "wikidata"):
        extra += 3
    return extra


def score_mall(row: dict[str, Any], tags: dict[str, Any]) -> int:
    """I centri veri sopra Conad, Muji e i negozi singoli taggati male."""
    extra = 0
    name = _blob(row.get("name"), _tag(tags, "name", "brand"))
    if tags.get("shop") == "mall":
        extra += 8
    elif tags.get("shop") == "department_store":
        extra += 2
        if "rinascente" in name:
            extra += 6
    for token, pts in (
        ("shopville", 7),
        ("centro commerciale", 6),
        ("outlet", 6),
        ("gallerie", 5),
        ("gallery", 5),
        ("retail park", 5),
        ("megashopping", 4),
        ("le gru", 6),
        ("8 gallery", 6),
        ("lingotto", 4),
    ):
        if token in name:
            extra += pts
            break
    if row.get("wikidata") or _tag(tags, "wikidata"):
        extra += 4
    if row.get("wikipedia") or _tag(tags, "wikipedia"):
        extra += 5
    if tags.get("building") in {"retail", "commercial", "mall"}:
        extra += 2
    return extra


def score_land(_row: dict[str, Any], tags: dict[str, Any]) -> int:
    extra = 0
    if _tag(tags, "wikidata"):
        extra += 4
    if tags.get("historic") in {"castle", "palace"}:
        extra += 3
    if tags.get("building") == "cathedral":
        extra += 3
    if tags.get("amenity") == "townhall":
        extra += 2
    return extra


def importance_score(row: dict[str, Any]) -> int:
    """Punteggio di importanza. Non è un dump: sceglie i 15–20 oggetti più parlanti."""
    tags = row.get("tags") or {}
    cat = row.get("category") or ""
    extra: ScoreFn | None = (CATEGORIES.get(cat) or {}).get("score")
    if cat == "mall":
        return extra(row, tags) if extra else 0
    score = 0
    if row.get("iata") or _tag(tags, "iata"):
        score += 5
    if row.get("icao") or _tag(tags, "icao"):
        score += 5
    if row.get("uic") or _tag(tags, "uic_ref"):
        score += 4
    if _yes(tags, "train") or str(row.get("train") or "").lower() in {"yes", "1", "true"}:
        score += 3
    if tags.get("building") == "train_station" or row.get("building") == "train_station":
        score += 3
    if row.get("operator") or _tag(tags, "operator"):
        score += 2
    if row.get("website") or _tag(tags, "website", "contact:website"):
        score += 2
    if row.get("wikipedia") or _tag(tags, "wikipedia"):
        score += 1
    if extra:
        score += extra(row, tags)
    return score


# Clausole Overpass in stile Wizard: unione di AND, NOT come tag sulla stessa query.
# primary = selettiva; fallback = un po' più larga, solo se i candidati sono pochi.
CATEGORIES: dict[str, dict[str, Any]] = {
    "aero": {
        "id": "aero",
        "emoji": "✈️",
        "title": "Aeroporti",
        "primary": (
            'nw["aeroway"="aerodrome"]["iata"]',
            'nw["aeroway"="aerodrome"]["icao"]',
        ),
        "fallback": ('nw["aeroway"="aerodrome"]["name"]',),
        "accept": accept_aerodrome,
        "score": score_aero,
        "out_limit": 40,
        "fallback_min": 3,
    },
    "rail": {
        "id": "rail",
        "emoji": "🚆",
        "title": "Stazioni principali",
        "primary": (
            'nw["railway"="station"]["train"="yes"]["station"!="subway"]["station"!="light_rail"]["station"!="tram"]["station"!="monorail"]',
            'nw["railway"="station"]["uic_ref"]["station"!="subway"]["station"!="light_rail"]',
            'nw["building"="train_station"]["name"]',
        ),
        "fallback": (
            'nw["railway"="station"]["name"]["station"!="subway"]["station"!="light_rail"]["station"!="tram"]',
        ),
        "accept": accept_rail,
        "score": score_rail,
        "out_limit": 80,
        "fallback_min": 5,
    },
    "hosp": {
        "id": "hosp",
        "emoji": "🏥",
        "title": "Ospedali",
        "primary": (
            'nw["amenity"="hospital"]["emergency"="yes"]["name"]',
            'nw["amenity"="hospital"]["beds"]["name"]',
        ),
        "fallback": ('nw["amenity"="hospital"]["name"]',),
        "accept": accept_named,
        "score": score_hosp,
        "out_limit": 50,
        "fallback_min": 5,
    },
    "port": {
        "id": "port",
        "emoji": "⚓",
        "title": "Porti",
        "primary": (
            'nw["industrial"="port"]["name"]',
            'nw["landuse"="harbour"]["name"]',
        ),
        "fallback": ('nw["harbour"="yes"]["name"]',),
        "accept": accept_port,
        "score": score_port,
        "out_limit": 40,
        "fallback_min": 2,
    },
    "stad": {
        "id": "stad",
        "emoji": "🏟️",
        "title": "Stadi",
        "primary": ('nw["leisure"="stadium"]["name"]',),
        "fallback": ('nw["leisure"="stadium"]["name"]',),
        "accept": accept_stadium,
        "score": score_stad,
        "out_limit": 40,
        "fallback_min": 3,
    },
    "mall": {
        "id": "mall",
        "emoji": "🏬",
        "title": "Centri commerciali",
        "primary": ('nw["shop"="mall"]["name"]',),
        "fallback": ('nw["shop"="mall"]["name"]',),
        "accept": accept_mall,
        "score": score_mall,
        "out_limit": 40,
        "fallback_min": 3,
    },
    "land": {
        "id": "land",
        "emoji": "🏛️",
        "title": "Luoghi principali",
        "primary": (
            'nw["tourism"="attraction"]["wikidata"]["name"]',
            'nw["historic"="castle"]["name"]',
            'nw["historic"="palace"]["name"]',
            'nw["amenity"="townhall"]["name"]',
            'nw["building"="cathedral"]["name"]',
        ),
        "fallback": (
            'nw["historic"="monument"]["wikidata"]',
            'nw["tourism"="museum"]["wikidata"]["name"]',
        ),
        "accept": accept_named,
        "score": score_land,
        "out_limit": 50,
        "fallback_min": 5,
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
        "wheelchair": _tag(tags, "wheelchair"),
        "railway": _tag(tags, "railway"),
        "emergency": _tag(tags, "emergency"),
        "beds": _tag(tags, "beds"),
        "map": osm_url(lat, lon, 15),
        "tags": tags,
    }


def build_query(bbox: BBox | str, category: str, *, fallback: bool = False, timeout: int | None = None, limit: int | None = None) -> str:
    """Query Overpass QL per una categoria (primary o fallback). Non chiama la rete."""
    cat = resolve_category(category)
    if not cat:
        raise ValueError(f"categoria sconosciuta: {category}")
    box = parse_bbox(bbox)
    meta = CATEGORIES[cat]
    clauses = tuple(meta["fallback"] if fallback else meta.get("primary") or meta.get("filters") or ())
    if not clauses:
        raise ValueError(f"nessuna clausola Overpass per {cat}")
    return compile_query(
        box,
        clauses,
        timeout=timeout if timeout is not None else QUERY_TIMEOUT,
        limit=limit if limit is not None else int(meta.get("out_limit") or OUT_LIMIT),
    )


def _ingest(payload: dict[str, Any], *, category: str, box: BBox) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    clat, clon = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    for el in payload.get("elements") or []:
        if not isinstance(el, dict):
            continue
        item = normalize_element(el, category=category)
        if not item or item["id"] in seen:
            continue
        seen.add(item["id"])
        item["_clat"] = clat
        item["_clon"] = clon
        item["score"] = importance_score(item)
        rows.append(item)
    merged: dict[tuple, dict[str, Any]] = {}
    for item in rows:
        key = _cluster_key(item)
        prev = merged.get(key)
        merged[key] = item if prev is None else _merge_items(prev, item)
    ranked = list(merged.values())
    ranked.sort(key=lambda r: (-int(r.get("score") or 0), r["name"].lower()))
    return ranked


def search(bbox: BBox | str, category: str, *, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """Una categoria: query Wizard-style, fallback solo se i candidati sono pochi."""
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
    pool_limit = int(meta.get("out_limit") or OUT_LIMIT)
    min_ok = int(meta.get("fallback_min") or FALLBACK_MIN)
    query = build_query(box, cat, fallback=False, timeout=QUERY_TIMEOUT, limit=pool_limit)
    used_fallback = False
    t0 = time.time()
    payload = overpass(query, timeout=timeout)
    timed("overpass", t0, cat=cat, fallback=0, ok=int(bool(payload.get("ok"))))
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
            "retry": True,
        }
    t1 = time.time()
    rows = _ingest(payload, category=cat, box=box)
    timed("parse_rank", t1, cat=cat, n=len(rows))
    fallback_clauses = tuple(meta.get("fallback") or ())
    if len(rows) < min_ok and fallback_clauses and fallback_clauses != tuple(meta.get("primary") or ()):
        q2 = build_query(box, cat, fallback=True, timeout=QUERY_TIMEOUT, limit=pool_limit)
        t2 = time.time()
        p2 = overpass(q2, timeout=timeout)
        timed("overpass", t2, cat=cat, fallback=1, ok=int(bool(p2.get("ok"))))
        if p2.get("ok"):
            extra = _ingest(p2, category=cat, box=box)
            by_id = {r["id"]: r for r in rows}
            for item in extra:
                by_id.setdefault(item["id"], item)
            rows = list(by_id.values())
            rows.sort(key=lambda r: (-int(r.get("score") or 0), r["name"].lower()))
            query = q2
            used_fallback = True
    pool = len(rows)
    rows = rows[:PAGE_CAP]
    for item in rows:
        item.pop("tags", None)
        item.pop("_clat", None)
        item.pop("_clon", None)
    bundle = {
        "ok": True,
        "category": cat,
        "title": meta["title"],
        "emoji": meta["emoji"],
        "bbox": box,
        "rows": rows,
        "total": len(rows),
        "pool": pool,
        "fallback": used_fallback,
        "source": "OpenStreetMap / Overpass",
        "ts": time.time(),
        "query": query,
        "cached": False,
    }
    osm_cache.put(_cache_key(box, cat), {k: v for k, v in bundle.items() if k != "cached"}, osm_cache.OVERPASS_TTL)
    log.debug("osm search cat=%s n=%d fallback=%s", cat, len(rows), used_fallback)
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


def format_osm_category(bundle: dict[str, Any], place: dict[str, Any] | None = None, *, limit: int = LIST_LIMIT, offset: int = 0) -> str:
    if not bundle.get("ok"):
        return (
            "🌍 <b>OSM WORLD</b>\n\n"
            "Overpass non ha risposto. Riprova tra un attimo.\n"
            f"<i>{e(bundle.get('error') or 'timeout')}</i>"
        )
    where = ""
    if place:
        where = f" · {e(place.get('display') or place.get('name'))}"
    cached = " · cache" if bundle.get("cached") else ""
    fb = " · fallback" if bundle.get("fallback") else ""
    rows = bundle.get("rows") or []
    start = max(0, offset)
    chunk = rows[start : start + limit]
    pool = int(bundle.get("pool") or len(rows) or 0)
    tally = f"{len(chunk)} di {len(rows)} principali{cached}{fb}"
    if pool > len(rows):
        tally += f" · pool {pool}"
    lines = [
        f"{bundle.get('emoji', '🗺️')} <b>{e(bundle.get('title'))}</b>{where}",
        f"{tally} · tocca una scheda",
        "",
    ]
    if not chunk:
        lines.append("Niente in questa categoria nel riquadro.")
    for row in chunk:
        lines.append(_row_line(row))
    if start + limit < len(rows):
        lines.append(f"… altri {len(rows) - start - limit}")
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
    if row.get("train") == "yes" or row.get("railway") == "station":
        bits.append("🚄 ferroviaria")
    if row.get("wheelchair"):
        bits.append(f"♿ {e(row['wheelchair'])}")
    if row.get("emergency") == "yes":
        bits.append("emergency")
    if row.get("beds"):
        bits.append(f"posti {e(row['beds'])}")
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
