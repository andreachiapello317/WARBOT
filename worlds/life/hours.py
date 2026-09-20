"""Parser minimo di opening_hours OSM. Nessuna libreria esterna."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

_DAY = {"mo": 0, "tu": 1, "we": 2, "th": 3, "fr": 4, "sa": 5, "su": 6}
_TZ = {
    "it": "Europe/Rome",
    "fr": "Europe/Paris",
    "de": "Europe/Berlin",
    "es": "Europe/Madrid",
    "pt": "Europe/Lisbon",
    "gb": "Europe/London",
    "ie": "Europe/Dublin",
    "at": "Europe/Vienna",
    "ch": "Europe/Zurich",
    "nl": "Europe/Amsterdam",
    "be": "Europe/Brussels",
    "pl": "Europe/Warsaw",
    "gr": "Europe/Athens",
    "hr": "Europe/Zagreb",
    "si": "Europe/Ljubljana",
    "hu": "Europe/Budapest",
    "cz": "Europe/Prague",
    "sk": "Europe/Bratislava",
    "se": "Europe/Stockholm",
    "no": "Europe/Oslo",
    "fi": "Europe/Helsinki",
    "dk": "Europe/Copenhagen",
    "us": "America/New_York",
    "jp": "Asia/Tokyo",
    "au": "Australia/Sydney",
}
_MONTHISH = re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|sh)\b")
_TIME = re.compile(r"(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})")
_DAYS = re.compile(
    r"\b(mo|tu|we|th|fr|sa|su)(?:\s*-\s*(mo|tu|we|th|fr|sa|su))?(?:\s*,\s*(mo|tu|we|th|fr|sa|su))*",
    re.I,
)


def city_now(city: dict | None) -> datetime:
    cc = str((city or {}).get("country_code") or "").lower()
    tzname = _TZ.get(cc)
    if tzname:
        try:
            return datetime.now(ZoneInfo(tzname))
        except Exception:
            pass
    try:
        hours = int(round(float((city or {}).get("lon") or 0.0) / 15.0))
    except (TypeError, ValueError):
        hours = 0
    hours = max(-12, min(14, hours))
    return datetime.now(timezone(timedelta(hours=hours)))


def _days_from(token: str) -> set[int] | None:
    token = token.strip().lower()
    if not token:
        return None
    found: set[int] = set()
    parts = [p.strip() for p in token.split(",") if p.strip()]
    for part in parts:
        if "-" in part:
            a, b = (x.strip() for x in part.split("-", 1))
            if a not in _DAY or b not in _DAY:
                return None
            start, end = _DAY[a], _DAY[b]
            i = start
            found.add(i)
            while i != end:
                i = (i + 1) % 7
                found.add(i)
        else:
            if part not in _DAY:
                return None
            found.add(_DAY[part])
    return found or None


def _times(chunk: str) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for match in _TIME.finditer(chunk):
        h1, m1, h2, m2 = (int(match.group(i)) for i in range(1, 5))
        if not (0 <= h1 <= 24 and 0 <= h2 <= 24 and 0 <= m1 < 60 and 0 <= m2 < 60):
            continue
        a = min(h1, 23) * 60 + (0 if h1 == 24 else m1)
        if h2 == 24 and m2 == 0:
            b = 24 * 60
        else:
            b = min(h2, 23) * 60 + m2
        out.append((a, b if b != a or h1 == h2 else a))
        if h1 == h2 and m1 == m2:
            out[-1] = (0, 24 * 60)
    return out


def _in_span(minute: int, start: int, end: int) -> bool:
    if start == end:
        return True
    if start < end:
        return start <= minute < end
    return minute >= start or minute < end


def is_open_now(opening_hours: str | None, now: datetime | None = None) -> bool | None:
    """True/False se interpretabile, None se lo schema è troppo complesso o assente."""
    raw = (opening_hours or "").strip()
    if not raw:
        return None
    text = " ".join(raw.split())
    low = text.lower()
    if low in {"24/7", "24/7;"}:
        return True
    if low in {"closed", "off"}:
        return False
    if _MONTHISH.search(low) or "sunrise" in low or "sunset" in low or "||" in low:
        return None
    now = now or datetime.now(timezone.utc)
    weekday = now.weekday()
    minute = now.hour * 60 + now.minute
    matched = False
    known = False
    for rule in text.split(";"):
        chunk = rule.strip()
        if not chunk:
            continue
        low_c = chunk.lower()
        if low_c in {"ph off", "ph closed"}:
            continue
        if low_c.startswith("ph"):
            return None
        times = _times(chunk)
        day_blob = _DAYS.search(chunk)
        days = _days_from(day_blob.group(0)) if day_blob else None
        if times and days is None and not day_blob:
            days = set(range(7))
        if not times and ("off" in low_c or "closed" in low_c) and days is not None:
            known = True
            if weekday in days:
                matched = False
            continue
        if not times or days is None:
            return None
        known = True
        if weekday in days:
            if any(_in_span(minute, a, b) for a, b in times):
                matched = True
            elif "off" in low_c:
                matched = False
    if not known:
        return None
    return matched
