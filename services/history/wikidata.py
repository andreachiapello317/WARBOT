"""Client Wikidata/Wikipedia. Niente SPARQL bloccante: wbgetentities è più stabile."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

USER_AGENT = "WARBOT/1.0 (educational museum; Wikidata/Wikipedia)"
WD_API = "https://www.wikidata.org/w/api.php"
WP_SUMMARY = "https://it.wikipedia.org/api/rest_v1/page/summary/"
COMMONS_FILE = "https://commons.wikimedia.org/wiki/Special:FilePath/"

_CACHE: dict[str, tuple[float, Any]] = {}
TTL_ENTITY = 6 * 3600
TTL_WIKI = 6 * 3600


def _cached(key: str, ttl: float, loader):
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    value = loader()
    _CACHE[key] = (now, value)
    return value


def _get_json(url: str, timeout: int = 18) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _year(time_str: str | None) -> int | None:
    if not time_str:
        return None
    text = time_str.strip()
    # +1939-09-01T00:00:00Z  or -0449-01-01T00:00:00Z
    sign = -1 if text.startswith("-") else 1
    digits = text.lstrip("+-")[:4]
    if not digits.isdigit():
        return None
    year = int(digits)
    return -year if sign < 0 else year


def format_year(year: int | None) -> str:
    if year is None:
        return ""
    if year < 0:
        return f"{abs(year)} a.C."
    return str(year)


def format_span(start: int | None, end: int | None) -> str:
    a, b = format_year(start), format_year(end)
    if a and b:
        return f"{a}–{b}"
    return a or b or ""


def _claim_ids(claims: dict, pid: str) -> list[str]:
    out: list[str] = []
    for snak in claims.get(pid) or []:
        val = ((snak.get("mainsnak") or {}).get("datavalue") or {}).get("value")
        if isinstance(val, dict) and val.get("id"):
            out.append(val["id"])
    return out


def _claim_time(claims: dict, pid: str) -> int | None:
    for snak in claims.get(pid) or []:
        val = ((snak.get("mainsnak") or {}).get("datavalue") or {}).get("value")
        if isinstance(val, dict) and val.get("time"):
            return _year(val["time"])
    return None


def _claim_file(claims: dict, pid: str = "P18") -> str:
    for snak in claims.get(pid) or []:
        val = ((snak.get("mainsnak") or {}).get("datavalue") or {}).get("value")
        if isinstance(val, str) and val:
            return COMMONS_FILE + urllib.parse.quote(val.replace(" ", "_")) + "?width=800"
    return ""


def _parse_entity(raw: dict[str, Any]) -> dict[str, Any] | None:
    if not raw or raw.get("missing") is not None:
        return None
    qid = raw.get("id") or ""
    labels = raw.get("labels") or {}
    descs = raw.get("descriptions") or {}
    claims = raw.get("claims") or {}
    site = ((raw.get("sitelinks") or {}).get("itwiki") or {}).get("title") or ""
    label = (labels.get("it") or labels.get("en") or {}).get("value") or qid
    desc = (descs.get("it") or descs.get("en") or {}).get("value") or ""
    start = _claim_time(claims, "P580") or _claim_time(claims, "P585") or _claim_time(claims, "P571")
    end = _claim_time(claims, "P582") or _claim_time(claims, "P576")
    types = _claim_ids(claims, "P31")
    return {
        "id": qid,
        "label": label,
        "desc": desc,
        "start": start,
        "end": end,
        "span": format_span(start, end),
        "image": _claim_file(claims),
        "parts": _claim_ids(claims, "P527"),
        "participants": _claim_ids(claims, "P710"),
        "places": _claim_ids(claims, "P276") + _claim_ids(claims, "P17"),
        "conflicts": _claim_ids(claims, "P607") + _claim_ids(claims, "P361"),
        "types": types,
        "human": "Q5" in types,
        "wiki": site,
        "url": f"https://www.wikidata.org/wiki/{qid}",
        "source": "Wikidata",
    }


def get_entities(qids: list[str]) -> dict[str, dict[str, Any]]:
    clean = []
    seen = set()
    for qid in qids:
        qid = (qid or "").strip()
        if qid and qid not in seen and qid.startswith("Q"):
            seen.add(qid)
            clean.append(qid)
    if not clean:
        return {}

    def load() -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for i in range(0, len(clean), 40):
            chunk = clean[i : i + 40]
            query = urllib.parse.urlencode(
                {
                    "action": "wbgetentities",
                    "ids": "|".join(chunk),
                    "props": "labels|descriptions|claims|sitelinks",
                    "languages": "it|en",
                    "sitefilter": "itwiki",
                    "format": "json",
                }
            )
            try:
                data = _get_json(f"{WD_API}?{query}", timeout=22)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
                continue
            for qid, raw in (data.get("entities") or {}).items():
                parsed = _parse_entity(raw)
                if parsed:
                    out[qid] = parsed
        return out

    key = "wd:" + ",".join(clean[:80])
    return _cached(key, TTL_ENTITY, load)


def get_entity(qid: str) -> dict[str, Any] | None:
    return get_entities([qid]).get(qid)


def wiki_summary(title: str) -> dict[str, Any] | None:
    title = (title or "").strip()
    if not title:
        return None

    def load():
        path = urllib.parse.quote(title.replace(" ", "_"))
        try:
            data = _get_json(WP_SUMMARY + path, timeout=14)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
            return None
        if data.get("type") == "disambiguation":
            return None
        thumb = (data.get("thumbnail") or {}).get("source") or ""
        return {
            "title": data.get("title") or title,
            "extract": data.get("extract") or "",
            "url": (data.get("content_urls") or {}).get("desktop", {}).get("page") or "",
            "image": thumb,
            "source": "Wikipedia in italiano",
        }

    return _cached(f"wp:{title}", TTL_WIKI, load)


def search_entities(text: str, limit: int = 8) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode(
        {
            "action": "wbsearchentities",
            "search": text,
            "language": "it",
            "uselang": "it",
            "limit": str(limit),
            "format": "json",
        }
    )

    def load():
        try:
            data = _get_json(f"{WD_API}?{query}", timeout=14)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
            return []
        rows = []
        for hit in data.get("search") or []:
            qid = hit.get("id")
            if not qid:
                continue
            rows.append(
                {
                    "id": qid,
                    "label": hit.get("label") or qid,
                    "desc": hit.get("description") or "",
                    "url": f"https://www.wikidata.org/wiki/{qid}",
                    "source": "Wikidata",
                }
            )
        return rows

    return _cached(f"wds:{text}:{limit}", 1800, load)
