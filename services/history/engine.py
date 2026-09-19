"""Motore EPOCHE: schede curate WARBOT + archivi, Wikidata solo come grafo."""

from __future__ import annotations

import random
from typing import Any

from services.catalog import clip, e
from services.history.corpus import (
    FACETS,
    card_by_id,
    cards_for,
    counts_for,
    decorate,
    page_for,
    related_cards,
    search_cards,
    timeline_cards,
)
from services.history.eras import ERA_ORDER, ERAS, all_eras, era_by_id
from services.history.media import gallery_for
from services.history.sources import resolve_sources, search_url, source_meta
from services.history.wikidata import format_year, get_entity

NOTE = (
    "Schede curate WARBOT, arricchite da archivi pubblici "
    "(Europeana, Library of Congress, Smithsonian, Internet Archive, "
    "Imperial War Museums, National Archives, NASA/ESA). "
    "Wikidata è solo un grafo di collegamento. Enciclopedia, non un manuale operativo."
)

MEDIA_KINDS = frozenset({"img", "doc"})


def _source_lines(sources: list[dict[str, Any]], *, url: str = "", years: str = "") -> list[str]:
    lines = []
    if years:
        lines.append(f"📅 Data: <b>{e(years)}</b>")
    names = [src.get("name") or src.get("id") for src in sources if src.get("kind") != "graph"]
    if names:
        lines.append("📚 Fonte: " + " · ".join(e(name) for name in names[:4]))
    if url:
        lines.append(f'🔗 <a href="{url}">Fonte originale</a>')
    elif sources:
        href = sources[0].get("url") or ""
        if href:
            lines.append(f'🔗 <a href="{href}">Catalogo {e(sources[0].get("name") or "")}</a>')
    return lines


def overview(era_id: str, *, fetch_media: bool = True) -> dict[str, Any]:
    era = era_by_id(era_id)
    if not era:
        return {"ok": False, "error": "epoca assente"}
    page = page_for(era_id)
    sources = resolve_sources(page.get("src") or era.get("sources") or ())
    images: list[dict[str, Any]] = []
    if fetch_media:
        images = gallery_for(era.get("media") or era["title"], limit=4, era_id=era_id, flavor="img")
    return {
        "ok": True,
        "era": era,
        "essay": page.get("essay") or era.get("essay") or era["title"],
        "sources": sources,
        "image": images[0] if images else None,
        "counts": counts_for(era_id),
        "origin": "warbot",
    }


def list_for(era_id: str, kind: str) -> dict[str, Any]:
    era = era_by_id(era_id)
    if not era:
        return {"ok": False, "error": "epoca assente", "rows": []}
    if kind in MEDIA_KINDS:
        query = era.get("media") or era["title"]
        if kind == "doc":
            query = f"{era['title']} document report photograph"
        rows = gallery_for(query, limit=14, era_id=era_id, flavor=kind)
        curated = [decorate(card) for card in cards_for(era_id, "doc" if kind == "doc" else "art")]
        return {
            "ok": True,
            "era": era,
            "kind": kind,
            "rows": rows,
            "curated": curated[:6],
            "query": query,
            "origin": "archives",
        }
    rows = [decorate(card) for card in cards_for(era_id, kind)]
    return {"ok": True, "era": era, "kind": kind, "rows": rows, "origin": "warbot"}


def timeline(era_id: str) -> dict[str, Any]:
    era = era_by_id(era_id)
    if not era:
        return {"ok": False, "error": "epoca assente"}
    events = timeline_cards(era_id)
    by_year: dict[int, list[dict[str, Any]]] = {}
    for row in events:
        year = int(row["start"])
        by_year.setdefault(year, []).append(decorate(row))
    years = sorted(by_year)
    return {
        "ok": True,
        "era": era,
        "years": [(year, by_year[year][:6]) for year in years],
        "count": len(events),
        "origin": "warbot",
    }


def gallery(era_id: str, *, flavor: str = "img") -> dict[str, Any]:
    packed = list_for(era_id, "doc" if flavor == "doc" else "img")
    packed["flavor"] = flavor
    return packed


def entity_card(cid: str, *, fetch_media: bool = True) -> dict[str, Any] | None:
    row = card_by_id(cid)
    if not row:
        return None
    item = decorate(row)
    era = era_by_id(row["era"])
    images: list[dict[str, Any]] = []
    if fetch_media:
        images = gallery_for(row.get("media") or row["title"], limit=6, era_id=row["era"], flavor="img")
    return {
        "ok": True,
        "item": item,
        "era": era,
        "related": [decorate(r) for r in related_cards(row)],
        "images": images,
        "qid": row.get("qid") or "",
        "origin": "warbot",
    }


def graph_card(qid: str) -> dict[str, Any] | None:
    """Collegamento secondario: anagrafe Wikidata, non la scheda enciclopedica."""
    row = get_entity(qid)
    if not row:
        return None
    return {"ok": True, "item": row, "origin": "wikidata"}


def travel(era_id: str | None = None, *, fetch_media: bool = True) -> dict[str, Any]:
    era = era_by_id(era_id) if era_id else era_by_id(random.choice(ERA_ORDER))
    if not era:
        era = era_by_id("ww2")
    pool = timeline_cards(era["id"]) or cards_for(era["id"])
    pick = decorate(random.choice(pool)) if pool else decorate(
        {
            "id": era["id"],
            "title": era["title"],
            "years": era["years"],
            "summary": page_for(era["id"]).get("essay", ""),
            "src": page_for(era["id"]).get("src") or (),
            "kind": "tl",
            "era": era["id"],
        }
    )
    people = [decorate(r) for r in cards_for(era["id"], "ppl")][:4]
    images: list[dict[str, Any]] = []
    if fetch_media:
        images = gallery_for(pick.get("media") or pick["title"], limit=3, era_id=era["id"], flavor="img")
    return {
        "ok": True,
        "era": era,
        "event": pick,
        "people": people,
        "image": images[0] if images else None,
        "year": pick.get("start") or era["start"],
        "origin": "warbot",
    }


def format_era_index() -> str:
    lines = [
        "🌍 <b>EPOCHE</b>",
        "Enciclopedia curata WARBOT. Gli archivi arricchiscono; Wikidata non racconta la storia al posto nostro.",
        "",
    ]
    for era in all_eras():
        n = sum(counts_for(era["id"]).values())
        lines.append(f"{era['emoji']} <b>{e(era['title'])}</b> · {e(era['years'])} · {n} schede")
    lines += ["", "🎲 <b>Viaggia nel tempo</b> pesca un anno dalle schede, non da un grafo grezzo.", "", f"<i>{NOTE}</i>"]
    return clip("\n".join(lines))


def format_overview(data: dict[str, Any]) -> str:
    if not data.get("ok"):
        return "Questa epoca non è in mappa."
    era = data["era"]
    lines = [
        f"{era['emoji']} <b>{e(era['title']).upper()}</b>",
        f"📅 {e(era['years'])}",
        "",
        e(data.get("essay") or ""),
        "",
    ]
    lines.extend(_source_lines(data.get("sources") or [], years=era["years"]))
    counts = data.get("counts") or {}
    filled = [f"{emoji} {title}" for key, emoji, title in FACETS if counts.get(key)]
    if filled:
        lines += ["", "Sale: " + " · ".join(filled[:8])]
    img = data.get("image") or {}
    if img.get("url"):
        lines.append(f'<a href="{img["url"]}">{e(img.get("title") or "immagine d\'archivio")}</a> · {e(img.get("source") or "")}')
    lines += ["", f"<i>{NOTE}</i>"]
    return clip("\n".join(lines))


def format_list(data: dict[str, Any], heading: str) -> str:
    era = data.get("era") or {}
    lines = [f"{era.get('emoji', '🌍')} <b>{e(era.get('title', ''))} · {e(heading)}</b>", ""]
    if data.get("origin") == "archives":
        lines.append("Materiale d'archivio (con fonte sulla scheda). Le porte dei cataloghi stanno in fondo.")
        lines.append("")
        curated = data.get("curated") or []
        if curated:
            lines.append("Schede WARBOT collegate:")
            for row in curated[:4]:
                lines.append(f"• <b>{e(row['title'])}</b> · {e(row.get('years') or '')}")
            lines.append("")
    rows = data.get("rows") or []
    if not rows:
        lines.append("Sala ancora magra nel database interno. Apri i cataloghi istituzionali qui sotto, o un'altra sala.")
    for row in rows[:16]:
        if row.get("db") == "warbot" or row.get("origin") == "warbot" or row.get("summary"):
            extra = f" · {e(row.get('years') or '')}" if row.get("years") else ""
            lines.append(f"• <b>{e(row['title'])}</b>{extra}")
            src = row.get("sources") or resolve_sources(row.get("src") or ())
            if src:
                lines.append("  📚 " + " · ".join(e(s.get("name") or "") for s in src[:3]))
        else:
            date = f" · {e(row['date'])}" if row.get("date") else ""
            lines.append(f"🖼 <b>{e(row.get('title') or 'senza titolo')}</b>{date}")
            lines.append(f"  📚 {e(row.get('credit') or row.get('source') or '')}")
            if row.get("url"):
                lines.append(f'  🔗 <a href="{row["url"]}">originale</a>')
    lines += ["", f"<i>{NOTE}</i>"]
    return clip("\n".join(lines))


def format_timeline(data: dict[str, Any]) -> str:
    if not data.get("ok"):
        return "Timeline non disponibile."
    era = data["era"]
    lines = [
        f"⏳ <b>CRONOLOGIA · {e(era['title'])}</b>",
        f"{data.get('count', 0)} eventi dalle schede WARBOT, non da un dump Wikidata.",
        "",
    ]
    years = data.get("years") or []
    if not years:
        lines.append("Nessuna data in questa sala. Prova Guerre o Personaggi.")
    for year, rows in years[:16]:
        lines.append(f"<b>{e(format_year(year))}</b>")
        for row in rows[:4]:
            lines.append(f"├ {e(row['title'])}")
        lines.append("")
    lines.append(f"<i>{NOTE}</i>")
    return clip("\n".join(lines))


def format_gallery(data: dict[str, Any], heading: str) -> str:
    return format_list(data, heading)


def format_entity(data: dict[str, Any]) -> str:
    item = data["item"]
    if data.get("origin") == "wikidata":
        lines = [
            f"🔗 <b>Grafo Wikidata · {e(item.get('label') or item.get('id'))}</b>",
            "Collegamento anagrafico, non la scheda enciclopedica WARBOT.",
            "",
            e((item.get("desc") or "")[:500]),
            "",
            f'<a href="{item.get("url") or "#"}">Apri Wikidata</a>',
            "",
            f"<i>{NOTE}</i>",
        ]
        return clip("\n".join(lines))
    era = data.get("era") or ERAS.get(item.get("era") or "", {})
    lines = [
        f"{item.get('emoji', '📖')} <b>{e(item['title'])}</b>",
        f"{e(item.get('kind_title') or '')} · {e((era or {}).get('title') or '')}",
        "",
        e(item.get("summary") or ""),
        "",
    ]
    lines.extend(_source_lines(item.get("sources") or [], url=item.get("url") or "", years=item.get("years") or ""))
    if item.get("qid"):
        lines.append(f'🔗 Grafo: <a href="https://www.wikidata.org/wiki/{item["qid"]}">{item["qid"]}</a> (collegamento)')
    img = (data.get("images") or [{}])[0] if data.get("images") else {}
    if img.get("url"):
        lines.append("")
        lines.append(f'📸 {e(img.get("title") or "immagine")} · 📚 {e(img.get("source") or "")}')
        if img.get("date"):
            lines.append(f"📅 {e(img['date'])}")
        lines.append(f'<a href="{img["url"]}">originale</a>')
    rel = data.get("related") or []
    if rel:
        lines.append("")
        lines.append("🧭 " + " · ".join(e(r["title"]) for r in rel[:5]))
    lines += ["", f"<i>{NOTE}</i>"]
    return clip("\n".join(lines))


def format_travel(data: dict[str, Any]) -> str:
    era = data["era"]
    event = data.get("event") or {}
    year = format_year(data.get("year"))
    lines = [
        "🎲 <b>VIAGGIA NEL TEMPO</b>",
        f"🕰️ Anno: <b>{e(year)}</b>",
        f"{era['emoji']} Epoca: {e(era['title'])}",
        f"⚔️ Scheda: {e(event.get('title') or era['title'])}",
        "",
        e((event.get("summary") or "")[:700]),
        "",
    ]
    lines.extend(_source_lines(event.get("sources") or resolve_sources(event.get("src") or ()), url=event.get("url") or "", years=event.get("years") or year))
    people = data.get("people") or []
    if people:
        lines.append("👤 " + " · ".join(e(p["title"]) for p in people[:4]))
    img = data.get("image") or {}
    if img.get("url"):
        lines.append(f'📸 <a href="{img["url"]}">{e(img.get("title") or "immagine")}</a> · {e(img.get("source") or "")}')
    lines += ["", f"<i>{NOTE}</i>"]
    return clip("\n".join(lines))


def format_search_hits(query: str, rows: list[dict[str, Any]]) -> str:
    lines = [f"🔍 <b>EPOCHE · {e(query)}</b>", "Schede del database WARBOT.", ""]
    if not rows:
        lines.append("Nessuna scheda interna. Prova il cassetto del museo o un'altra parola.")
    for row in rows[:12]:
        lines.append(f"{row.get('emoji', '📖')} <b>{e(row['title'])}</b> · {e(row.get('years') or '')}")
    lines += ["", f"<i>{NOTE}</i>"]
    return clip("\n".join(lines))


def source_door(key: str, query: str) -> str:
    meta = source_meta(key)
    return search_url(key, query) or meta.get("url") or ""
