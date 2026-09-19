"""Indice unico di WARBOT: ricerca, schede, ponti tra mondi."""

from __future__ import annotations

import random
import unicodedata
from datetime import date
from typing import Any

from services.bandiere import ITEMS as BANDIERE
from services.campi import ITEMS as CAMPI
from services.epoche import ITEMS as EPOCHE
from services.ferro import ITEMS as FERRO
from services.models import DISCLAIMER, ERA_LABELS, KIND_LABELS, WORLDS
from services.patti import ITEMS as PATTI
from services.truppe import ITEMS as TRUPPE

ALL: tuple[dict[str, Any], ...] = EPOCHE + CAMPI + TRUPPE + BANDIERE + FERRO + PATTI
BY_ID: dict[str, dict[str, Any]] = {item["id"]: item for item in ALL}


def _fold(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def by_id(eid: str) -> dict[str, Any] | None:
    return BY_ID.get(eid)


def by_world(world: str) -> list[dict[str, Any]]:
    return [item for item in ALL if item["world"] == world]


def by_kind(kind: str) -> list[dict[str, Any]]:
    return [item for item in ALL if item["kind"] == kind]


def by_era(era: str) -> list[dict[str, Any]]:
    return [item for item in ALL if item.get("era") == era and item["kind"] == "war"]


def related_items(item: dict[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for eid in item.get("related") or ():
        other = by_id(str(eid))
        if other and other["id"] != item["id"]:
            found.append(other)
    return found


def search(query: str, *, limit: int = 16) -> list[dict[str, Any]]:
    q = _fold(query.strip())
    if len(q) < 2:
        return []
    scored: list[tuple[int, dict[str, Any]]] = []
    for item in ALL:
        blob = " ".join(
            [
                item["id"],
                item["title"],
                item.get("subtitle") or "",
                " ".join(item.get("aliases") or ()),
                " ".join(item.get("tags") or ()),
                item.get("summary") or "",
            ]
        )
        hay = _fold(blob)
        score = 0
        if q == _fold(item["title"]) or q == item["id"]:
            score = 100
        elif q in _fold(item["title"]) or any(q in _fold(a) for a in item.get("aliases") or ()):
            score = 80
        elif q in hay:
            score = 40 + hay.count(q)
        if score:
            scored.append((score, item))
    scored.sort(key=lambda row: (-row[0], row[1]["title"]))
    return [item for _, item in scored[:limit]]


def of_the_day() -> dict[str, Any]:
    rng = random.Random(date.today().isoformat())
    return rng.choice(ALL)


def random_item(*, world: str | None = None, kind: str | None = None) -> dict[str, Any]:
    pool = ALL
    if world:
        pool = tuple(by_world(world))
    if kind:
        pool = tuple(item for item in pool if item["kind"] == kind)
    return random.choice(pool if pool else ALL)


def e(text: Any) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def clip(text: str, limit: int = 3900) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def format_card(item: dict[str, Any], *, section: str | None = None) -> str:
    kind_em, kind_it = KIND_LABELS.get(item["kind"], ("📄", item["kind"]))
    lines = [
        f"{item['emoji']} <b>{e(item['title'])}</b>",
        f"{kind_em} {e(kind_it)}" + (f" · {e(item['subtitle'])}" if item.get("subtitle") else ""),
        "",
        e(item["summary"]),
    ]
    if item.get("fields"):
        lines.append("")
        for label, value in item["fields"]:
            lines.append(f"{label}: {e(value)}")
    sections = item.get("sections") or ()
    if section:
        for title, body in sections:
            if _fold(title) == _fold(section) or title.startswith(section):
                lines += ["", f"<b>{e(title)}</b>", e(body)]
                break
    else:
        for title, body in sections[:2]:
            lines += ["", f"<b>{e(title)}</b>", e(body)]
    rel = related_items(item)
    if rel:
        lines.append("")
        lines.append("🔗 " + " · ".join(f"{r['emoji']} {e(r['title'])}" for r in rel[:6]))
    lines += ["", f"<i>{DISCLAIMER}</i>"]
    return clip("\n".join(lines))


def format_list(rows: list[dict[str, Any]], title: str, blurb: str) -> str:
    lines = [f"<b>{e(title)}</b>", e(blurb), ""]
    if not rows:
        lines.append("In questo cassetto del museo, per ora, non c'è nulla.")
    for item in rows:
        extra = f" — {e(item['subtitle'])}" if item.get("subtitle") else ""
        lines.append(f"{item['emoji']} <b>{e(item['title'])}</b>{extra}")
    lines += ["", f"<i>{DISCLAIMER}</i>"]
    return clip("\n".join(lines))


def format_search(query: str, rows: list[dict[str, Any]]) -> str:
    if not rows:
        return (
            f"🔎 <b>{e(query.upper())}</b>\n\n"
            "Nessuna scheda. Prova un nome più corto: Waterloo, Stalingrado, Alpini, Maginot."
        )
    lines = [f"🔎 <b>{e(query.upper())}</b>", ""]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in rows:
        grouped.setdefault(item["kind"], []).append(item)
    order = ("war", "battle", "person", "army", "vehicle", "gear", "fort", "role", "rank", "doc", "peace", "idea")
    for kind in order:
        chunk = grouped.get(kind)
        if not chunk:
            continue
        em, label = KIND_LABELS[kind]
        lines.append(f"{em} <b>{label}</b>")
        for item in chunk:
            lines.append(f"· {item['emoji']} {e(item['title'])}")
        lines.append("")
    lines.append("Tocca una scheda sotto.")
    return clip("\n".join(lines))


def era_label(era: str) -> str:
    em, name = ERA_LABELS.get(era, ("•", era))
    return f"{em} {name}"


def world_meta(key: str) -> dict[str, str]:
    return WORLDS[key]
