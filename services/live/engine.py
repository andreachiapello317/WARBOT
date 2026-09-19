"""Query engine OSM WORLD.

Ispirato al Wizard di Overpass Turbo (DNF: unione di congiunzioni, AND/NOT sui tag,
bbox, [out:json], out center), NON all'interfaccia Turbo come servizio.

WARBOT → questo builder → Overpass API (maps.mail.ru).
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from services.live import cache as osm_cache

log = logging.getLogger("warbot.osm")

TIMING = (os.getenv("OSM_TIMING") or "").strip().lower() in {"1", "true", "yes", "on"}
FALLBACK_MIN = osm_cache.int_env("OSM_FALLBACK_MIN", 4, lo=1, hi=15)
PAGE_SIZE = osm_cache.int_env("OSM_RESULT_LIMIT", 10, lo=5, hi=20)
PAGE_CAP = osm_cache.int_env("OSM_PAGE_CAP", 10, lo=5, hi=20)


def bbox_clause(bbox: tuple[float, float, float, float]) -> str:
    south, west, north, east = bbox
    return f"({south},{west},{north},{east})"


def compile_query(
    bbox: tuple[float, float, float, float],
    clauses: tuple[str, ...],
    *,
    timeout: int,
    limit: int,
) -> str:
    """Compila una query Overpass QL in stile Wizard: union + bbox + JSON + center."""
    if not clauses:
        raise ValueError("serve almeno una clausola Overpass")
    area = bbox_clause(bbox)
    if len(clauses) == 1:
        body = f"{clauses[0]}{area};"
    else:
        union = "\n  ".join(f"{clause}{area};" for clause in clauses)
        body = f"(\n  {union}\n);"
    return (
        f"[out:json][timeout:{timeout}];\n"
        f"{body}\n"
        f"out center {limit};"
    )


def timed(label: str, t0: float, **extra: Any) -> float:
    elapsed = time.time() - t0
    if TIMING:
        bits = " ".join(f"{k}={v}" for k, v in extra.items())
        log.info("timing %s %.3fs %s", label, elapsed, bits)
    return elapsed
