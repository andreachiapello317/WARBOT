"""Immagini e documenti da Commons, Library of Congress, Europeana opzionale."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

USER_AGENT = "WARBOT/1.0 (educational museum; public collections)"
_CACHE: dict[str, tuple[float, Any]] = {}
TTL = 3600


def _cached(key: str, ttl: float, loader):
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    value = loader()
    _CACHE[key] = (now, value)
    return value


def _get_json(url: str, headers: dict[str, str] | None = None, timeout: int = 16) -> Any:
    hdrs = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def commons_images(query: str, limit: int = 8) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode(
        {
            "action": "query",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": "6",
            "gsrlimit": str(limit),
            "prop": "imageinfo",
            "iiprop": "url|extmetadata|mime",
            "iiurlwidth": "640",
            "format": "json",
        }
    )

    def load():
        try:
            data = _get_json(f"https://commons.wikimedia.org/w/api.php?{params}")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
            return []
        rows = []
        for page in (data.get("query") or {}).get("pages", {}).values():
            info = (page.get("imageinfo") or [{}])[0]
            mime = info.get("mime") or ""
            if mime and not str(mime).startswith("image/"):
                continue
            meta = info.get("extmetadata") or {}
            artist = ((meta.get("Artist") or {}).get("value") or "").strip()
            rows.append(
                {
                    "title": (page.get("title") or "").replace("File:", ""),
                    "thumb": info.get("thumburl") or info.get("url") or "",
                    "url": info.get("descriptionurl") or info.get("url") or "",
                    "credit": "Wikimedia Commons" + (f" · {artist[:80]}" if artist else ""),
                    "source": "Wikimedia Commons",
                }
            )
        return rows

    return _cached(f"com:{query}:{limit}", TTL, load)


def loc_items(query: str, limit: int = 6) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"q": query, "fo": "json", "c": str(limit)})

    def load():
        try:
            data = _get_json(
                f"https://www.loc.gov/search/?{params}",
                headers={"User-Agent": "Mozilla/5.0 (compatible; WARBOT/1.0; educational museum)"},
                timeout=18,
            )
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
            return []
        rows = []
        for item in data.get("results") or []:
            images = item.get("image_url") or []
            if isinstance(images, str):
                images = [images]
            thumb = images[0] if images else ""
            rows.append(
                {
                    "title": item.get("title") or "Risorsa LoC",
                    "thumb": thumb,
                    "url": item.get("id") or item.get("url") or "https://www.loc.gov/",
                    "credit": "Library of Congress",
                    "source": "Library of Congress",
                    "date": (item.get("date") or ""),
                }
            )
        return rows

    return _cached(f"loc:{query}:{limit}", TTL, load)


def europeana_items(query: str, limit: int = 6) -> list[dict[str, Any]]:
    key = (os.getenv("EUROPEANA_API_KEY") or "").strip()
    if not key:
        return []
    params = urllib.parse.urlencode(
        {"wskey": key, "query": query, "rows": str(limit), "media": "true", "qf": "TYPE:IMAGE"}
    )

    def load():
        try:
            data = _get_json(f"https://api.europeana.eu/record/v2/search.json?{params}", timeout=18)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
            return []
        rows = []
        for item in data.get("items") or []:
            title = item.get("title") or ["Documento Europeana"]
            if isinstance(title, list):
                title = title[0] if title else "Documento Europeana"
            edm = item.get("edmPreview") or item.get("edmIsShownBy") or []
            if isinstance(edm, str):
                edm = [edm]
            rows.append(
                {
                    "title": str(title),
                    "thumb": edm[0] if edm else "",
                    "url": item.get("guid") or item.get("link") or "https://www.europeana.eu/",
                    "credit": "Europeana",
                    "source": "Europeana",
                }
            )
        return rows

    return _cached(f"eu:{query}:{limit}", TTL, load)


def smithsonian_items(query: str, limit: int = 6) -> list[dict[str, Any]]:
    key = (os.getenv("SMITHSONIAN_API_KEY") or os.getenv("DATA_GOV_API_KEY") or "").strip()
    if not key:
        return []
    params = urllib.parse.urlencode({"q": query, "rows": str(limit), "api_key": key})

    def load():
        try:
            data = _get_json(f"https://api.si.edu/openaccess/api/v1.0/search?{params}", timeout=18)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
            return []
        rows = []
        for item in (data.get("response") or {}).get("rows") or []:
            title = item.get("title") or "Smithsonian"
            media = (((item.get("content") or {}).get("descriptiveNonRepeating") or {}).get("online_media") or {}).get("media") or []
            thumb = ""
            if media:
                thumb = media[0].get("thumbnail") or media[0].get("content") or ""
            rows.append(
                {
                    "title": str(title),
                    "thumb": thumb,
                    "url": f"https://www.si.edu/object/{item.get('id') or ''}",
                    "credit": "Smithsonian Open Access",
                    "source": "Smithsonian",
                }
            )
        return rows

    return _cached(f"si:{query}:{limit}", TTL, load)


def gallery_for(query: str, *, limit: int = 10) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen = set()
    for chunk in (
        commons_images(query, limit=limit),
        loc_items(query, limit=max(4, limit // 2)),
        europeana_items(query, limit=4),
        smithsonian_items(query, limit=4),
    ):
        for item in chunk:
            url = item.get("url") or item.get("thumb")
            if not url or url in seen:
                continue
            seen.add(url)
            rows.append(item)
            if len(rows) >= limit:
                return rows
    return rows
