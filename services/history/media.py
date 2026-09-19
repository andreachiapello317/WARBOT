"""Immagini e documenti da archivi pubblici. Arricchiscono le schede curate, non le sostituiscono."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from services.history.sources import catalogue_doors

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
                    "date": "",
                    "license": "verificare la scheda Commons",
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
                    "date": str(item.get("date") or ""),
                    "license": "Library of Congress (diritti sulla scheda)",
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
                    "date": str((item.get("year") or [""])[0] if isinstance(item.get("year"), list) else item.get("year") or ""),
                    "license": "Europeana (diritti sulla scheda)",
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
                    "date": "",
                    "license": "Smithsonian Open Access (diritti sulla scheda)",
                }
            )
        return rows

    return _cached(f"si:{query}:{limit}", TTL, load)


def archive_items(query: str, limit: int = 6) -> list[dict[str, Any]]:
    q = f"({query}) AND (mediatype:texts OR mediatype:image)"
    params = (
        f"q={urllib.parse.quote(q)}&fl[]=identifier&fl[]=title&fl[]=year"
        f"&fl[]=mediatype&rows={limit}&page=1&output=json"
    )

    def load():
        try:
            data = _get_json(f"https://archive.org/advancedsearch.php?{params}", timeout=18)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
            return []
        rows = []
        for doc in ((data.get("response") or {}).get("docs") or [])[:limit]:
            ident = doc.get("identifier") or ""
            if not ident:
                continue
            year = doc.get("year") or ""
            if isinstance(year, list):
                year = year[0] if year else ""
            rows.append(
                {
                    "title": doc.get("title") or ident,
                    "thumb": f"https://archive.org/services/img/{ident}",
                    "url": f"https://archive.org/details/{ident}",
                    "credit": "Internet Archive",
                    "source": "Internet Archive",
                    "date": str(year),
                    "license": "verificare la scheda Internet Archive",
                }
            )
        return rows

    return _cached(f"ia:{query}:{limit}", TTL, load)


def tna_items(query: str, limit: int = 6) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"sps.searchQuery": query, "sps.resultsPageSize": str(limit)})

    def load():
        try:
            data = _get_json(
                f"https://discovery.nationalarchives.gov.uk/API/search/v1/records?{params}",
                timeout=18,
            )
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
            return []
        rows = []
        for rec in data.get("records") or []:
            rid = rec.get("id") or ""
            rows.append(
                {
                    "title": rec.get("title") or rec.get("reference") or "Documento TNA",
                    "thumb": "",
                    "url": f"https://discovery.nationalarchives.gov.uk/details/r/{rid}" if rid else "https://www.nationalarchives.gov.uk/",
                    "credit": "The National Archives (UK)",
                    "source": "The National Archives (UK)",
                    "date": rec.get("coveringDates") or rec.get("startDate") or "",
                    "license": "catalogo TNA · diritti sulla scheda",
                    "ref": rec.get("reference") or "",
                }
            )
        return rows

    return _cached(f"tna:{query}:{limit}", TTL, load)


def nasa_items(query: str, limit: int = 6) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"q": query, "media_type": "image"})

    def load():
        try:
            data = _get_json(f"https://images-api.nasa.gov/search?{params}", timeout=18)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
            return []
        rows = []
        for item in ((data.get("collection") or {}).get("items") or [])[:limit]:
            info = (item.get("data") or [{}])[0]
            links = item.get("links") or []
            thumb = ""
            for link in links:
                if link.get("rel") == "preview" or link.get("render") == "image":
                    thumb = link.get("href") or ""
                    break
            if not thumb and links:
                thumb = links[0].get("href") or ""
            nasa_id = info.get("nasa_id") or ""
            rows.append(
                {
                    "title": info.get("title") or "NASA",
                    "thumb": thumb,
                    "url": f"https://images.nasa.gov/details/{nasa_id}" if nasa_id else (item.get("href") or "https://images.nasa.gov/"),
                    "credit": "NASA Image and Video Library",
                    "source": "NASA",
                    "date": str(info.get("date_created") or "")[:10],
                    "license": "materiale NASA (verificare la scheda)",
                }
            )
        return rows

    return _cached(f"nasa:{query}:{limit}", TTL, load)


def dpla_items(query: str, limit: int = 6) -> list[dict[str, Any]]:
    key = (os.getenv("DPLA_API_KEY") or "").strip()
    if not key:
        return []
    params = urllib.parse.urlencode({"q": query, "page_size": str(limit), "api_key": key})

    def load():
        try:
            data = _get_json(f"https://api.dp.la/v2/items?{params}", timeout=18)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
            return []
        rows = []
        for item in data.get("docs") or []:
            source = (item.get("sourceResource") or {})
            title = source.get("title") or "DPLA"
            if isinstance(title, list):
                title = title[0] if title else "DPLA"
            date = source.get("date") or ""
            if isinstance(date, list):
                date = (date[0] or {}).get("displayDate") if isinstance(date[0], dict) else date[0]
            elif isinstance(date, dict):
                date = date.get("displayDate") or ""
            obj = item.get("object") or ""
            if isinstance(obj, list):
                obj = obj[0] if obj else ""
            shown = item.get("isShownAt") or item.get("id") or "https://dp.la/"
            provider = ((item.get("provider") or {}).get("name")) or "DPLA"
            rows.append(
                {
                    "title": str(title),
                    "thumb": str(obj),
                    "url": str(shown),
                    "credit": f"DPLA · {provider}",
                    "source": "Digital Public Library of America",
                    "date": str(date or ""),
                    "license": "DPLA (diritti sulla scheda)",
                }
            )
        return rows

    return _cached(f"dpla:{query}:{limit}", TTL, load)


def gallery_for(query: str, *, limit: int = 10, era_id: str | None = None, flavor: str = "img") -> list[dict[str, Any]]:
    query = (query or "").strip()
    if not query:
        return []
    chunks: list[list[dict[str, Any]]] = []
    if era_id in {"spa", "dig"} or "space" in query.lower() or "apollo" in query.lower():
        chunks.append(nasa_items(query, limit=max(4, limit // 2)))
    if flavor == "doc":
        chunks.append(tna_items(query, limit=max(4, limit // 2)))
        chunks.append(archive_items(query, limit=4))
        chunks.append(catalogue_doors(query, era_id=era_id or ""))
    chunks.append(loc_items(query, limit=max(4, limit // 2)))
    chunks.append(europeana_items(query, limit=4))
    chunks.append(smithsonian_items(query, limit=4))
    chunks.append(dpla_items(query, limit=4))
    if flavor != "doc":
        chunks.append(commons_images(query, limit=max(3, limit // 3)))
        if era_id in {"ww1", "ww2", "int", "cold"}:
            chunks.append(archive_items(query, limit=4))
    rows: list[dict[str, Any]] = []
    seen = set()
    for chunk in chunks:
        for item in chunk:
            url = item.get("url") or item.get("thumb")
            if not url or url in seen:
                continue
            if flavor == "img" and not item.get("thumb"):
                continue
            seen.add(url)
            rows.append(item)
            if len(rows) >= limit:
                return rows
    return rows

