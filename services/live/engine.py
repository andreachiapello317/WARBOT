"""Query engine OSM WORLD — Overpass QL, non Overpass Turbo.

Fonti (principi, non esempi copiati):
- Andrea Albani, «Overpass: oltre il wizard», OSMIT 2020
  https://wiki.openstreetmap.org/w/images/7/7b/Overpass-IT-1.5.pdf  (CC-BY-SA 4.0)
- Overpass API / Overpass QL, wiki OSM
- Wizard di Turbo solo come modello AND/OR; Turbo non è l'endpoint.

WARBOT → questo compiler → Overpass API (maps.mail.ru interpreter).
Niente scorciatoie Turbo ({{bbox}}, {{geocodeArea}}, {{center}}).
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from services.live import cache as osm_cache

log = logging.getLogger("warbot.osm")

TIMING = (os.getenv("OSM_TIMING") or "").strip().lower() in {"1", "true", "yes", "on"}
FALLBACK_MIN = osm_cache.int_env("OSM_FALLBACK_MIN", 4, lo=1, hi=15)
PAGE_SIZE = osm_cache.int_env("OSM_RESULT_LIMIT", 10, lo=5, hi=20)
PAGE_CAP = osm_cache.int_env("OSM_PAGE_CAP", 10, lo=5, hi=20)

KINDS = {"node", "way", "rel", "nw", "nwr"}
OPS = {"eq", "neq", "exists", "missing", "regex", "nregex"}

BBox = tuple[float, float, float, float]
Around = tuple[float, float, int]


def _q(value: str) -> str:
    """Valore/chiave QL tra doppi apici, escape interno."""
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


@dataclass(frozen=True)
class TagFilter:
    """Un predicato AND sulla stessa entità OSM (filtri concatenati)."""

    key: str
    op: str = "exists"
    value: str = ""
    flags: str = ""

    def __post_init__(self) -> None:
        if self.op not in OPS:
            raise ValueError(f"operatore Overpass sconosciuto: {self.op}")
        if self.op in {"eq", "neq", "regex", "nregex"} and self.value == "":
            raise ValueError(f"filtro {self.op} senza valore")

    def to_ql(self) -> str:
        key = _q(self.key)
        if self.op == "exists":
            return f"[{key}]"
        if self.op == "missing":
            return f"[!{key}]"
        val = _q(self.value)
        if self.op == "eq":
            return f"[{key}={val}]"
        if self.op == "neq":
            return f"[{key}!={val}]"
        flag = f",{self.flags}" if self.flags else ""
        if self.op == "regex":
            return f"[{key}~{val}{flag}]"
        return f"[{key}!~{val}{flag}]"


@dataclass(frozen=True)
class Clause:
    """Uno statement node|way|rel|nw|nwr + filtri AND. Il tipo OSM è esplicito."""

    kind: str
    filters: tuple[TagFilter, ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"tipo OSM sconosciuto: {self.kind}")

    def selector(self) -> str:
        return self.kind + "".join(f.to_ql() for f in self.filters)


def eq(key: str, value: str) -> TagFilter:
    return TagFilter(key, "eq", value)


def neq(key: str, value: str) -> TagFilter:
    return TagFilter(key, "neq", value)


def exists(key: str) -> TagFilter:
    return TagFilter(key, "exists")


def missing(key: str) -> TagFilter:
    return TagFilter(key, "missing")


def regex(key: str, pattern: str, *, ignore_case: bool = False) -> TagFilter:
    return TagFilter(key, "regex", pattern, "i" if ignore_case else "")


def nregex(key: str, pattern: str, *, ignore_case: bool = False) -> TagFilter:
    return TagFilter(key, "nregex", pattern, "i" if ignore_case else "")


def clause(kind: str, *filters: TagFilter) -> Clause:
    return Clause(kind, tuple(filters))


def bbox_clause(bbox: BBox) -> str:
    south, west, north, east = bbox
    return f"({south},{west},{north},{east})"


def around_clause(around: Around) -> str:
    lat, lon, meters = around
    return f"(around:{int(meters)},{lat},{lon})"


def geo_clause(*, bbox: BBox | None = None, around: Around | None = None) -> str:
    """Restrizione geografica nativa: around su un punto, altrimenti bbox.

    around è il filtro del corso Albani (distanza da un oggetto/punto).
    Non è {{center}} di Turbo.
    """
    if around is not None:
        return around_clause(around)
    if bbox is not None:
        return bbox_clause(bbox)
    raise ValueError("serve around (lat,lon,m) oppure bbox south,west,north,east")


def _as_clause(item: Clause | str) -> Clause | str:
    if isinstance(item, Clause) or isinstance(item, str):
        return item
    raise TypeError(f"clausola Overpass non valida: {item!r}")


def _statement(item: Clause | str, geo: str) -> str:
    item = _as_clause(item)
    if isinstance(item, Clause):
        return f"{item.selector()}{geo}"
    selector = item.strip()
    if not selector:
        raise ValueError("clausola Overpass vuota")
    return f"{selector}{geo}"


def compile_query(
    bbox: BBox | None,
    clauses: Sequence[Clause | str],
    *,
    timeout: int,
    limit: int,
    around: Around | None = None,
    minus: Sequence[Clause | str] = (),
) -> str:
    """Compila Overpass QL.

    Settings in testa: [out:json][timeout:] — JSON per Telegram, timeout corto.
    Filtri concatenati = AND sulla stessa entità.
    Più clausole = union (OR). minus = difference (A − B).
    out center N qt: centroide + tag, senza recurse sui membri, ordine quadtile.
    """
    if not clauses:
        raise ValueError("serve almeno una clausola Overpass")
    geo = geo_clause(bbox=bbox, around=around)
    positive = [_statement(c, geo) for c in clauses]
    negative = [_statement(c, geo) for c in minus]
    if negative:
        pos = "\n  ".join(f"{s};" for s in positive)
        neg = "\n  ".join(f"- {s};" for s in negative)
        body = f"(\n  {pos}\n  {neg}\n);"
    elif len(positive) == 1:
        body = f"{positive[0]};"
    else:
        union = "\n  ".join(f"{s};" for s in positive)
        body = f"(\n  {union}\n);"
    return (
        f"[out:json][timeout:{int(timeout)}];\n"
        f"{body}\n"
        f"out center {int(limit)} qt;"
    )


def as_clauses(raw: Iterable[Any]) -> tuple[Clause | str, ...]:
    return tuple(_as_clause(item) for item in raw)


def timed(label: str, t0: float, **extra: Any) -> float:
    elapsed = time.time() - t0
    if TIMING:
        bits = " ".join(f"{k}={v}" for k, v in extra.items())
        log.info("timing %s %.3fs %s", label, elapsed, bits)
    return elapsed
