"""Historical Engine: un solo grafo (Wikidata Q-id) visto da epoche, persone, guerre, luoghi."""

from __future__ import annotations

import random
from typing import Any

from services.catalog import clip, e
from services.history.eras import ERA_ORDER, ERAS, all_eras, era_by_id
from services.history.media import gallery_for
from services.history.wikidata import format_year, get_entities, get_entity, search_entities, wiki_summary

NOTE = (
    "Fonti pubbliche: Wikidata, Wikipedia, Wikimedia Commons, Library of Congress"
    " (e Europeana se è impostata la chiave). Enciclopedia, non un manuale operativo."
)

SECTIONS = (
    ("ov", "🌍", "Panoramica"),
    ("tl", "⏳", "Timeline"),
    ("war", "⚔️", "Guerre e campagne"),
    ("bat", "🗺️", "Battaglie"),
    ("ppl", "👤", "Personaggi"),
    ("plc", "🗺️", "Luoghi"),
    ("sld", "🪖", "Soldati e uniformi"),
    ("tec", "⚙️", "Tecnologia"),
    ("img", "📸", "Immagini"),
    ("doc", "📜", "Documenti"),
)


def _gather(era: dict[str, Any]) -> dict[str, dict[str, Any]]:
    qids = [era["qid"], *(era.get("wars") or ()), *(era.get("people") or ())]
    hub = get_entity(era["qid"])
    if hub:
        qids.extend(hub.get("parts") or [])
        qids.extend(hub.get("participants") or [])
        qids.extend(hub.get("places") or [])
    return get_entities(qids)


def _is_human(row: dict[str, Any]) -> bool:
    return bool(row.get("human") or "Q5" in (row.get("types") or ()))


def _person_ok(row: dict[str, Any], era: dict[str, Any] | None = None) -> bool:
    label = (row.get("label") or "").strip()
    if len(label) < 3 or label.isdigit() or label.startswith("Q") and label[1:].isdigit():
        return False
    if not any(ch.isalpha() for ch in label):
        return False
    if era and row.get("id") in set(era.get("people") or ()):
        return True
    if not _is_human(row):
        return False
    if not era:
        return True
    birth, death = row.get("start"), row.get("end")
    if birth is None and death is None:
        return False
    lo, hi = era["start"], era["end"]
    if birth is not None and birth > hi + 10:
        return False
    if death is not None and death < lo - 10:
        return False
    return True


def _is_conflict(row: dict[str, Any]) -> bool:
    types = set(row.get("types") or ())
    return bool(types & {"Q198", "Q178561", "Q350604", "Q103495", "Q124734", "Q180684"}) or (
        not _is_human(row) and not types & {"Q515", "Q6256", "Q3624078"}
    )


def _is_place(row: dict[str, Any]) -> bool:
    types = set(row.get("types") or ())
    return bool(types & {"Q515", "Q6256", "Q3624078", "Q5107", "Q1549591"})


def _sorted(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda r: (r.get("start") is None, r.get("start") if r.get("start") is not None else 0, r.get("label") or ""))


def overview(era_id: str) -> dict[str, Any]:
    era = era_by_id(era_id)
    if not era:
        return {"ok": False, "error": "epoca assente"}
    hub = get_entity(era["qid"])
    title = (hub or {}).get("wiki") or era.get("wiki") or era["title"]
    wiki = wiki_summary(str(title))
    image = (hub or {}).get("image") or (wiki or {}).get("image") or ""
    extract = (wiki or {}).get("extract") or (hub or {}).get("desc") or era["title"]
    return {
        "ok": True,
        "era": era,
        "hub": hub,
        "wiki": wiki,
        "image": image,
        "extract": extract,
        "sources": ["Wikidata " + era["qid"], (wiki or {}).get("source") or ""],
    }


def list_for(era_id: str, kind: str) -> dict[str, Any]:
    era = era_by_id(era_id)
    if not era:
        return {"ok": False, "error": "epoca assente", "rows": []}
    bundle = _gather(era)
    hub = bundle.get(era["qid"])
    rows = [row for qid, row in bundle.items() if qid != era["qid"]]
    if kind == "ppl":
        picked = [r for r in rows if _person_ok(r, era)]
        extras = get_entities(list(era.get("people") or ()))
        picked.extend(
            r for r in extras.values() if r["id"] not in {x["id"] for x in picked} and _person_ok(r, era)
        )
        rows = picked
    elif kind == "war":
        rows = [r for r in rows if _is_conflict(r) and not (r.get("label") or "").lower().startswith("battaglia")]
        if hub:
            rows = [hub] + rows
    elif kind == "bat":
        rows = [r for r in rows if "battaglia" in (r.get("label") or "").lower() or "Q178561" in (r.get("types") or ())]
        if not rows:
            rows = _sorted(rows_from_parts(bundle, era))[:16]
    elif kind == "plc":
        rows = [r for r in rows if _is_place(r) or r["id"] in ((hub or {}).get("places") or [])]
        if not rows:
            rows = [bundle[qid] for qid in ((hub or {}).get("places") or []) if qid in bundle]
    else:
        rows = rows_from_parts(bundle, era)
    rows = _sorted({r["id"]: r for r in rows}.values())
    return {"ok": True, "era": era, "rows": rows[:24], "kind": kind, "hub": hub}


def rows_from_parts(bundle: dict[str, dict[str, Any]], era: dict[str, Any]) -> list[dict[str, Any]]:
    hub = bundle.get(era["qid"]) or {}
    ids = list(hub.get("parts") or [])
    return [bundle[qid] for qid in ids if qid in bundle]


def timeline(era_id: str) -> dict[str, Any]:
    packed = list_for(era_id, "tl")
    if not packed.get("ok"):
        return packed
    events = [r for r in packed["rows"] if r.get("start") is not None]
    if not events:
        events = packed["rows"]
    by_year: dict[int, list[dict[str, Any]]] = {}
    for row in events:
        year = int(row["start"]) if row.get("start") is not None else packed["era"]["start"]
        by_year.setdefault(year, []).append(row)
    years = sorted(by_year)
    return {
        "ok": True,
        "era": packed["era"],
        "years": [(year, by_year[year][:6]) for year in years[:18]],
        "count": sum(len(v) for v in by_year.values()),
    }


def gallery(era_id: str, *, flavor: str = "img") -> dict[str, Any]:
    era = era_by_id(era_id)
    if not era:
        return {"ok": False, "error": "epoca assente", "rows": []}
    query = era.get("media") or era["title"]
    if flavor == "sld":
        query = f"{era['title']} soldiers uniform photograph"
    elif flavor == "doc":
        query = f"{era['title']} document poster map"
    elif flavor == "tec":
        query = f"{era['title']} tank aircraft ship technology"
    rows = gallery_for(query, limit=12)
    return {"ok": True, "era": era, "rows": rows, "query": query, "flavor": flavor}


def entity_card(qid: str) -> dict[str, Any] | None:
    row = get_entity(qid)
    if not row:
        return None
    wiki = wiki_summary(row.get("wiki") or row["label"])
    related_ids = (row.get("parts") or [])[:8] + (row.get("participants") or [])[:8] + (row.get("places") or [])[:6]
    related = []
    for extra in get_entities(related_ids).values():
        if extra["id"] == qid:
            continue
        label = (extra.get("label") or "").strip()
        if len(label) < 3 or label.isdigit() or not any(ch.isalpha() for ch in label):
            continue
        if extra.get("human") and not _person_ok(extra):
            continue
        related.append(extra)
        if len(related) >= 12:
            break
    return {"ok": True, "item": row, "wiki": wiki, "related": related}


def travel(era_id: str | None = None) -> dict[str, Any]:
    era = era_by_id(era_id) if era_id else era_by_id(random.choice(ERA_ORDER))
    if not era:
        era = era_by_id("ww2")
    packed = timeline(era["id"])
    events = []
    for _year, rows in packed.get("years") or []:
        events.extend(rows)
    if not events:
        hub = get_entity(era["qid"])
        events = [hub] if hub else []
    pick = random.choice(events) if events else {"label": era["title"], "id": era["qid"], "start": era["start"]}
    wiki = wiki_summary(pick.get("wiki") or pick.get("label") or era["title"])
    event_people = [
        r for r in get_entities((pick.get("participants") or [])[:12]).values() if _person_ok(r, era)
    ]
    people = event_people or (list_for(era["id"], "ppl").get("rows") or [])
    images = gallery(era["id"]).get("rows") or []
    return {
        "ok": True,
        "era": era,
        "event": pick,
        "wiki": wiki,
        "people": people[:4],
        "image": (images[0] if images else None),
        "year": pick.get("start") or era["start"],
    }


def search_era_events(era_id: str, query: str) -> list[dict[str, Any]]:
    era = era_by_id(era_id)
    if not era:
        return []
    q = f"{query} {era['title']}"
    return search_entities(q, limit=10)


def format_era_index() -> str:
    lines = [
        "🌍 <b>EPOCHE</b>",
        "Una timeline viva: Wikidata, Wikipedia, immagini di musei.",
        "Non sono più solo le schede statiche del cassetto.",
        "",
    ]
    for era in all_eras():
        lines.append(f"{era['emoji']} <b>{e(era['title'])}</b> · {e(era['years'])}")
    lines += ["", "🎲 <b>Viaggia nel tempo</b> pesca un anno, un luogo, un evento.", "", f"<i>{NOTE}</i>"]
    return clip("\n".join(lines))


def format_overview(data: dict[str, Any]) -> str:
    if not data.get("ok"):
        return "Questa epoca non è in mappa."
    era, hub, wiki = data["era"], data.get("hub") or {}, data.get("wiki") or {}
    span = (hub or {}).get("span") or era["years"]
    extract = e((data.get("extract") or "")[:900])
    lines = [
        f"{era['emoji']} <b>{e(era['title']).upper()}</b>",
        f"📅 {e(span)}",
        f"Wikidata <a href=\"https://www.wikidata.org/wiki/{era['qid']}\">{era['qid']}</a>",
        "",
        extract,
        "",
    ]
    if wiki.get("url"):
        lines.append(f"<a href=\"{wiki['url']}\">Wikipedia</a>")
    if data.get("image"):
        lines.append(f"<a href=\"{data['image']}\">immagine</a>")
    lines += ["", f"<i>{NOTE}</i>"]
    return clip("\n".join(lines))


def format_list(data: dict[str, Any], heading: str) -> str:
    era = data.get("era") or {}
    lines = [f"{era.get('emoji', '🌍')} <b>{e(era.get('title', ''))} · {e(heading)}</b>", ""]
    rows = data.get("rows") or []
    if not rows:
        lines.append("Questa finestra è ancora vuota: la fonte non ha restituito entità collegate.")
    for row in rows[:16]:
        extra = f" · {e(row['span'])}" if row.get("span") else ""
        desc = e((row.get("desc") or "")[:80])
        lines.append(f"• <b>{e(row['label'])}</b>{extra}")
        if desc:
            lines.append(f"  {desc}")
    lines += ["", f"<i>{NOTE}</i>"]
    return clip("\n".join(lines))


def format_timeline(data: dict[str, Any]) -> str:
    if not data.get("ok"):
        return "Timeline non disponibile."
    era = data["era"]
    lines = [f"⏳ <b>TIMELINE · {e(era['title'])}</b>", f"{data.get('count', 0)} eventi collegati via Wikidata.", ""]
    years = data.get("years") or []
    if not years:
        lines.append("Nessuna data strutturata su questa epoca. Prova Guerre o Personaggi.")
    for year, rows in years[:14]:
        lines.append(f"<b>{e(format_year(year))}</b>")
        for row in rows[:4]:
            lines.append(f"├ {e(row['label'])}")
        lines.append("")
    lines.append(f"<i>{NOTE}</i>")
    return clip("\n".join(lines))


def format_gallery(data: dict[str, Any], heading: str) -> str:
    era = data.get("era") or {}
    lines = [f"📸 <b>{e(heading)} · {e(era.get('title', ''))}</b>", "Collezioni pubbliche, con fonte.", ""]
    rows = data.get("rows") or []
    if not rows:
        lines.append("Nessuna immagine in questo momento (rete o query vuota). Riprova tra poco.")
    for row in rows[:8]:
        title = e(row.get("title") or "senza titolo")
        credit = e(row.get("credit") or row.get("source") or "")
        url = row.get("url") or row.get("thumb") or ""
        lines.append(f"🖼 <b>{title}</b>")
        lines.append(f"{credit}")
        if url:
            lines.append(f"<a href=\"{url}\">apri</a>")
        lines.append("")
    lines.append(f"<i>{NOTE}</i>")
    return clip("\n".join(lines))


def format_entity(data: dict[str, Any]) -> str:
    item = data["item"]
    wiki = data.get("wiki") or {}
    extract = e((wiki.get("extract") or item.get("desc") or "")[:800])
    lines = [
        f"📖 <b>{e(item['label'])}</b>",
        e(item.get("span") or "") + (f" · {item['id']}" if item.get("id") else ""),
        "",
        extract,
        "",
        f"<a href=\"{item['url']}\">Wikidata</a>",
    ]
    if wiki.get("url"):
        lines.append(f"<a href=\"{wiki['url']}\">Wikipedia</a>")
    if item.get("image"):
        lines.append(f"<a href=\"{item['image']}\">immagine</a>")
    rel = data.get("related") or []
    if rel:
        lines.append("")
        lines.append("🔗 " + " · ".join(e(r["label"]) for r in rel[:6]))
    lines += ["", f"<i>{NOTE}</i>"]
    return clip("\n".join(lines))


def format_travel(data: dict[str, Any]) -> str:
    era = data["era"]
    event = data.get("event") or {}
    wiki = data.get("wiki") or {}
    year = format_year(data.get("year"))
    lines = [
        "🎲 <b>VIAGGIA NEL TEMPO</b>",
        f"🕰️ Anno: <b>{e(year)}</b>",
        f"{era['emoji']} Epoca: {e(era['title'])}",
        f"⚔️ Evento: {e(event.get('label') or era['title'])}",
        "",
        e((wiki.get("extract") or event.get("desc") or "")[:700]),
        "",
    ]
    people = data.get("people") or []
    if people:
        lines.append("👤 " + " · ".join(e(p["label"]) for p in people))
    img = data.get("image") or {}
    if img.get("url"):
        lines.append(f"<a href=\"{img['url']}\">{e(img.get('title') or 'immagine')}</a>")
    if event.get("url"):
        lines.append(f"<a href=\"{event['url']}\">Wikidata</a>")
    elif event.get("id"):
        lines.append(f"<a href=\"https://www.wikidata.org/wiki/{event['id']}\">Wikidata</a>")
    lines += ["", f"<i>{NOTE}</i>"]
    return clip("\n".join(lines))
