"""OSM WORLD: Overpass per categoria, dopo il geocoder. Nessuna query gigante sulla città."""

from __future__ import annotations

import html
import json
import logging
import math
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

from services.live import cache as osm_cache
from services.live.engine import (
    FALLBACK_MIN,
    PAGE_CAP,
    PAGE_SIZE,
    as_clauses,
    clause,
    compile_query,
    eq,
    exists,
    neq,
    regex,
    timed,
)

log = logging.getLogger("warbot.osm")

TELEGRAM_MAX_LEN = 3900

OVERPASS_URL = "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
OVERPASS_FALLBACK_URLS = (
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass-api.de/api/interpreter",
)
USER_AGENT = "WARBOT/1.0 (OSM WORLD; Overpass)"
DEFAULT_TIMEOUT = osm_cache.int_env("OSM_OVERPASS_TIMEOUT", 8, lo=5, hi=20)
QUERY_TIMEOUT = osm_cache.int_env("OSM_OVERPASS_QL_TIMEOUT", 10, lo=6, hi=25)
FIRST_HOST_TIMEOUT = osm_cache.int_env("OSM_OVERPASS_FIRST_TIMEOUT", 6, lo=4, hi=12)
OVERPASS_RETRIES = osm_cache.int_env("OSM_OVERPASS_RETRIES", 1, lo=1, hi=3)
OUT_LIMIT = osm_cache.int_env("OSM_OVERPASS_LIMIT", 40, lo=20, hi=120)
RESULT_LIMIT = PAGE_SIZE
LIST_LIMIT = PAGE_SIZE
QUERY_VER = "29"
DEDUP_METERS = 180
HOST_COOLDOWN = 180
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


_AERO_PARTS = {
    "runway",
    "taxiway",
    "terminal",
    "hangar",
    "gate",
    "helipad",
    "apron",
    "holding_position",
    "parking_position",
}


def accept_aerodrome(tags: dict[str, Any]) -> bool:
    aeroway = str(tags.get("aeroway") or "")
    if aeroway in _AERO_PARTS:
        return False
    if aeroway != "aerodrome":
        return False
    kind = str(tags.get("aerodrome") or tags.get("aerodrome:type") or "").lower()
    if kind in {"heliport", "airstrip", "helipad"}:
        return False
    return accept_named(tags)


def accept_rail(tags: dict[str, Any]) -> bool:
    """Solo hub: Wikipedia o nome noto o tante banchine. Wikidata da solo non basta."""
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
    if _yes(tags, "subway") and not (
        _yes(tags, "train") and (tags.get("building") == "train_station" or bool(_tag(tags, "uic_ref")))
    ):
        return False
    if _yes(tags, "tram", "light_rail") and not _yes(tags, "train"):
        return False
    if _yes(tags, "bus") and not _yes(tags, "train") and railway != "station":
        return False
    train_station = _yes(tags, "train") or tags.get("building") == "train_station" or bool(_tag(tags, "uic_ref"))
    if not train_station:
        return False
    name = _tag(tags, "name:it", "name", "official_name").lower()
    if any(
        bit in name
        for bit in (
            "bivio",
            "cabina",
            "deposito",
            "scalo merci",
            "terminali italia",
            "ex stazione",
            "fermata",
        )
    ):
        return False
    if str(tags.get("usage") or "").lower() in {"industrial", "military", "freight"}:
        return False
    return True


def accept_named(tags: dict[str, Any]) -> bool:
    return bool(_tag(tags, "name:it", "name", "official_name"))


def accept_hospital(tags: dict[str, Any]) -> bool:
    if tags.get("amenity") in {"clinic", "doctors", "pharmacy", "dentist"}:
        return False
    if tags.get("amenity") != "hospital":
        return False
    healthcare = str(tags.get("healthcare") or "").lower()
    if healthcare in {"clinic", "doctor", "pharmacy", "centre", "center"}:
        return False
    name = _blob(_tag(tags, "name:it", "name", "official_name"))
    if any(
        bit in name
        for bit in (
            "pronto soccorso",
            "emergency department",
            "first aid",
            "casa di comunità",
            "casa della comunità",
            "ex ospedale",
            "chiuso",
            "clinic",
            "clinica",
            "klinik",
            "クリニック",
        )
    ):
        return False
    return accept_named(tags)


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
    if tags.get("leisure") != "stadium":
        return False
    name = _blob(_tag(tags, "name:it", "name", "alt_name", "old_name"))
    if any(
        bit in name
        for bit in (
            "palaghiaccio",
            "palazzetto",
            "palasport",
            "pala ruffini",
            "pala ",
            "campo sportivo",
            "ice",
            "tennis",
        )
    ):
        return False
    sport = str(tags.get("sport") or "").lower()
    if any(bit in sport for bit in ("ice_hockey", "curling", "tennis", "ice_skating")):
        return False
    if not accept_named(tags):
        return False
    if _tag(tags, "wikidata", "wikipedia", "capacity"):
        return True
    return "soccer" in sport or "football" in sport


_GROCERY_MARKERS = (
    "conad",
    "lidl",
    "eurospin",
    "esselunga",
    "penny",
    "aldi",
    "despar",
    "iperal",
    "ipercoop",
    "iper coop",
    "ipermercato",
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
    ("centrale", 10),
    ("hauptbahnhof", 10),
    ("termini", 10),
    ("union station", 10),
    ("grand central", 10),
    ("penn station", 10),
    ("gare du nord", 10),
    ("gare de lyon", 9),
    ("saint-lazare", 8),
    ("montparnasse", 8),
    ("king's cross", 10),
    ("st pancras", 10),
    ("paddington", 9),
    ("waterloo", 8),
    ("liverpool street", 8),
    ("shinjuku", 10),
    ("tokyo station", 10),
    ("porta nuova", 9),
    ("porta susa", 8),
    ("porta garibaldi", 8),
    ("lingotto", 8),
    ("shibuya", 8),
    ("ikebukuro", 7),
    ("shinagawa", 7),
    ("rogoredo", 6),
    ("lambrate", 6),
    ("cadorna", 6),
    ("tiburtina", 6),
    ("ostiense", 5),
)


def _blob(*parts: Any) -> str:
    return " ".join(str(p or "") for p in parts).lower()


def _norm_place_name(name: str) -> str:
    n = " ".join(str(name or "").lower().split())
    n = n.split(" · ")[0].strip()
    n = re.sub(
        r"\s*\([^)]*(superficie|passante|sotterranea|underground|linea)[^)]*\)",
        "",
        n,
        flags=re.I,
    ).strip()
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


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2.0) ** 2
    return 2.0 * radius * math.asin(min(1.0, math.sqrt(a)))


def _strong_key(item: dict[str, Any]) -> tuple | None:
    """Identificatori OSM univoci: non unire strutture diverse solo per il nome."""
    iata = str(item.get("iata") or "").strip().upper()
    if len(iata) == 3 and iata.isalpha():
        return ("iata", iata)
    icao = str(item.get("icao") or "").strip().upper()
    if len(icao) == 4 and icao.isalnum():
        return ("icao", icao)
    uic = str(item.get("uic") or "").strip()
    if uic:
        return ("uic", uic)
    qid = str(item.get("wikidata") or "").strip()
    if qid.startswith("Q") and qid[1:].isdigit():
        return ("q", qid)
    return None


def _cluster_key(item: dict[str, Any]) -> tuple:
    strong = _strong_key(item)
    if strong:
        return strong
    return ("id", str(item.get("id") or ""))


def _should_merge(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if left.get("category") != right.get("category"):
        return False
    sk_l, sk_r = _strong_key(left), _strong_key(right)
    if sk_l and sk_r and sk_l != sk_r:
        return False
    na = _norm_place_name(left.get("name") or "")
    nb = _norm_place_name(right.get("name") or "")
    if not na or not nb:
        return False
    dist = _haversine_m(float(left["lat"]), float(left["lon"]), float(right["lat"]), float(right["lon"]))
    if na == nb and dist <= DEDUP_METERS:
        return True
    shorter, longer = (na, nb) if len(na) <= len(nb) else (nb, na)
    if dist <= 80 and len(shorter) >= 8 and shorter in longer:
        return True
    return False


def _dedup_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple, dict[str, Any]] = {}
    leftovers: list[dict[str, Any]] = []
    for item in rows:
        key = _strong_key(item)
        if key:
            prev = buckets.get(key)
            buckets[key] = item if prev is None else _merge_items(prev, item)
        else:
            leftovers.append(item)
    merged = list(buckets.values()) + leftovers
    merged.sort(key=lambda r: (-int(r.get("score") or 0), str(r.get("name") or "").lower()))
    kept: list[dict[str, Any]] = []
    for item in merged:
        found = False
        for idx, prev in enumerate(kept):
            if _should_merge(prev, item):
                kept[idx] = _merge_items(prev, item)
                found = True
                break
        if not found:
            kept.append(item)
    return kept


def _merge_items(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    tags = {**(left.get("tags") or {}), **(right.get("tags") or {})}
    type_rank = {"relation": 0, "way": 1, "node": 2}
    prefer_right = type_rank.get(str(right.get("osm_type") or ""), 9) < type_rank.get(str(left.get("osm_type") or ""), 9)
    out = dict(right if prefer_right else left)
    out["tags"] = tags
    out["name"] = _prefer_name(str(left.get("name") or ""), str(right.get("name") or ""))
    if prefer_right:
        for geo in ("id", "osm_type", "osm_id", "lat", "lon", "map"):
            if right.get(geo) is not None:
                out[geo] = right[geo]
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
        "kind",
        "tier",
    ):
        if not out.get(key):
            out[key] = left.get(key) or right.get(key)
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
        notable = bool(_tag(tags, "wikidata", "wikipedia"))
        if any(
            token in blob
            for token in (
                "centro commerciale",
                "shopville",
                "outlet",
                "gallerie",
                "gallery",
                "retail park",
                "megashopping",
                "le gru",
            )
        ):
            notable = True
        return notable and accept_named(tags)
    if shop == "department_store":
        if _tag(tags, "wikipedia", "wikidata"):
            return accept_named(tags)
        brand = _blob(_tag(tags, "brand", "name"))
        return "rinascente" in brand or brand.strip() == "coin"
    return False


def _named_bonus(row: dict[str, Any], tags: dict[str, Any]) -> int:
    return 2 if _tag(tags, "name:it", "name", "official_name") or row.get("name") else 0


def _wiki_bonus(row: dict[str, Any], tags: dict[str, Any]) -> int:
    score = 0
    if row.get("wikipedia") or _tag(tags, "wikipedia"):
        score += 4
    if row.get("wikidata") or _tag(tags, "wikidata"):
        score += 3
    if row.get("website") or _tag(tags, "website", "contact:website"):
        score += 3
    if row.get("operator") or _tag(tags, "operator"):
        score += 3
    return score


def score_aero(row: dict[str, Any], tags: dict[str, Any]) -> int:
    """IATA/ICAO/operator/sito/wiki prima; internazionali sopra i campi locali."""
    score = _named_bonus(row, tags)
    if row.get("iata") or _tag(tags, "iata"):
        score += 8
    if row.get("icao") or _tag(tags, "icao"):
        score += 6
    score += _wiki_bonus(row, tags)
    kind = str(tags.get("aerodrome") or tags.get("aerodrome:type") or "").lower()
    if "international" in kind:
        score += 8
        row["tier"] = "principale"
    elif row.get("iata") or _tag(tags, "iata"):
        row["tier"] = row.get("tier") or "secondario"
    else:
        row["tier"] = "locale"
        score -= 4
    clat, clon = row.get("_clat"), row.get("_clon")
    if isinstance(clat, (int, float)) and isinstance(clon, (int, float)):
        dist = ((float(row["lat"]) - float(clat)) ** 2 + (float(row["lon"]) - float(clon)) ** 2) ** 0.5
        score += max(0, 8 - int(dist * 30))
        if dist > 0.28 and "international" not in kind:
            score -= 24
    return score


def score_rail(row: dict[str, Any], tags: dict[str, Any]) -> int:
    """Hub passeggeri: train, UIC, building, piattaforme, operator, wiki."""
    score = _named_bonus(row, tags)
    if _yes(tags, "train") or str(row.get("train") or "").lower() in {"yes", "1", "true"}:
        score += 6
    if row.get("uic") or _tag(tags, "uic_ref"):
        score += 6
    if tags.get("building") == "train_station" or row.get("building") == "train_station":
        score += 5
    platforms = _tag(tags, "platforms")
    if platforms:
        score += 2
        try:
            if int(str(platforms).split(";")[0]) >= 5:
                score += 3
        except ValueError:
            pass
    if tags.get("public_transport") == "station":
        score += 2
    score += _wiki_bonus(row, tags)
    name = _blob(row.get("name"), _tag(tags, "name:it", "name"))
    if name.startswith("ex ") or "ex stazione" in name:
        score -= 12
    major = False
    for hub, pts in _MAJOR_RAIL:
        if hub in name:
            score += pts
            major = True
            break
    city = _norm_place_name(str(row.get("_hint") or "")).split(",")[0].strip()
    station = _norm_place_name(row.get("name") or "")
    city_named = bool(city) and len(city) >= 3 and station == city
    if city_named:
        score += 12
    notable = major or city_named or bool(row.get("uic") or _tag(tags, "uic_ref") or tags.get("building") == "train_station")
    if not notable:
        score -= 18
    clat, clon = row.get("_clat"), row.get("_clon")
    if isinstance(clat, (int, float)) and isinstance(clon, (int, float)):
        dist = ((float(row["lat"]) - float(clat)) ** 2 + (float(row["lon"]) - float(clon)) ** 2) ** 0.5
        score += max(0, 6 - int(dist * 90))
        if not major and not city_named:
            score -= int(dist * 80)
            if dist > 0.05:
                score -= 25
    return score


def score_hosp(row: dict[str, Any], tags: dict[str, Any]) -> int:
    score = _named_bonus(row, tags)
    if _yes(tags, "emergency") or str(tags.get("emergency") or "").lower() == "yes":
        score += 6
    if _tag(tags, "beds") or row.get("beds"):
        score += 4
    score += _wiki_bonus(row, tags)
    return score


def score_port(row: dict[str, Any], tags: dict[str, Any]) -> int:
    score = _named_bonus(row, tags)
    if tags.get("industrial") == "port":
        score += 6
    if tags.get("landuse") in {"port", "harbour"}:
        score += 5
    if _yes(tags, "harbour") or tags.get("harbour") == "yes":
        score += 4
    score += _wiki_bonus(row, tags)
    return score


def score_stad(row: dict[str, Any], tags: dict[str, Any]) -> int:
    score = _named_bonus(row, tags)
    sport = str(tags.get("sport") or "").lower()
    name = _blob(row.get("name"), _tag(tags, "name", "alt_name", "old_name"))
    if "soccer" in sport or "football" in sport:
        score += 6
    if _tag(tags, "capacity"):
        score += 5
    score += _wiki_bonus(row, tags)
    if any(bit in sport for bit in ("ice_hockey", "curling", "tennis", "ice_skating")):
        score -= 8
    if any(bit in name for bit in ("palaghiaccio", "palazzetto", "palasport", "pala ")):
        score -= 10
    if any(bit in name for bit in ("juventus", "allianz", "olimpico")):
        score += 6
    return score


def score_mall(row: dict[str, Any], tags: dict[str, Any]) -> int:
    """Centri commerciali veri, non supermercati o negozi singoli."""
    score = _named_bonus(row, tags)
    name = _blob(row.get("name"), _tag(tags, "name", "brand"))
    if tags.get("shop") == "mall":
        score += 8
    elif tags.get("shop") == "department_store":
        score += 2
        if "rinascente" in name:
            score += 6
    for token, pts in (
        ("shopville", 8),
        ("le gru", 8),
        ("8 gallery", 7),
        ("outlet", 6),
        ("gallerie", 5),
        ("gallery", 5),
        ("retail park", 5),
        ("megashopping", 4),
        ("lingotto", 4),
        ("centro commerciale", 3),
    ):
        if token in name:
            score += pts
            break
    score += _wiki_bonus(row, tags)
    if tags.get("building") in {"retail", "commercial", "mall"}:
        score += 2
    return score


def score_land(row: dict[str, Any], tags: dict[str, Any]) -> int:
    score = _named_bonus(row, tags)
    score += _wiki_bonus(row, tags)
    if tags.get("tourism"):
        score += 3
    if tags.get("historic") in {"castle", "palace", "monument", "memorial"}:
        score += 4
    if _tag(tags, "heritage"):
        score += 4
    if tags.get("building") in {"cathedral", "church", "palace"}:
        score += 3
    if tags.get("amenity") == "townhall":
        score += 2
    return score


def importance_score(row: dict[str, Any]) -> int:
    """Punteggio di categoria, deterministico. Nessun punteggio unico per tutto."""
    tags = row.get("tags") or {}
    cat = row.get("category") or ""
    fn: ScoreFn | None = (CATEGORIES.get(cat) or {}).get("score")
    return int(fn(row, tags)) if fn else 0


# Query per categoria: AND = filtri concatenati; OR = union di Clause; NOT = != / regex.
# radius_m → bbox sul punto geocodificato (indice spaziale, più veloce di around).
CATEGORIES: dict[str, dict[str, Any]] = {
    "aero": {
        "id": "aero",
        "emoji": "✈️",
        "title": "Aeroporti",
        "kind": "Aeroporto",
        "primary": (
            clause("way", eq("aeroway", "aerodrome"), exists("name"), exists("iata")),
            clause("rel", eq("aeroway", "aerodrome"), exists("name"), exists("iata")),
        ),
        "fallback": (
            clause("node", eq("aeroway", "aerodrome"), exists("name"), exists("iata")),
        ),
        "accept": accept_aerodrome,
        "score": score_aero,
        "out_limit": 12,
        "fallback_min": 1,
        "min_score": 4,
        "radius_m": 45000,
    },
    "rail": {
        "id": "rail",
        "emoji": "🚆",
        "title": "Stazioni ferroviarie",
        "kind": "Stazione ferroviaria",
        "primary": (
            clause(
                "node",
                eq("railway", "station"),
                eq("train", "yes"),
                exists("name"),
                neq("station", "subway"),
                neq("station", "tram"),
                neq("station", "light_rail"),
            ),
        ),
        "fallback": (
            clause(
                "nw",
                eq("railway", "station"),
                eq("train", "yes"),
                exists("name"),
                neq("station", "subway"),
                neq("station", "tram"),
                neq("station", "light_rail"),
            ),
        ),
        "accept": accept_rail,
        "score": score_rail,
        "out_limit": 40,
        "fallback_min": 2,
        "min_score": 6,
        "radius_m": 12000,
    },
    "hosp": {
        "id": "hosp",
        "emoji": "🏥",
        "title": "Ospedali",
        "kind": "Ospedale",
        "primary": (
            clause("way", eq("amenity", "hospital"), exists("name")),
            clause("rel", eq("amenity", "hospital"), exists("name")),
        ),
        "fallback": (clause("way", eq("amenity", "hospital"), eq("emergency", "yes"), exists("name")),),
        "accept": accept_hospital,
        "score": score_hosp,
        "out_limit": 24,
        "fallback_min": 2,
        "min_score": 4,
        "radius_m": 13000,
    },
    "port": {
        "id": "port",
        "emoji": "⚓",
        "title": "Porti",
        "kind": "Porto",
        "primary": (clause("nw", eq("industrial", "port"), exists("name")),),
        "fallback": (clause("nw", eq("harbour", "yes"), exists("name")),),
        "accept": accept_port,
        "score": score_port,
        "out_limit": 12,
        "fallback_min": 1,
        "min_score": 5,
        "radius_m": 40000,
    },
    "stad": {
        "id": "stad",
        "emoji": "🏟️",
        "title": "Stadi",
        "kind": "Stadio",
        "primary": (
            clause("rel", eq("leisure", "stadium"), exists("name")),
            clause("way", eq("leisure", "stadium"), exists("name"), exists("wikidata")),
        ),
        "fallback": (clause("way", eq("leisure", "stadium"), exists("wikidata"), eq("sport", "soccer")),),
        "accept": accept_stadium,
        "score": score_stad,
        "out_limit": 24,
        "fallback_min": 2,
        "min_score": 8,
        "radius_m": 18000,
    },
    "mall": {
        "id": "mall",
        "emoji": "🏬",
        "title": "Shopping",
        "kind": "Centro commerciale",
        "primary": (clause("way", eq("shop", "mall"), exists("name")),),
        "fallback": (
            clause(
                "way",
                eq("shop", "mall"),
                regex("name", "Shopville|Centro Commerciale|Outlet|Gallerie|Gallery|Le Gru|Shopping", ignore_case=True),
            ),
        ),
        "accept": accept_mall,
        "score": score_mall,
        "out_limit": 16,
        "fallback_min": 2,
        "min_score": 8,
        "radius_m": 18000,
        "near_m": 900,
    },
    "land": {
        "id": "land",
        "emoji": "🏛️",
        "title": "Luoghi importanti",
        "kind": "Luogo importante",
        "primary": (clause("nw", eq("tourism", "attraction"), exists("wikipedia"), exists("name")),),
        "fallback": (
            clause("nw", eq("historic", "castle"), exists("wikipedia"), exists("name")),
            clause("nw", eq("building", "cathedral"), exists("wikipedia"), exists("name")),
            clause("nw", eq("amenity", "townhall"), exists("wikipedia"), exists("name")),
        ),
        "accept": accept_named,
        "score": score_land,
        "out_limit": 20,
        "fallback_min": 2,
        "min_score": 6,
        "radius_m": 13000,
        "near_m": 800,
    },
    "food": {
        "id": "food",
        "emoji": "🍴",
        "title": "Ristoranti",
        "kind": "Ristorante",
        "primary": (clause("node", eq("amenity", "restaurant"), exists("name")),),
        "fallback": (clause("node", eq("amenity", "cafe"), exists("name"), exists("wikidata")),),
        "accept": accept_named,
        "score": score_land,
        "out_limit": 16,
        "fallback_min": 2,
        "min_score": 2,
        "radius_m": 400,
        "near_m": 400,
    },
    "stay": {
        "id": "stay",
        "emoji": "🏨",
        "title": "Hotel",
        "kind": "Hotel",
        "primary": (clause("node", eq("tourism", "hotel"), exists("name")),),
        "fallback": (clause("way", eq("tourism", "hotel"), exists("name")),),
        "accept": accept_named,
        "score": score_land,
        "out_limit": 16,
        "fallback_min": 2,
        "min_score": 2,
        "radius_m": 700,
        "near_m": 700,
    },
    "move": {
        "id": "move",
        "emoji": "🚇",
        "title": "Trasporti",
        "kind": "Fermata / stazione",
        "primary": (
            clause(
                "node",
                eq("railway", "station"),
                eq("train", "yes"),
                exists("name"),
                neq("station", "subway"),
            ),
        ),
        "fallback": (clause("node", eq("public_transport", "station"), exists("name"), exists("wikidata")),),
        "accept": accept_named,
        "score": score_rail,
        "out_limit": 12,
        "fallback_min": 1,
        "min_score": 2,
        "radius_m": 900,
        "near_m": 900,
    },
}

WORLD_CATEGORIES = ("aero", "rail", "hosp", "port", "stad", "mall", "land")
NEAR_CATEGORIES = ("food", "stay", "mall", "move", "land")

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
    "food": "food",
    "ristoranti": "food",
    "ristorante": "food",
    "restaurant": "food",
    "stay": "stay",
    "hotel": "stay",
    "hotels": "stay",
    "albergo": "stay",
    "alberghi": "stay",
    "move": "move",
    "trasporti": "move",
    "transport": "move",
}


def resolve_category(raw: str | None) -> str | None:
    key = (raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    return _ALIASES.get(key) if key in _ALIASES else (key if key in CATEGORIES else None)


_INTENT_CATS: tuple[tuple[str, str], ...] = (
    ("aeroporti", "aero"),
    ("aeroporto", "aero"),
    ("airports", "aero"),
    ("airport", "aero"),
    ("stazioni ferroviarie", "rail"),
    ("stazioni", "rail"),
    ("stazione", "rail"),
    ("stations", "rail"),
    ("ospedali", "hosp"),
    ("ospedale", "hosp"),
    ("hospitals", "hosp"),
    ("porti", "port"),
    ("porto", "port"),
    ("stadi", "stad"),
    ("stadio", "stad"),
    ("centri commerciali", "mall"),
    ("shopping", "mall"),
    ("ristoranti", "food"),
    ("hotel", "stay"),
    ("luoghi importanti", "land"),
)


def parse_osm_intent(text: str) -> dict[str, Any]:
    """Capisce 'stazioni vicino al Duomo' / 'aeroporti Milano' senza LLM."""
    raw = " ".join((text or "").split())
    q = raw
    cat = None
    low = q.lower()
    for phrase, key in _INTENT_CATS:
        if low.startswith(phrase + " ") or low == phrase:
            cat = key
            q = q[len(phrase) :].strip()
            low = q.lower()
            break
        if f" {phrase} " in f" {low} ":
            cat = key
            q = re.sub(re.escape(phrase), " ", q, count=1, flags=re.I).strip()
            low = q.lower()
            break
    near = False
    m = re.search(
        r"\b(?:vicino(?:\s+all['aeo]|\s+agli|\s+ai|\s+al|\s+a)?|near|around)\s+(.+)$",
        q,
        flags=re.I,
    )
    if m:
        near = True
        q = m.group(1).strip()
    q = re.sub(r"^(?:di|del|della|dello|dei|degli|delle|the|of)\s+", "", q, flags=re.I).strip(" ,.-")
    return {"query": q or raw, "category": cat, "near": near, "raw": raw}


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


def _meters_box(lat: float, lon: float, meters: int) -> BBox:
    dlat = meters / 111320.0
    coslat = max(0.2, math.cos(math.radians(lat)))
    dlon = meters / (111320.0 * coslat)
    return (lat - dlat, lon - dlon, lat + dlat, lon + dlon)


def _scope_bbox(
    box: BBox,
    cat: str,
    center: tuple[float, float] | None = None,
    radius_m: int | None = None,
) -> BBox:
    """Riquadro equivalente al raggio around, per cache e ranking."""
    if center is not None:
        clat, clon = float(center[0]), float(center[1])
    else:
        south, west, north, east = box
        clat = (south + north) / 2.0
        clon = (west + east) / 2.0
    meta = CATEGORIES.get(cat) or {}
    meters = int(radius_m if radius_m is not None else (meta.get("radius_m") or 0))
    if meters > 0:
        return _meters_box(clat, clon, meters)
    span = float(meta.get("span") or 0.14)
    return (clat - span, clon - span, clat + span, clon + span)


def _as_center(center: tuple[float, float] | list[float] | None) -> tuple[float, float] | None:
    if center is None or len(center) < 2:
        return None
    return (float(center[0]), float(center[1]))


def _bbox_ql(bbox: BBox) -> str:
    south, west, north, east = bbox
    return f"({south},{west},{north},{east})"


def _cache_key(bbox: BBox, cat: str, extra: str = "") -> str:
    south, west, north, east = bbox
    tail = f":{extra}" if extra else ""
    return f"osm:{QUERY_VER}:{south:.4f},{west:.4f},{north:.4f},{east:.4f}:{cat}{tail}"


def _copy_bundle(bundle: dict[str, Any], *, cached: bool) -> dict[str, Any]:
    rows = list(bundle.get("rows") or [])
    out = dict(bundle)
    out["rows"] = rows
    out["cached"] = cached
    return out


def peek(
    bbox: BBox | str,
    category: str,
    *,
    center: tuple[float, float] | list[float] | None = None,
    extra: str = "",
    radius_m: int | None = None,
) -> dict[str, Any] | None:
    """Risultato categoria in cache, senza Overpass. None se assente o scaduto."""
    cat = resolve_category(category)
    if not cat:
        return None
    try:
        box = _scope_bbox(parse_bbox(bbox), cat, _as_center(center), radius_m=radius_m)
    except (TypeError, ValueError):
        return None
    hit = osm_cache.get(_cache_key(box, cat, extra))
    if isinstance(hit, dict) and hit.get("ok"):
        return _copy_bundle(hit, cached=True)
    return None


_dead_until: dict[str, float] = {}


def _mark_host(host: str, *, ok: bool) -> None:
    if ok:
        _dead_until.pop(host, None)
        return
    _dead_until[host] = time.time() + HOST_COOLDOWN


def _overpass_urls() -> list[str]:
    custom = (os.getenv("OSM_OVERPASS_URL") or "").strip()
    urls: list[str] = []
    for url in (custom, *OVERPASS_FALLBACK_URLS):
        if url and url not in urls:
            urls.append(url)
    now = time.time()
    live = [u for u in urls if _dead_until.get(urllib.parse.urlparse(u).netloc or "", 0) < now]
    return live or urls or [OVERPASS_URL]


def overpass(query: str, *, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """POST application/x-www-form-urlencoded, parametro data=. Timeout: stop, Riprova manuale."""
    body = urllib.parse.urlencode({"data": query}).encode("utf-8")
    last_error = "Overpass non ha risposto"
    last_detail = ""
    urls = _overpass_urls()
    for index, url in enumerate(urls):
        host = urllib.parse.urlparse(url).netloc or "overpass"
        host_timeout = timeout if index == len(urls) - 1 else min(int(timeout), FIRST_HOST_TIMEOUT)
        for attempt in range(OVERPASS_RETRIES):
            req = urllib.request.Request(
                url,
                data=body,
                method="POST",
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=host_timeout) as resp:
                    raw = resp.read()
            except TimeoutError as exc:
                last_error = f"timeout Overpass ({host_timeout}s)"
                last_detail = str(exc)
                log.warning("overpass timeout host=%s", host)
                _mark_host(host, ok=False)
                break
            except urllib.error.HTTPError as exc:
                last_error = f"HTTP {exc.code}"
                last_detail = str(exc)
                log.warning("overpass http=%s host=%s", exc.code, host)
                if exc.code in {404, 429, 502, 503, 504}:
                    _mark_host(host, ok=False)
                if exc.code not in {429, 502, 503, 504, 404}:
                    break
            except urllib.error.URLError as exc:
                last_error = "Overpass non raggiungibile"
                last_detail = str(exc.reason or exc)
                log.warning("overpass unreachable host=%s", host)
            else:
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    log.warning("overpass json invalid host=%s", host)
                    return {"ok": False, "error": "JSON Overpass non valido", "detail": str(exc), "elements": []}
                if not isinstance(payload, dict):
                    return {"ok": False, "error": "payload Overpass inatteso", "elements": []}
                payload["ok"] = True
                payload.setdefault("elements", [])
                _mark_host(host, ok=True)
                return payload
            if attempt < OVERPASS_RETRIES - 1:
                time.sleep(0.4 * (attempt + 1))
    return {"ok": False, "error": last_error, "detail": last_detail, "elements": [], "retry": True}


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
    name = _tag(tags, "name:it", "name", "official_name") or "senza nome"
    name = re.sub(r"\s*\((superficie|passante|sotterranea|underground)\)", "", name, flags=re.I).strip()
    alt = _tag(tags, "alt_name", "old_name")
    if alt and alt.lower() not in name.lower() and ";" not in alt and len(alt) <= 48:
        name = f"{name} · {alt}"
    if category == "stad" and "allianz" in name.lower() and "juventus" not in name.lower():
        name = f"{name} · Juventus Stadium"
    wiki = _tag(tags, "wikipedia")
    qid = _tag(tags, "wikidata")
    site = _tag(tags, "website", "contact:website", "url")
    kind = str(meta.get("kind") or meta.get("title") or "punto")
    return {
        "id": f"{el.get('type')}/{el.get('id')}",
        "osm_type": str(el.get("type") or ""),
        "osm_id": el.get("id"),
        "name": name,
        "lat": lat,
        "lon": lon,
        "type": str(el.get("type") or category),
        "category": category,
        "kind": kind,
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
        "platforms": _tag(tags, "platforms"),
        "capacity": _tag(tags, "capacity"),
        "sport": _tag(tags, "sport"),
        "cuisine": _tag(tags, "cuisine"),
        "phone": _tag(tags, "phone", "contact:phone"),
        "addr": " ".join(p for p in (_tag(tags, "addr:street"), _tag(tags, "addr:housenumber"), _tag(tags, "addr:city")) if p),
        "map": osm_url(lat, lon, 15),
        "tags": tags,
    }


def build_query(
    bbox: BBox | str,
    category: str,
    *,
    fallback: bool = False,
    timeout: int | None = None,
    limit: int | None = None,
    center: tuple[float, float] | list[float] | None = None,
    around_m: int | None = None,
    radius_m: int | None = None,
) -> str:
    """Query Overpass QL per una categoria (primary o fallback). Non chiama la rete."""
    cat = resolve_category(category)
    if not cat:
        raise ValueError(f"categoria sconosciuta: {category}")
    here = _as_center(center)
    meta = CATEGORIES[cat]
    if radius_m:
        if here is None:
            south, west, north, east = parse_bbox(bbox)
            here = ((south + north) / 2.0, (west + east) / 2.0)
        box = _meters_box(here[0], here[1], int(radius_m))
    else:
        box = _scope_bbox(parse_bbox(bbox), cat, here)
    raw = meta["fallback"] if fallback else meta.get("primary") or meta.get("filters") or ()
    clauses = as_clauses(raw)
    if not clauses:
        raise ValueError(f"nessuna clausola Overpass per {cat}")
    around = None
    bbox_arg: BBox | None = box
    if around_m and here:
        around = (here[0], here[1], int(around_m))
        bbox_arg = None
    return compile_query(
        bbox_arg,
        clauses,
        timeout=timeout if timeout is not None else QUERY_TIMEOUT,
        limit=limit if limit is not None else int(meta.get("out_limit") or OUT_LIMIT),
        around=around,
        minus=as_clauses(meta.get("minus") or ()) if not fallback else (),
    )


def build_osm_query(
    category: str,
    bbox: BBox | str,
    limit: int | None = None,
    *,
    fallback: bool = False,
    timeout: int | None = None,
    center: tuple[float, float] | list[float] | None = None,
    around_m: int | None = None,
    radius_m: int | None = None,
) -> str:
    """API stabile: build_osm_query(category, area/bbox, limit)."""
    return build_query(
        bbox,
        category,
        fallback=fallback,
        timeout=timeout,
        limit=limit,
        center=center,
        around_m=around_m,
        radius_m=radius_m,
    )


def build_airport_query(bbox: BBox | str, **kwargs: Any) -> str:
    return build_query(bbox, "aero", **kwargs)


def build_station_query(bbox: BBox | str, **kwargs: Any) -> str:
    return build_query(bbox, "rail", **kwargs)


def build_hospital_query(bbox: BBox | str, **kwargs: Any) -> str:
    return build_query(bbox, "hosp", **kwargs)


def build_port_query(bbox: BBox | str, **kwargs: Any) -> str:
    return build_query(bbox, "port", **kwargs)


def build_stadium_query(bbox: BBox | str, **kwargs: Any) -> str:
    return build_query(bbox, "stad", **kwargs)


def build_mall_query(bbox: BBox | str, **kwargs: Any) -> str:
    return build_query(bbox, "mall", **kwargs)


def build_landmark_query(bbox: BBox | str, **kwargs: Any) -> str:
    return build_query(bbox, "land", **kwargs)


OSM_QUERIES: dict[str, Callable[..., str]] = {
    "aero": build_airport_query,
    "airports": build_airport_query,
    "rail": build_station_query,
    "stations": build_station_query,
    "hosp": build_hospital_query,
    "hospitals": build_hospital_query,
    "port": build_port_query,
    "ports": build_port_query,
    "stad": build_stadium_query,
    "stadiums": build_stadium_query,
    "mall": build_mall_query,
    "shopping": build_mall_query,
    "land": build_landmark_query,
    "landmarks": build_landmark_query,
}


def _ingest(payload: dict[str, Any], *, category: str, box: BBox, hint: str = "") -> list[dict[str, Any]]:
    t_parse = time.time()
    elements = [el for el in (payload.get("elements") or []) if isinstance(el, dict)]
    timed("parse", t_parse, n=len(elements), cat=category)

    t_norm = time.time()
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    clat, clon = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    for el in elements:
        item = normalize_element(el, category=category)
        if not item or item["id"] in seen:
            continue
        seen.add(item["id"])
        item["_clat"] = clat
        item["_clon"] = clon
        item["_hint"] = hint
        rows.append(item)
    timed("normalize", t_norm, n=len(rows), cat=category)

    t_rank = time.time()
    for item in rows:
        item["score"] = importance_score(item)
        if item.get("category") == "aero" and item.get("tier"):
            tier = item["tier"]
            item["kind"] = {
                "principale": "Aeroporto principale",
                "secondario": "Aeroporto secondario",
                "locale": "Aeroporto locale",
            }.get(str(tier), item.get("kind") or "Aeroporto")
    ranked = _dedup_rows(rows)
    ranked.sort(key=lambda r: (-int(r.get("score") or 0), r["name"].lower()))
    timed("rank", t_rank, n=len(ranked), cat=category)
    return ranked


def _trim_airports(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Caselle sì, Cuneo no: tieni il più vicino e gli internazionali."""
    if len(rows) <= 1:
        return rows

    def dist(row: dict[str, Any]) -> float:
        clat, clon = row.get("_clat"), row.get("_clon")
        if not isinstance(clat, (int, float)) or not isinstance(clon, (int, float)):
            return 0.0
        return ((float(row["lat"]) - float(clat)) ** 2 + (float(row["lon"]) - float(clon)) ** 2) ** 0.5

    ordered = sorted(rows, key=dist)
    nearest = dist(ordered[0])
    kept: list[dict[str, Any]] = []
    for row in ordered:
        d = dist(row)
        tags = row.get("tags") or {}
        kind = str(tags.get("aerodrome") or tags.get("aerodrome:type") or "").lower()
        intl = "international" in kind
        if d <= nearest + 0.03 or d <= 0.22 or intl:
            kept.append(row)
    kept.sort(key=lambda r: (-int(r.get("score") or 0), r["name"].lower()))
    return kept


def search(
    bbox: BBox | str,
    category: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    center: tuple[float, float] | list[float] | None = None,
    hint: str | None = None,
    radius_m: int | None = None,
    min_score: int | None = None,
    extra: str = "",
    around: bool = False,
) -> dict[str, Any]:
    """Una categoria: query Wizard-style, fallback solo se i candidati sono pochi."""
    cat = resolve_category(category)
    if not cat:
        return {"ok": False, "error": f"categoria sconosciuta: {category}", "rows": [], "total": 0}
    try:
        raw_box = parse_bbox(bbox)
        here = _as_center(center)
        box = _scope_bbox(raw_box, cat, here, radius_m=radius_m)
    except (TypeError, ValueError) as exc:
        return {"ok": False, "error": str(exc), "rows": [], "total": 0}

    hit = peek(raw_box, cat, center=here, extra=extra, radius_m=radius_m)
    if hit is not None:
        return hit

    meta = CATEGORIES[cat]
    pool_limit = int(meta.get("out_limit") or OUT_LIMIT)
    min_ok = int(meta.get("fallback_min") or FALLBACK_MIN)
    floor = int(meta.get("min_score") or 0) if min_score is None else int(min_score)
    around_m = int(meta.get("near_m") or meta.get("radius_m") or 600) if around else None
    t_build = time.time()
    query = build_osm_query(
        cat,
        raw_box,
        pool_limit,
        fallback=False,
        timeout=QUERY_TIMEOUT,
        center=here,
        around_m=around_m,
        radius_m=radius_m,
    )
    timed("query_build", t_build, cat=cat, around=int(around))
    used_fallback = False
    t_http = time.time()
    payload = overpass(query, timeout=timeout)
    timed("overpass_http", t_http, cat=cat, fallback=0, ok=int(bool(payload.get("ok"))), n=len(payload.get("elements") or []))
    if not payload.get("ok") and around and here:
        q_box = build_osm_query(cat, raw_box, pool_limit, fallback=False, timeout=QUERY_TIMEOUT, center=here, radius_m=around_m)
        t_httpb = time.time()
        payload = overpass(q_box, timeout=timeout)
        timed("overpass_http", t_httpb, cat=cat, around_box=1, ok=int(bool(payload.get("ok"))))
        if payload.get("ok"):
            query = q_box
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
    ranked = _ingest(payload, category=cat, box=box, hint=str(hint or ""))

    def _floor(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not floor:
            return items
        return [r for r in items if int(r.get("score") or 0) >= floor]

    rows = _floor(ranked)
    pool = len(ranked)
    fallback_clauses = tuple(meta.get("fallback") or ())
    if len(rows) < min_ok and fallback_clauses and fallback_clauses != tuple(meta.get("primary") or ()):
        t_build2 = time.time()
        q2 = build_osm_query(
            cat,
            raw_box,
            pool_limit,
            fallback=True,
            timeout=QUERY_TIMEOUT,
            center=here,
            around_m=around_m,
            radius_m=radius_m,
        )
        timed("query_build", t_build2, cat=cat, fallback=1)
        t_http2 = time.time()
        p2 = overpass(q2, timeout=timeout)
        timed("overpass_http", t_http2, cat=cat, fallback=1, ok=int(bool(p2.get("ok"))), n=len(p2.get("elements") or []))
        if p2.get("ok"):
            extra_rows = _ingest(p2, category=cat, box=box, hint=str(hint or ""))
            ranked = _dedup_rows(ranked + extra_rows)
            ranked.sort(key=lambda r: (-int(r.get("score") or 0), r["name"].lower()))
            rows = _floor(ranked)
            pool = len(ranked)
            query = q2
            used_fallback = True
    if cat == "aero" and not around:
        rows = _trim_airports(rows)
    rows = rows[:PAGE_CAP]
    for item in rows:
        item.pop("tags", None)
        item.pop("_clat", None)
        item.pop("_clon", None)
        item.pop("_hint", None)
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
        "around": around,
    }
    osm_cache.put(_cache_key(box, cat, extra), {k: v for k, v in bundle.items() if k != "cached"}, osm_cache.OVERPASS_TTL)
    log.debug("osm search cat=%s n=%d fallback=%s", cat, len(rows), used_fallback)
    return bundle


def search_near(
    lat: float,
    lon: float,
    category: str,
    *,
    hint: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Vicini a un punto OSM: around Overpass, una categoria sola."""
    cat = resolve_category(category)
    if not cat:
        return {"ok": False, "error": f"categoria sconosciuta: {category}", "rows": [], "total": 0}
    meta = CATEGORIES[cat]
    meters = int(meta.get("near_m") or meta.get("radius_m") or 600)
    box = _meters_box(float(lat), float(lon), meters)
    extra = f"near:{float(lat):.4f},{float(lon):.4f}:{meters}"
    return search(
        box,
        cat,
        timeout=timeout,
        center=(float(lat), float(lon)),
        hint=hint or "",
        radius_m=meters,
        extra=extra,
        around=True,
    )


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
        "Poi scegli una categoria. Overpass parte solo a quel punto.\n"
        "Dalla scheda apri mappa, dati OSM, dintorni (around) ed esplora zona.\n"
        "Prova anche: <i>stazioni vicino al Duomo</i>\n\n"
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
        "",
        "Cosa vuoi esplorare?",
    ]
    for key in WORLD_CATEGORIES:
        meta = CATEGORIES[key]
        lines.append(f"{meta['emoji']} {e(meta['title'])}")
    if note:
        lines.append("")
        lines.append(f"<i>{e(note)}</i>")
    lines += ["", "Overpass parte solo quando scegli una categoria.", f"<i>{OSM_NOTE}</i>"]
    return clip("\n".join(lines))


def _kind_line(row: dict[str, Any]) -> str:
    cat = CATEGORIES.get(row.get("category") or "", {})
    emoji = cat.get("emoji") or "📍"
    label = row.get("kind") or cat.get("kind") or cat.get("title") or "punto"
    return f"{emoji} {e(label)}"


def _row_line(row: dict[str, Any], index: int) -> str:
    extra: list[str] = []
    if row.get("iata") or row.get("icao"):
        extra.append(" / ".join(p for p in (row.get("iata"), row.get("icao")) if p))
    if row.get("uic"):
        extra.append(f"UIC {row['uic']}")
    bits = [f"{index}. <b>{e(row['name'])}</b>", f"   {_kind_line(row)}"]
    if row.get("platforms"):
        bits.append(f"   🚉 {e(row['platforms'])} binari")
    if row.get("capacity"):
        bits.append(f"   👥 {e(row['capacity'])}")
    if row.get("operator"):
        bits.append(f"   🏢 {e(row['operator'])}")
    if extra:
        bits.append(f"   {e(' · '.join(extra))}")
    if row.get("addr"):
        bits.append(f"   📍 {e(row['addr'])}")
    elif row.get("lat") is not None and row.get("lon") is not None:
        bits.append(f"   📍 {float(row['lat']):.4f}, {float(row['lon']):.4f}")
    if row.get("website"):
        bits.append(f'   🌐 <a href="{html.escape(str(row["website"]), quote=True)}">sito</a>')
    if row.get("map"):
        bits.append(f'   🗺️ <a href="{html.escape(str(row["map"]), quote=True)}">mappa</a>')
    return "\n".join(bits)


def format_osm_category(bundle: dict[str, Any], place: dict[str, Any] | None = None, *, limit: int = LIST_LIMIT, offset: int = 0) -> str:
    if not bundle.get("ok"):
        return (
            "🌍 <b>OSM WORLD</b>\n\n"
            "Overpass non ha risposto. Riprova tra un attimo.\n"
            f"<i>{e(bundle.get('error') or 'timeout')}</i>"
        )
    where = e((place or {}).get("display") or (place or {}).get("name") or "")
    city = where.upper() if where else ""
    cached = " · cache" if bundle.get("cached") else ""
    fb = " · fallback" if bundle.get("fallback") else ""
    rows = bundle.get("rows") or []
    start = max(0, offset)
    chunk = rows[start : start + limit]
    pool = int(bundle.get("pool") or len(rows) or 0)
    head = f"{bundle.get('emoji', '🗺️')} <b>{e(str(bundle.get('title') or '').upper())}</b>"
    if city:
        head += f" — {city}"
    tally = f"{len(chunk)} di {len(rows)}{cached}{fb}"
    if pool > len(rows):
        tally += f" · pool {pool}"
    lines = [head, tally, ""]
    if not chunk:
        lines.append("Nessun risultato utile in questa categoria per il luogo scelto.")
    for i, row in enumerate(chunk, start=start + 1):
        lines.append(_row_line(row, i))
        lines.append("")
    if start + limit < len(rows):
        lines.append(f"➡️ altri {len(rows) - start - limit}")
    lines += [f"<i>{OSM_NOTE}</i>"]
    return clip("\n".join(lines))


def format_osm_item(row: dict[str, Any], place: dict[str, Any] | None = None) -> str:
    cat = CATEGORIES.get(row.get("category") or "", {})
    head = f"{cat.get('emoji', '📍')} <b>{e(row['name'])}</b>"
    lines = ["🌍 <b>OSM WORLD</b>", head]
    if place:
        lines.append(f"📍 {e(place.get('display') or place.get('name'))}")
    lines.append(_kind_line(row))
    if row.get("addr"):
        lines.append(f"📍 {e(row['addr'])}")
    lines.append(f"{float(row['lat']):.5f}, {float(row['lon']):.5f}")
    if row.get("platforms"):
        lines.append(f"🚉 {e(row['platforms'])} binari")
    if row.get("capacity"):
        lines.append(f"👥 capienza {e(row['capacity'])}")
    if row.get("operator"):
        lines.append(f"🏢 Gestore: {e(row['operator'])}")
    if row.get("iata"):
        lines.append(f"IATA {e(row['iata'])}")
    if row.get("icao"):
        lines.append(f"ICAO {e(row['icao'])}")
    if row.get("uic"):
        lines.append(f"UIC {e(row['uic'])}")
    if row.get("emergency") == "yes":
        lines.append("🏥 pronto soccorso")
    if row.get("beds"):
        lines.append(f"posti letto {e(row['beds'])}")
    if row.get("cuisine"):
        lines.append(f"🍴 {e(row['cuisine'])}")
    if row.get("website"):
        lines.append(f'🌐 <a href="{html.escape(row["website"], quote=True)}">sito ufficiale</a>')
    if row.get("wikipedia_url"):
        lines.append(f'📖 <a href="{html.escape(row["wikipedia_url"], quote=True)}">Wikipedia</a>')
    if row.get("wikidata_url"):
        lines.append(f'🏷️ <a href="{html.escape(row["wikidata_url"], quote=True)}">Wikidata {e(row["wikidata"])}</a>')
    lines.append(f'🗺️ <a href="{row["map"]}">Apri mappa</a>')
    lines += [
        "",
        "Cosa vuoi vedere?",
        "📍 Dove si trova",
        "🏷️ Dettagli OSM",
        "🔎 Cosa c'è vicino",
        "🌍 Esplora zona",
        "",
        f"<i>{OSM_NOTE}</i>",
    ]
    return clip("\n".join(lines))


def format_osm_item_tags(row: dict[str, Any]) -> str:
    cat = CATEGORIES.get(row.get("category") or "", {})
    lines = [
        "🏷️ <b>DATI OSM</b>",
        f"{cat.get('emoji', '📍')} <b>{e(row.get('name'))}</b>",
        f"{e(row.get('osm_type') or '')}/{e(row.get('osm_id') or '')}",
        "",
    ]
    fields = (
        ("operator", "operator"),
        ("building", "building"),
        ("railway", "railway"),
        ("train", "train"),
        ("platforms", "platforms"),
        ("uic", "uic_ref"),
        ("iata", "iata"),
        ("icao", "icao"),
        ("emergency", "emergency"),
        ("beds", "beds"),
        ("capacity", "capacity"),
        ("sport", "sport"),
        ("cuisine", "cuisine"),
        ("wheelchair", "wheelchair"),
        ("wikidata", "wikidata"),
        ("wikipedia", "wikipedia"),
    )
    for key, label in fields:
        val = row.get(key)
        if val:
            lines.append(f"<code>{e(label)}</code> = {e(val)}")
    if len(lines) <= 5:
        lines.append("Pochi tag su questo oggetto.")
    lines += ["", f"<i>{OSM_NOTE}</i>"]
    return clip("\n".join(lines))


def format_osm_nearby_menu(row: dict[str, Any], *, zone: bool = False) -> str:
    title = "🌍 ESPLORA ZONA" if zone else "🔎 COSA C'È VICINO"
    lines = [
        title,
        f"📍 <b>{e(row.get('name'))}</b>",
        f"{float(row['lat']):.5f}, {float(row['lon']):.5f}",
        "",
        "Cosa c'è nei dintorni?",
    ]
    for key in NEAR_CATEGORIES:
        meta = CATEGORIES[key]
        lines.append(f"{meta['emoji']} {e(meta['title'])}")
    lines += [
        "",
        "Overpass parte solo quando scegli una categoria.",
        "Una query around sul punto, non sei query insieme.",
        f"<i>{OSM_NOTE}</i>",
    ]
    return clip("\n".join(lines))


def format_osm_item_map(row: dict[str, Any]) -> str:
    lat, lon = float(row["lat"]), float(row["lon"])
    zone = f"https://www.openstreetmap.org/#map=16/{lat:.4f}/{lon:.4f}"
    return clip(
        "\n".join(
            [
                "🗺️ <b>MAPPA</b>",
                f"📍 <b>{e(row.get('name'))}</b>",
                f"{lat:.5f}, {lon:.5f}",
                f'<a href="{row["map"]}">segnaposto</a>',
                f'<a href="{zone}">mostra zona</a>',
                "",
                f"<i>{OSM_NOTE}</i>",
            ]
        )
    )


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
