"""Istituzioni citate sulle schede EPOCHE. Wikidata è solo un grafo, non una fonte."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

SOURCES: dict[str, dict[str, str]] = {
    "europeana": {
        "name": "Europeana",
        "url": "https://www.europeana.eu/",
        "search": "https://www.europeana.eu/en/search?query={q}",
        "kind": "archive",
    },
    "loc": {
        "name": "Library of Congress",
        "url": "https://www.loc.gov/",
        "search": "https://www.loc.gov/search/?q={q}",
        "kind": "archive",
    },
    "si": {
        "name": "Smithsonian Open Access",
        "url": "https://www.si.edu/openaccess",
        "search": "https://www.si.edu/search/collection-images?q={q}",
        "kind": "museum",
    },
    "ia": {
        "name": "Internet Archive",
        "url": "https://archive.org/",
        "search": "https://archive.org/search?query={q}",
        "kind": "archive",
    },
    "dpla": {
        "name": "Digital Public Library of America",
        "url": "https://dp.la/",
        "search": "https://dp.la/search?q={q}",
        "kind": "archive",
    },
    "bm": {
        "name": "British Museum",
        "url": "https://www.britishmuseum.org/collection",
        "search": "https://www.britishmuseum.org/collection/search?keyword={q}",
        "kind": "museum",
    },
    "iwm": {
        "name": "Imperial War Museums",
        "url": "https://www.iwm.org.uk/collections",
        "search": "https://www.iwm.org.uk/collections/search?query={q}",
        "kind": "museum",
    },
    "nara": {
        "name": "U.S. National Archives",
        "url": "https://www.archives.gov/",
        "search": "https://catalog.archives.gov/search?q={q}",
        "kind": "archive",
    },
    "tna": {
        "name": "The National Archives (UK)",
        "url": "https://www.nationalarchives.gov.uk/",
        "search": "https://discovery.nationalarchives.gov.uk/results/r?_q={q}",
        "kind": "archive",
    },
    "nasa": {
        "name": "NASA Image and Video Library",
        "url": "https://images.nasa.gov/",
        "search": "https://images.nasa.gov/search?q={q}",
        "kind": "agency",
    },
    "esa": {
        "name": "ESA",
        "url": "https://www.esa.int/",
        "search": "https://www.esa.int/esearch?q={q}",
        "kind": "agency",
    },
    "commons": {
        "name": "Wikimedia Commons",
        "url": "https://commons.wikimedia.org/",
        "search": "https://commons.wikimedia.org/w/index.php?search={q}",
        "kind": "media",
    },
    "wd": {
        "name": "Wikidata",
        "url": "https://www.wikidata.org/",
        "search": "https://www.wikidata.org/w/index.php?search={q}",
        "kind": "graph",
    },
}


def source_meta(key: str) -> dict[str, str]:
    return SOURCES.get(key) or {"name": key, "url": "", "search": "", "kind": "other"}


def resolve_sources(keys: tuple[str, ...] | list[str] | None) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen = set()
    for key in keys or ():
        if key in seen:
            continue
        seen.add(key)
        meta = source_meta(key)
        out.append({"id": key, **meta})
    return out


def search_url(key: str, query: str) -> str:
    meta = source_meta(key)
    pattern = meta.get("search") or meta.get("url") or ""
    if "{q}" in pattern:
        return pattern.format(q=quote_plus(query))
    return meta.get("url") or ""


def catalogue_doors(query: str, *, era_id: str = "") -> list[dict[str, Any]]:
    """Porte verso i cataloghi: non sono oggetti, sono la fonte originale da aprire."""
    keys = ["loc", "europeana", "ia", "bm"]
    if era_id in {"ww1", "ww2", "int", "cold"}:
        keys = ["iwm", "tna", "loc", "nara", "europeana"]
    elif era_id in {"spa", "dig"}:
        keys = ["nasa", "esa", "loc", "si"]
    elif era_id in {"pre", "ant", "gre", "rom", "tarda"}:
        keys = ["bm", "loc", "europeana", "si"]
    rows = []
    for key in keys:
        meta = source_meta(key)
        url = search_url(key, query)
        rows.append(
            {
                "title": f"Cerca «{query}» · {meta['name']}",
                "url": url,
                "thumb": "",
                "credit": meta["name"],
                "source": meta["name"],
                "date": "",
                "kind": "catalogue",
            }
        )
    return rows
