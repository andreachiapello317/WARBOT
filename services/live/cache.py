"""Cache OSM WORLD: memoria + file JSON, TTL da variabile d'ambiente."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

_lock = threading.Lock()
_mem: dict[str, tuple[float, float, Any]] = {}
_loaded = False


def int_env(name: str, default: int, *, lo: int | None = None, hi: int | None = None) -> int:
    raw = (os.getenv(name) or "").strip()
    try:
        value = int(raw) if raw else default
    except ValueError:
        value = default
    if lo is not None:
        value = max(lo, value)
    if hi is not None:
        value = min(hi, value)
    return value


GEOCODE_TTL = int_env("OSM_CACHE_TTL_GEOCODE", 6 * 3600)
OVERPASS_TTL = int_env("OSM_CACHE_TTL_OVERPASS", 3 * 3600)
CACHE_PATH = Path(os.getenv("OSM_CACHE_FILE") or "data/osm_cache.json")


def _load_unlocked() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    try:
        raw = CACHE_PATH.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return
    if not isinstance(payload, dict):
        return
    now = time.time()
    for key, row in payload.items():
        if not isinstance(row, dict):
            continue
        try:
            ts = float(row["t"])
            ttl = float(row.get("ttl") or 0)
        except (KeyError, TypeError, ValueError):
            continue
        if ttl <= 0 or now - ts >= ttl:
            continue
        _mem[str(key)] = (ts, ttl, row.get("v"))


def _save_unlocked() -> None:
    now = time.time()
    payload: dict[str, Any] = {}
    for key, (ts, ttl, value) in _mem.items():
        if ttl <= 0 or now - ts >= ttl:
            continue
        payload[key] = {"t": ts, "ttl": ttl, "v": value}
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        tmp.replace(CACHE_PATH)
    except OSError:
        pass


def get(key: str) -> Any | None:
    """Valore ancora valido, altrimenti None. Non tocca la rete."""
    with _lock:
        _load_unlocked()
        hit = _mem.get(key)
        if not hit:
            return None
        ts, ttl, value = hit
        if ttl <= 0 or time.time() - ts >= ttl:
            _mem.pop(key, None)
            return None
        return value


def put(key: str, value: Any, ttl: int) -> None:
    if ttl <= 0:
        return
    with _lock:
        _load_unlocked()
        _mem[key] = (time.time(), float(ttl), value)
        _save_unlocked()
