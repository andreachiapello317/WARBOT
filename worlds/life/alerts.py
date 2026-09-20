"""Allerte Meteoalarm (CAP JSON). Cache globale, niente API key."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from core.http import error_code, http_get_retry, parse_json

log = logging.getLogger("warbot.life")

METEOALARM = "https://feeds.meteoalarm.org/api/v1/warnings/{feed}"
TIMEOUT_S = 20
CACHE_TTL = 1200
MISS_TTL = 1800

_FEEDS = {
    "it": "feeds-italy",
    "fr": "feeds-france",
    "de": "feeds-germany",
    "es": "feeds-spain",
    "pt": "feeds-portugal",
    "at": "feeds-austria",
    "ch": "feeds-switzerland",
    "be": "feeds-belgium",
    "nl": "feeds-netherlands",
    "pl": "feeds-poland",
    "gr": "feeds-greece",
    "hr": "feeds-croatia",
    "si": "feeds-slovenia",
    "hu": "feeds-hungary",
    "cz": "feeds-czechia",
    "sk": "feeds-slovakia",
    "ie": "feeds-ireland",
    "gb": "feeds-united-kingdom",
    "uk": "feeds-united-kingdom",
    "se": "feeds-sweden",
    "no": "feeds-norway",
    "fi": "feeds-finland",
    "dk": "feeds-denmark",
}

_cache: dict[str, tuple[float, dict[str, Any]]] = {}

_LANG = {
    "it": "it",
    "fr": "fr",
    "de": "de",
    "es": "es",
    "pt": "pt",
    "nl": "nl",
    "pl": "pl",
    "gr": "el",
    "hr": "hr",
    "si": "sl",
    "hu": "hu",
    "cz": "cs",
    "sk": "sk",
    "se": "sv",
    "no": "no",
    "fi": "fi",
    "dk": "da",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(raw: str | None) -> datetime | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _norm(text: str) -> str:
    return " ".join(text.lower().replace("'", " ").split())


def fetch_meteoalarm(country_code: str) -> dict[str, Any]:
    cc = (country_code or "").strip().lower()
    feed = _FEEDS.get(cc)
    if not feed:
        return {"ok": True, "rows": [], "supported": False, "country": cc, "provider": "meteoalarm"}
    hit = _cache.get(feed)
    if hit and time.time() - hit[0] < (CACHE_TTL if hit[1].get("ok") else MISS_TTL):
        return dict(hit[1])
    url = METEOALARM.format(feed=feed)
    http, body, _hdrs, ms = http_get_retry(url, timeout=TIMEOUT_S)
    log.info("[API] provider=meteoalarm feed=%s request_ms=%.0f http=%s", feed, ms, http if http > 0 else "000")
    if http != 200:
        bundle = {
            "ok": False,
            "code": error_code(http),
            "http": http,
            "request_ms": ms,
            "rows": [],
            "supported": True,
            "provider": "meteoalarm",
        }
        _cache[feed] = (time.time(), bundle)
        return bundle
    payload, bad = parse_json(body)
    if bad or not isinstance(payload, dict):
        bundle = {
            "ok": False,
            "code": error_code(http, invalid_json=bad),
            "http": http,
            "rows": [],
            "supported": True,
            "provider": "meteoalarm",
        }
        _cache[feed] = (time.time(), bundle)
        return bundle
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    prefer = _LANG.get(cc, "en")
    now = _now()
    for item in payload.get("warnings") or []:
        if not isinstance(item, dict):
            continue
        alert = item.get("alert") if isinstance(item.get("alert"), dict) else {}
        ident = str(alert.get("identifier") or "")
        infos = alert.get("info") or []
        if isinstance(infos, dict):
            infos = [infos]
        picked = None
        fallback = None
        for info in infos:
            if not isinstance(info, dict):
                continue
            lang = str(info.get("language") or "").lower()
            if prefer and lang.startswith(prefer):
                picked = info
                break
            if fallback is None and (lang.startswith("en") or not lang):
                fallback = info
        info = picked or fallback
        if not isinstance(info, dict):
            continue
        expires = _parse_iso(str(info.get("expires") or ""))
        if expires is not None and expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires is not None and expires < now:
            continue
        severity = str(info.get("severity") or "")
        desc = str(info.get("description") or "")
        if "No Special Awareness" in desc or "Nessuna allerta" in desc:
            continue
        if severity.lower() in {"unknown", "none"}:
            continue
        event = info.get("event") or info.get("headline") or "allerta"
        if isinstance(event, list):
            event = event[0] if event else "allerta"
        areas = info.get("area") or []
        if isinstance(areas, dict):
            areas = [areas]
        area_names = [str(a.get("areaDesc") or "") for a in areas if isinstance(a, dict)]
        key = ident or f"{event}|{','.join(area_names)}|{info.get('expires')}"
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "id": ident,
                "event": str(event),
                "headline": str(info.get("headline") or event),
                "severity": severity,
                "certainty": str(info.get("certainty") or ""),
                "areas": [a for a in area_names if a],
                "onset": str(info.get("onset") or info.get("effective") or "")[:16],
                "expires": str(info.get("expires") or "")[:16],
                "description": desc.split("DISCLAIMER")[0].strip()[:240],
            }
        )
    bundle = {
        "ok": True,
        "rows": rows,
        "supported": True,
        "country": cc,
        "provider": "meteoalarm",
        "request_ms": ms,
        "http": http,
    }
    _cache[feed] = (time.time(), bundle)
    return dict(bundle)


def filter_for_city(rows: list[dict[str, Any]], city: dict[str, Any]) -> list[dict[str, Any]]:
    state = _norm(str(city.get("state") or city.get("region") or ""))
    mun = _norm(str(city.get("municipality") or city.get("name") or ""))
    pool = rows
    if state or mun:
        matched: list[dict[str, Any]] = []
        for row in rows:
            blob = _norm(" ".join(row.get("areas") or []))
            if state and state in blob:
                matched.append(row)
                continue
            if mun and mun in blob:
                matched.append(row)
        pool = matched or [
            r for r in rows if str(r.get("severity") or "").lower() in {"severe", "extreme", "moderate"}
        ][:8]
    serious = [
        r
        for r in pool
        if str(r.get("severity") or "").lower() in {"moderate", "severe", "extreme"}
    ]
    chosen = serious or []
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in chosen:
        key = f"{_norm(str(row.get('event') or ''))}|{','.join(row.get('areas') or [])}"
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out[:12]
