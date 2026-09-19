#!/usr/bin/env python3
"""Museo web di WARBOT: gli stessi sei mondi del bot Telegram, da sfogliare nel browser."""

from __future__ import annotations

import html
import json
import random
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from services.catalog import (
    ALL,
    by_era,
    by_id,
    by_kind,
    format_search,
    of_the_day,
    random_item,
    related_items,
    search,
)
from services.history.engine import (
    entity_card,
    gallery,
    graph_card,
    list_for,
    overview,
    timeline,
    travel,
)
from services.history.corpus import search_cards
from services.history.eras import ERAS, all_eras
from services.history.pack import FACETS
from services.live import (
    LIVE_NOTE,
    REGIONS,
    fetch_aircraft,
    fetch_hub,
    fetch_iss,
    fetch_ships,
)
from services.models import DISCLAIMER, ERA_LABELS, KIND_LABELS, WORLDS
from services.quiz import build_quiz
from ui.texts import cerca_text, esplora_text, help_text, home_text, quiz_hub_text, world_text

HOST = "0.0.0.0"
PORT = 47261


def h(text: object) -> str:
    return html.escape(str(text), quote=True)


def nav() -> str:
    chips = "".join(
        f'<a class="chip" href="/w/{key}">{meta["emoji"]} {meta["title"].title()}</a>'
        for key, meta in WORLDS.items()
    )
    return f"""
    <header class="top">
      <a class="brand" href="/">⚔️ WARBOT</a>
      <nav>{chips}
        <a class="chip" href="/oggi">📖 Oggi</a>
        <a class="chip" href="/casuale">🎲 Casuale</a>
        <a class="chip" href="/cerca">🔍 Cerca</a>
        <a class="chip" href="/quiz">🎲 Quiz</a>
        <a class="chip" href="/live">📡 Posizioni live</a>
      </nav>
    </header>"""


def layout(title: str, body: str, *, lead: str = "", extra_head: str = "", extra_script: str = "") -> str:
    return f"""<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{h(title)} · WARBOT</title>
  {extra_head}
  <style>
    :root {{
      --bg:#12140f; --panel:#1c2118; --ink:#e8e0c8; --muted:#b7aa8a;
      --brass:#c4a35a; --line:#3a3f32; --olive:#6b7f4a; --red:#8c2f2f;
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0; font-family:"Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif;
      background:
        radial-gradient(1200px 500px at 10% -10%, #2a311f 0%, transparent 50%),
        var(--bg);
      color:var(--ink); min-height:100vh;
    }}
    a {{ color:var(--brass); text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    .top {{
      display:flex; flex-wrap:wrap; gap:12px 18px; align-items:center;
      justify-content:space-between; padding:18px 22px;
      border-bottom:1px solid var(--line); background:#161910cc; backdrop-filter:blur(8px);
      position:sticky; top:0; z-index:2;
    }}
    .brand {{ font-size:1.35rem; letter-spacing:.08em; color:var(--ink); font-weight:700; }}
    nav {{ display:flex; flex-wrap:wrap; gap:8px; }}
    .chip {{
      display:inline-block; padding:7px 12px; border:1px solid var(--line);
      background:var(--panel); color:var(--ink); border-radius:999px; font-size:.92rem;
    }}
    .wrap {{ max-width:980px; margin:0 auto; padding:28px 18px 80px; }}
    h1 {{ font-size:clamp(1.8rem, 4vw, 2.8rem); margin:0 0 8px; letter-spacing:.02em; }}
    .lead {{ color:var(--muted); font-size:1.12rem; line-height:1.5; white-space:pre-wrap; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:14px; margin-top:22px; }}
    .card {{
      background:var(--panel); border:1px solid var(--line); padding:18px 16px;
      border-radius:14px; min-height:140px; display:flex; flex-direction:column; gap:8px;
    }}
    .card:hover {{ border-color:var(--brass); }}
    .card.live {{
      border-color:var(--brass);
      background:linear-gradient(165deg, #2c341c 0%, var(--panel) 55%);
      min-height:120px;
    }}
    .card h2 {{ margin:0; font-size:1.25rem; }}
    .card p {{ margin:0; color:var(--muted); line-height:1.45; }}
    .meta {{ display:flex; flex-wrap:wrap; gap:8px 14px; color:var(--muted); margin:16px 0; }}
    .field {{ background:#0003; border:1px solid var(--line); padding:8px 10px; border-radius:8px; }}
    article section {{ margin-top:22px; }}
    article h3 {{ margin:0 0 8px; color:var(--brass); font-size:1.05rem; letter-spacing:.06em; text-transform:uppercase; }}
    .note {{ margin-top:28px; font-size:.92rem; color:var(--muted); border-top:1px solid var(--line); padding-top:14px; }}
    form {{ display:flex; gap:8px; margin-top:18px; }}
    input[type=search], input[type=text] {{
      flex:1; padding:12px 14px; border-radius:10px; border:1px solid var(--line);
      background:#0e100c; color:var(--ink); font:inherit;
    }}
    button, .btn {{
      font:inherit; cursor:pointer; background:var(--brass); color:#1a1408;
      border:0; padding:12px 16px; border-radius:10px; font-weight:700;
    }}
    .opts {{ display:grid; gap:10px; margin-top:18px; }}
    .opts a, .opts button {{
      display:block; width:100%; text-align:left; background:var(--panel);
      color:var(--ink); border:1px solid var(--line); padding:14px;
    }}
    .gallery {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:10px; margin-top:16px; }}
    .gallery a {{ display:block; background:var(--panel); border:1px solid var(--line); border-radius:12px; overflow:hidden; color:var(--ink); }}
    .gallery img {{ width:100%; height:140px; object-fit:cover; display:block; background:#0e100c; }}
    .gallery span {{ display:block; padding:8px 10px; font-size:.85rem; color:var(--muted); }}
    .ok {{ color:#b6d48a; }}
    .ko {{ color:#e7a2a2; }}
    #map {{
      height:min(62vh, 520px); margin:18px 0; border-radius:14px;
      border:1px solid var(--line); background:#0e100c;
    }}
    .live-table {{ width:100%; border-collapse:collapse; margin-top:12px; font-size:.95rem; }}
    .live-table th, .live-table td {{
      text-align:left; padding:8px 6px; border-bottom:1px solid var(--line); vertical-align:top;
    }}
    .live-table th {{ color:var(--brass); font-size:.82rem; letter-spacing:.04em; text-transform:uppercase; }}
    .src {{
      font-size:.92rem; color:var(--muted); border-left:3px solid var(--brass);
      padding:10px 14px; margin:16px 0; background:#0002; border-radius:0 10px 10px 0;
    }}
    .src a {{ margin-right:10px; }}
    @media (max-width:640px) {{
      .top {{ padding:12px; }}
      .brand {{ width:100%; }}
      .live-table {{ font-size:.85rem; }}
    }}
  </style>
</head>
<body>
  {nav()}
  <main class="wrap">
    {f'<p class="lead">{h(lead)}</p>' if lead else ''}
    {body}
    <p class="note">{h(DISCLAIMER)}</p>
  </main>
  {extra_script}
</body>
</html>"""


def telegramish(text: str) -> str:
    raw = html.escape(text)
    raw = raw.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
    raw = raw.replace("&lt;i&gt;", "<i>").replace("&lt;/i&gt;", "</i>")
    return f'<div class="lead" style="white-space:pre-wrap">{raw}</div>'


def card_tile(item: dict) -> str:
    return (
        f'<a class="card" href="/e/{h(item["id"])}">'
        f'<h2>{item["emoji"]} {h(item["title"])}</h2>'
        f'<p>{h(item.get("subtitle") or KIND_LABELS.get(item["kind"], ("", item["kind"]))[1])}</p>'
        f"</a>"
    )


def render_home() -> str:
    worlds = "".join(
        f'<a class="card" href="/w/{key}"><h2>{meta["emoji"]} {h(meta["title"])}</h2><p>{h(meta["blurb"])}</p></a>'
        for key, meta in WORLDS.items()
    )
    extras = """
    <div class="grid">
      <a class="card live" href="/live"><h2>📡 Posizioni live</h2><p>Aerei in volo, navi del Baltico, ISS. Coordinate vere, aggiornate adesso. Tocca qui.</p></a>
      <a class="card" href="/oggi"><h2>📖 Oggi</h2><p>La scheda del giorno, come COSMICO ma da museo.</p></a>
      <a class="card" href="/casuale"><h2>🎲 Casuale</h2><p>Un cassetto a caso.</p></a>
      <a class="card" href="/cerca"><h2>🔍 Cerca</h2><p>Scrivi Stalingrado e vedi i ponti.</p></a>
      <a class="card" href="/quiz"><h2>🎲 Quiz</h2><p>Dieci modi per mettere alla prova il catalogo.</p></a>
    </div>"""
    body = f"{telegramish(home_text())}<div class='grid'>{worlds}</div>{extras}"
    return layout("Museo", body)


def render_world(key: str) -> str:
    meta = WORLDS[key]
    if key == "epoche":
        tiles = "".join(
            f'<a class="card" href="/era/{h(era["id"])}"><h2>{era["emoji"]} {h(era["title"])}</h2>'
            f'<p>{h(era["years"])}</p></a>'
            for era in all_eras()
        )
        extra = (
            '<p class="meta">'
            '<a class="chip" href="/viaggia">🎲 Viaggia nel tempo</a> '
            '<a class="chip" href="/l/war/all">📚 Cassetto del museo</a>'
            "</p>"
        )
        body = (
            f"<h1>{meta['emoji']} {h(meta['title'])}</h1>"
            "<p class='lead'>Diciotto ere. Schede curate WARBOT, arricchite da musei e archivi. "
            "Wikidata è solo un grafo, non la fonte della sala.</p>"
            + extra
            + f"<div class='grid'>{tiles}</div>"
        )
        return layout(meta["title"], body)
    rows = [item for item in ALL if item["world"] == key]
    filters = ""
    if key == "ferro":
        filters = '<p class="meta"><a class="chip" href="/live">📡 Posizioni live: aerei, navi, ISS</a></p>'
    tiles = "".join(card_tile(item) for item in rows)
    body = f"<h1>{meta['emoji']} {h(meta['title'])}</h1>{telegramish(world_text(key))}{filters}<div class='grid'>{tiles}</div>"
    return layout(meta["title"], body)


FACET_SLUG = {
    "tl": "cronologia",
    "civ": "civilta",
    "war": "guerre",
    "arm": "eserciti",
    "ppl": "persone",
    "ter": "territori",
    "cty": "citta",
    "sci": "scienza",
    "art": "arte",
    "lit": "letteratura",
    "rel": "religioni",
    "eco": "economia",
    "tec": "tecnologia",
    "trn": "trasporti",
    "arc": "architettura",
    "plc": "luoghi",
    "doc": "documenti",
    "img": "immagini",
}
SLUG_FACET = {slug: key for key, slug in FACET_SLUG.items()}
SLUG_FACET.update({"timeline": "tl", "soldati": "arm", "battaglie": "war", "tecnologia": "tec"})


def _era_nav(eid: str, active: str = "ov") -> str:
    links = [("ov", f"/era/{eid}", "🌍 Panoramica")]
    links += [(key, f"/era/{eid}/{FACET_SLUG[key]}", f"{emoji} {title}") for key, emoji, title in FACETS]
    chips = []
    for key, href, label in links:
        style = "border-color:var(--brass)" if key == active else ""
        chips.append(f'<a class="chip" href="{href}" style="{style}">{label}</a>')
    chips.append('<a class="chip" href="/w/epoche">🌍 Tutte le epoche</a>')
    chips.append('<a class="chip" href="/viaggia">🎲 Viaggia</a>')
    return f'<div class="tabs">{"".join(chips)}</div>'


def _source_box(sources: list, *, url: str = "", years: str = "") -> str:
    bits = []
    if years:
        bits.append(f"<div>📅 Data: {h(years)}</div>")
    names = [s.get("name") or s.get("id") for s in sources or [] if s.get("kind") != "graph"]
    if names:
        bits.append("<div>📚 Fonte: " + " · ".join(h(n) for n in names[:4]) + "</div>")
    if url:
        bits.append(f'<div>🔗 <a href="{h(url)}" target="_blank" rel="noopener">Fonte originale</a></div>')
    elif sources:
        href = (sources[0] or {}).get("url") or ""
        if href:
            bits.append(f'<div>🔗 <a href="{h(href)}" target="_blank" rel="noopener">Catalogo {h(sources[0].get("name") or "")}</a></div>')
    if not bits:
        return ""
    return f'<div class="src">{"".join(bits)}</div>'


def _gallery_html(rows: list[dict]) -> str:
    if not rows:
        return "<p>Nessuna immagine in questo momento.</p>"
    bits = []
    for row in rows[:12]:
        src = h(row.get("thumb") or "")
        href = h(row.get("url") or row.get("thumb") or "#")
        title = h(row.get("title") or "")
        credit = h(row.get("credit") or row.get("source") or "")
        date = h(row.get("date") or "")
        if date:
            credit = f"{credit} · {date}" if credit else date
        img = f'<img src="{src}" alt="{title}"/>' if src else ""
        if not src:
            bits.append(
                f'<a href="{href}" target="_blank" rel="noopener"><span><b>{title}</b><br>{credit}</span></a>'
            )
            continue
        bits.append(f'<a href="{href}" target="_blank" rel="noopener">{img}<span>{title}<br>{credit}</span></a>')
    return f'<div class="gallery">{"".join(bits)}</div>'


def render_era(eid: str, view: str = "ov") -> str:
    era = ERAS.get(eid)
    if not era:
        return layout("Epoca assente", "<h1>Epoca non in mappa</h1><p><a href='/w/epoche'>Torna alle epoche</a></p>")
    if view == "tl":
        data = timeline(eid)
        blocks = []
        for year, rows in data.get("years") or []:
            items = "".join(
                f'<li><a href="/hc/{h(r["id"])}">{h(r["title"])}</a> · {h(r.get("years") or "")}</li>'
                for r in rows
            )
            blocks.append(f"<h3>{h(year)}</h3><ul>{items}</ul>")
        body = (
            f"<h1>{era['emoji']} {h(era['title'])} · Cronologia</h1>"
            + _era_nav(eid, "tl")
            + "<p class='lead'>Eventi dalle schede WARBOT, ciascuno con fonte.</p>"
            + ("".join(blocks) or "<p>Nessuna data in questa sala.</p>")
        )
        return layout(f"Cronologia · {era['title']}", body)
    if view in {"img", "doc"}:
        data = gallery(eid, flavor=view)
        title = "Immagini" if view == "img" else "Documenti"
        curated = "".join(
            f'<a class="card" href="/hc/{h(r["id"])}"><h2>{h(r["title"])}</h2><p>{h(r.get("years") or "")}</p></a>'
            for r in data.get("curated") or []
        )
        body = (
            f"<h1>{era['emoji']} {h(era['title'])} · {title}</h1>"
            + _era_nav(eid, view)
            + "<p class='lead'>Archivi pubblici. Ogni pezzo porta fonte, data se c'è, e link originale. "
            "IWM e British Museum, senza API aperta, restano come porte di catalogo.</p>"
            + (f"<h3>Schede WARBOT</h3><div class='grid'>{curated}</div>" if curated else "")
            + _gallery_html(data.get("rows") or [])
        )
        return layout(f"{title} · {era['title']}", body)
    if view != "ov":
        data = list_for(eid, view)
        facet = next((t for k, _e, t in FACETS if k == view), view)
        tiles = "".join(
            f'<a class="card" href="/hc/{h(r["id"])}"><h2>{r.get("emoji", "📖")} {h(r["title"])}</h2>'
            f'<p>{h(r.get("years") or "")}</p></a>'
            for r in data.get("rows") or []
        )
        empty = "<p>Sala ancora magra: apri Documenti o Immagini per gli archivi, o un'altra epoca.</p>"
        body = (
            f"<h1>{era['emoji']} {h(era['title'])} · {h(facet)}</h1>"
            + _era_nav(eid, view)
            + (f"<div class='grid'>{tiles}</div>" if tiles else empty)
        )
        return layout(f"{facet} · {era['title']}", body)
    data = overview(eid, fetch_media=False)
    img = data.get("image") or {}
    thumb = img.get("thumb") or img.get("url") or ""
    hero = (
        f'<p><img src="{h(thumb)}" alt="" style="max-width:100%;border-radius:14px;border:1px solid var(--line)"/></p>'
        if thumb
        else ""
    )
    rooms = "".join(
        f'<a class="card" href="/era/{h(eid)}/{FACET_SLUG[key]}"><h2>{emoji} {h(title)}</h2>'
        f'<p>{(data.get("counts") or {}).get(key, 0)} schede</p></a>'
        for key, emoji, title in FACETS
        if key not in {"img", "doc"}
    )
    rooms += (
        f'<a class="card" href="/era/{h(eid)}/immagini"><h2>📸 Immagini</h2><p>Archivi pubblici.</p></a>'
        f'<a class="card" href="/era/{h(eid)}/documenti"><h2>📜 Documenti</h2><p>Cataloghi e originali.</p></a>'
    )
    body = (
        f"<h1>{era['emoji']} {h(era['title'])}</h1>"
        f"<p class='lead'>📅 {h(era['years'])}</p>"
        + _era_nav(eid, "ov")
        + hero
        + f"<p class='lead'>{h(data.get('essay') or '')}</p>"
        + _source_box(data.get("sources") or [], years=era["years"])
        + f'<div class="grid">{rooms}</div>'
    )
    return layout(era["title"], body)


def render_hc(cid: str) -> str:
    data = entity_card(cid, fetch_media=False)
    if not data:
        return layout("Scheda assente", "<h1>Scheda assente nel database WARBOT</h1><p><a href='/w/epoche'>Epoche</a></p>")
    item = data["item"]
    era = data.get("era") or {}
    rel = "".join(
        f'<a class="card" href="/hc/{h(r["id"])}"><h2>{r.get("emoji", "📖")} {h(r["title"])}</h2><p>{h(r.get("years") or "")}</p></a>'
        for r in data.get("related") or []
    )
    qid = item.get("qid") or ""
    graph = f'<a class="chip" href="/wd/{h(qid)}">Grafo Wikidata {h(qid)}</a>' if qid else ""
    body = (
        f"<h1>{item.get('emoji', '📖')} {h(item['title'])}</h1>"
        f"<p class='lead'>{h(item.get('kind_title') or '')} · {h((era or {}).get('title') or '')} · {h(item.get('years') or '')}</p>"
        + ( _era_nav(era["id"], item.get("kind") or "ov") if era.get("id") else "" )
        + f"<p class='lead'>{h(item.get('summary') or '')}</p>"
        + _source_box(item.get("sources") or [], url=item.get("url") or "", years=item.get("years") or "")
        + f'<p class="meta">{graph}<a class="chip" href="/era/{h(era.get("id") or "")}">Apri l\'epoca</a></p>'
        + (f"<h3>Nella stessa sala</h3><div class='grid'>{rel}</div>" if rel else "")
    )
    return layout(item["title"], body)


def render_wd(qid: str) -> str:
    data = graph_card(qid)
    if not data:
        return layout("Grafo assente", "<h1>Wikidata non ha risposto</h1><p>È solo un collegamento anagrafico. <a href='/w/epoche'>Epoche</a></p>")
    item = data["item"]
    body = (
        f"<h1>🔗 Grafo · {h(item.get('label') or qid)}</h1>"
        f"<p class='lead'>Collegamento Wikidata, non la scheda enciclopedica WARBOT.</p>"
        f"<p class='lead'>{h(item.get('desc') or '')}</p>"
        f'<p class="meta"><a class="chip" href="{h(item.get("url") or "#")}">Apri Wikidata</a>'
        '<a class="chip" href="/w/epoche">🌍 Epoche</a></p>'
    )
    return layout(item.get("label") or qid, body)


def render_viaggia() -> str:
    data = travel(fetch_media=False)
    era = data["era"]
    event = data.get("event") or {}
    people = "".join(
        f'<a class="chip" href="/hc/{h(p["id"])}">{h(p["title"])}</a>' for p in data.get("people") or []
    )
    cid = event.get("id") or ""
    body = (
        "<h1>🎲 Viaggia nel tempo</h1>"
        f"<p class='lead'>🕰️ {h(event.get('years') or event.get('start') or era['start'])} · {era['emoji']} {h(era['title'])}<br>"
        f"⚔️ {h(event.get('title') or era['title'])}</p>"
        + f"<p class='lead'>{h(event.get('summary') or '')}</p>"
        + _source_box(event.get("sources") or [], url=event.get("url") or "", years=event.get("years") or "")
        + f'<p class="meta">{people}</p>'
        + f'<p class="meta"><a class="chip" href="/hc/{h(cid)}">Scheda WARBOT</a> '
        f'<a class="chip" href="/era/{h(era["id"])}">Apri l\'epoca</a> '
        f'<a class="chip" href="/viaggia">Un altro viaggio</a></p>'
    )
    return layout("Viaggia nel tempo", body)


def render_entity(eid: str) -> str:
    item = by_id(eid)
    if not item:
        return layout("Non trovato", "<h1>Scheda assente</h1><p>Torna all'ingresso.</p>")
    fields = "".join(f'<div class="field">{h(k)}: {h(v)}</div>' for k, v in item.get("fields") or ())
    sections = "".join(
        f"<section><h3>{h(title)}</h3><p>{h(body)}</p></section>" for title, body in item.get("sections") or ()
    )
    rel = related_items(item)
    related = ""
    if rel:
        related = "<h3>Collegamenti</h3><div class='grid'>" + "".join(card_tile(r) for r in rel) + "</div>"
    em, kind = KIND_LABELS.get(item["kind"], ("📄", item["kind"]))
    body = f"""
      <h1>{item['emoji']} {h(item['title'])}</h1>
      <p class="lead">{h(em + ' ' + kind)}{(' · ' + h(item['subtitle'])) if item.get('subtitle') else ''}</p>
      <p class="lead">{h(item['summary'])}</p>
      <div class="meta">{fields}</div>
      {sections}
      {related}
      <p class="meta"><a class="chip" href="/w/{h(item['world'])}">← {h(WORLDS[item['world']]['title'])}</a></p>
    """
    return layout(item["title"], body)


def render_list(kind: str, filt: str) -> str:
    kind_map = {
        "war": "war", "bat": "battle", "role": "role", "rank": "rank", "army": "army",
        "gear": "gear", "vehicle": "vehicle", "fort": "fort", "doc": "doc",
        "peace": "peace", "person": "person", "idea": "idea",
    }
    real = kind_map.get(kind, kind)
    if real == "war" and filt in ERA_LABELS:
        rows = by_era(filt)
        title = ERA_LABELS[filt][1]
    elif real == "battle" and filt in ERA_LABELS:
        rows = [item for item in by_kind("battle") if item.get("era") == filt]
        title = f"Battaglie · {ERA_LABELS[filt][1]}"
    else:
        rows = by_kind(real)
        title = KIND_LABELS.get(real, ("📄", real))[1]
    tiles = "".join(card_tile(item) for item in rows)
    body = f"<h1>{h(title)}</h1><div class='grid'>{tiles}</div>"
    return layout(title, body)


def render_cerca(q: str) -> str:
    form = """
    <h1>🔍 Cerca</h1>
    <form action="/cerca" method="get">
      <input type="search" name="q" placeholder="Stalingrado, Waterloo, Maginot…" value="{value}"/>
      <button>Cerca</button>
    </form>
    """.format(value=h(q))
    if not q:
        return layout("Cerca", form + telegramish(cerca_text()))
    rows = search(q)
    hist = search_cards(q)
    tiles = "".join(card_tile(item) for item in rows)
    hist_tiles = "".join(
        f'<a class="card" href="/hc/{h(r["id"])}"><h2>{r.get("emoji", "📖")} {h(r["title"])}</h2><p>{h(r.get("years") or "EPOCHE")}</p></a>'
        for r in hist
    )
    if not tiles and not hist_tiles:
        tiles = "<p>Nessuna scheda.</p>"
    extra = f"<h3>Database EPOCHE</h3><div class='grid'>{hist_tiles}</div>" if hist_tiles else ""
    body = form + telegramish(format_search(q, rows).replace("<b>", "").replace("</b>", "")) + f"<div class='grid'>{tiles}</div>" + extra
    return layout(f"Cerca · {q}", body)


_QUIZ: dict[str, dict] = {}


def render_quiz(mode: str | None, pick: str | None, sid: str | None) -> str:
    modes = [
        ("war", "🧠 Guerra"), ("bat", "🗺️ Battaglia"), ("rank", "🎖️ Grado"),
        ("veh", "🚁 Mezzo"), ("nat", "🏳️ Nazione"), ("per", "👤 Personaggio"),
        ("trt", "📜 Trattato"), ("year", "📅 Anno"), ("tf", "⚔️ Vero o falso"), ("10", "🎯 10 domande"),
    ]
    hub = "<h1>🎲 Quiz storico</h1>" + telegramish(quiz_hub_text())
    hub += '<div class="grid">' + "".join(f'<a class="card" href="/quiz?mode={m}"><h2>{lab}</h2></a>' for m, lab in modes) + "</div>"
    if not mode:
        return layout("Quiz", hub)
    if pick is None:
        quiz = build_quiz(mode)
        if not quiz:
            return layout("Quiz", hub)
        token = f"{random.randint(1, 10**9)}"
        _QUIZ[token] = quiz
        opts = "".join(
            f'<a class="btn" style="background:var(--panel);color:var(--ink);border:1px solid var(--line)" '
            f'href="/quiz?mode={h(mode)}&sid={token}&i={i}">{h("ABCD"[i])} · {h(opt)}</a>'
            for i, opt in enumerate(quiz["options"])
        )
        body = f"<h1>{h(quiz['title'])}</h1><p class='lead'>{quiz['prompt']}</p><div class='opts'>{opts}</div>"
        return layout("Quiz", body)
    quiz = _QUIZ.get(sid or "")
    if not quiz:
        return layout("Quiz", "<p>Domanda scaduta.</p><p><a href='/quiz'>Ricomincia</a></p>")
    i = int(pick)
    opt = quiz["options"][i] if 0 <= i < len(quiz["options"]) else ""
    ok = opt == quiz["answer"]
    cls = "ok" if ok else "ko"
    msg = "Giusto." if ok else f"Era: {quiz['answer']}"
    eid = quiz.get("explain")
    more = f'<p><a class="chip" href="/e/{h(eid)}">📖 Scheda</a> <a class="chip" href="/quiz?mode={h(mode)}">➡️ Prossima</a></p>'
    body = f"<h1 class='{cls}'>{h(msg)}</h1>{more}<p><a href='/quiz'>Tutti i quiz</a></p>"
    return layout("Quiz", body)


LEAFLET_HEAD = """
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
  integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>
"""


def _ago(ts: float | None) -> str:
    if not ts:
        return ""
    delta = max(0, int(time.time() - ts))
    if delta < 5:
        return "adesso"
    if delta < 60:
        return f"{delta} s fa"
    return f"{delta // 60} min fa"


def _live_tabs(active: str, region: str = "it") -> str:
    links = [
        ("hub", "/live", "📡 Hub"),
        ("ac", f"/live/ac?r={h(region)}", "✈️ Aerei"),
        ("heli", f"/live/heli?r={h(region)}", "🚁 Elicotteri"),
        ("navi", "/live/navi", "⚓ Navi"),
        ("iss", "/live/iss", "🛰️ ISS"),
        ("json", f"/live.json?kind={h(active if active != 'hub' else 'all')}&r={h(region)}", "JSON"),
    ]
    chips = []
    for key, href, label in links:
        style = "border-color:var(--brass)" if key == active else ""
        chips.append(f'<a class="chip" href="{href}" style="{style}">{label}</a>')
    return f'<div class="tabs">{"".join(chips)}</div>'


def _region_tabs(kind: str, region: str) -> str:
    chips = []
    for key, cfg in REGIONS.items():
        href = f"/live/{kind}?r={key}"
        style = "border-color:var(--brass)" if key == region else ""
        chips.append(f'<a class="chip" href="{href}" style="{style}">{cfg["emoji"]} {h(cfg["title"])}</a>')
    return f'<p class="meta">{"".join(chips)}</p>'


def _leaflet(points: list[dict], center: tuple[float, float], zoom: int) -> str:
    payload = json.dumps(points, ensure_ascii=False).replace("<", "\\u003c")
    colors = {"ac": "#c4a35a", "heli": "#6b7f4a", "ship": "#6a8caf", "iss": "#c45a5a"}
    return f"""
<div id="map" role="img" aria-label="Mappa delle posizioni live"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
  integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
<script>
(function () {{
  const POINTS = {payload};
  const COLORS = {json.dumps(colors)};
  const map = L.map("map").setView([{center[0]}, {center[1]}], {zoom});
  L.tileLayer("https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
    maxZoom: 12,
    attribution: "&copy; OpenStreetMap"
  }}).addTo(map);
  const layer = L.featureGroup();
  POINTS.forEach(function (p) {{
    const marker = L.circleMarker([p.lat, p.lon], {{
      radius: p.kind === "iss" ? 9 : 5,
      color: COLORS[p.kind] || "#c4a35a",
      weight: 1,
      fillOpacity: 0.85
    }});
    marker.bindPopup(p.label);
    layer.addLayer(marker);
  }});
  if (POINTS.length) {{
    layer.addTo(map);
    if (POINTS.length > 1) map.fitBounds(layer.getBounds().pad(0.18));
  }}
}})();
</script>
"""


def render_live_hub() -> str:
    snap = fetch_hub()
    iss = snap.get("iss") or {}
    ac = snap.get("ac") or {}
    ships = snap.get("ships") or {}
    points: list[dict] = []
    if iss.get("ok"):
        place = iss.get("place") or "ISS"
        points.append(
            {
                "lat": iss["lat"],
                "lon": iss["lon"],
                "kind": "iss",
                "label": (
                    f"<b>ISS</b><br>{html.escape(str(place))}<br>"
                    f"{(iss.get('alt_km') or 0):.0f} km · {(iss.get('vel_kmh') or 0):.0f} km/h"
                ),
            }
        )
    airborne = [r for r in (ac.get("rows") or []) if not r.get("on_ground")][:50]
    for r in airborne:
        points.append(
            {
                "lat": r["lat"],
                "lon": r["lon"],
                "kind": "heli" if r.get("heli") else "ac",
                "label": (
                    f"<b>{html.escape(r['flight'])}</b><br>{html.escape(r['desc'])}<br>"
                    f"{int(r['alt_ft'] or 0)} ft"
                ),
            }
        )
    if iss.get("ok"):
        center = (iss["lat"], iss["lon"])
        zoom = 3
    elif airborne:
        center = (airborne[0]["lat"], airborne[0]["lon"])
        zoom = 5
    else:
        cfg = REGIONS["it"]
        center = (cfg["lat"], cfg["lon"])
        zoom = 5
    map_html = _leaflet(points, center, zoom) if points else "<p>Nessun punto da mettere in mappa in questo istante.</p>"

    iss_line = "ISS non raggiungibile"
    if iss.get("ok"):
        iss_line = (
            f"{iss['lat']:.2f}, {iss['lon']:.2f} · {(iss.get('alt_km') or 0):.0f} km · "
            f"{html.escape(str(iss.get('place') or ''))}"
        )
    ac_line = "feed ADS-B assente"
    if ac.get("ok"):
        ac_line = f"{ac.get('airborne', 0)} in volo su {ac.get('total', 0)} tracciati in Italia"
    ships_line = "AIS assente"
    if ships.get("ok"):
        ships_line = f"{ships.get('moving', 0)} in moto su {ships.get('total', 0)} nel Baltico"

    stats = f"""
    <div class="grid">
      <a class="card" href="/live/iss"><h2>🛰️ ISS</h2><p>{h(iss_line)}</p></a>
      <a class="card" href="/live/ac?r=it"><h2>✈️ Aerei</h2><p>{h(ac_line)}</p></a>
      <a class="card" href="/live/navi"><h2>⚓ Navi</h2><p>{h(ships_line)}</p></a>
    </div>
    """
    cards = """
    <div class="grid">
      <a class="card" href="/live/ac?r=it"><h2>✈️ Aerei per zona</h2><p>Italia, Mediterraneo, Europa, Manica, costa est USA, Giappone.</p></a>
      <a class="card" href="/live/heli?r=it"><h2>🚁 Elicotteri</h2><p>Stesso ADS-B, solo categoria eli.</p></a>
      <a class="card" href="/live/navi"><h2>⚓ Elenco navi</h2><p>AIS aperto del Baltico finlandese, con destinazione e velocità.</p></a>
      <a class="card" href="/live/iss"><h2>🛰️ Scheda ISS</h2><p>Quota, velocità, luce o ombra, mappa a tutta pagina.</p></a>
    </div>
    """
    iss_map = ""
    if iss.get("ok"):
        iss_map = f'<p class="meta"><a class="chip" href="{h(iss["map"])}">Apri ISS su OpenStreetMap</a></p>'
    body = (
        "<h1>📡 Posizioni live</h1>"
        "<p class='lead'>Coordinate vere, adesso. Aerei da ADS-B pubblico, navi da AIS finlandese, "
        "ISS da wheretheiss.at. Non è un radar militare.</p>"
        + _live_tabs("hub")
        + stats
        + map_html
        + iss_map
        + cards
        + f'<p class="lead">{h(LIVE_NOTE)}</p>'
        + '<p class="meta"><a class="chip" href="/live">🔄 Aggiorna</a> '
        '<a class="chip" href="/live.json">JSON</a></p>'
    )
    return layout("Posizioni live", body, extra_head=LEAFLET_HEAD)


def render_live_aircraft(region: str, *, heli: bool = False) -> str:
    region = region if region in REGIONS else "it"
    bundle = fetch_aircraft(region)
    kind = "heli" if heli else "ac"
    title = "Elicotteri" if heli else "Aerei"
    cfg = REGIONS[region]
    if not bundle.get("ok"):
        body = (
            f"<h1>{'🚁' if heli else '✈️'} {h(title)}</h1>"
            + _live_tabs(kind, region)
            + _region_tabs(kind, region)
            + f"<p>Il feed ADS-B non ha risposto: {h(bundle.get('error') or 'timeout')}</p>"
            + f'<p><a class="chip" href="/live/{kind}?r={h(region)}">Riprova</a></p>'
        )
        return layout(title, body)
    rows = [r for r in bundle.get("rows") or [] if (r["heli"] if heli else True)]
    airborne = [r for r in rows if not r["on_ground"]]
    shown = airborne[:80] or rows[:80]
    points = [
        {
            "lat": r["lat"],
            "lon": r["lon"],
            "kind": "heli" if r["heli"] else "ac",
            "label": (
                f"<b>{html.escape(r['flight'])}</b><br>"
                f"{html.escape(r['desc'])}<br>"
                f"{'al suolo' if r['on_ground'] else str(int(r['alt_ft'] or 0)) + ' ft'}"
                f" · {int(r['gs_kt'] or 0)} kt"
            ),
        }
        for r in shown
    ]
    table_rows = []
    for r in shown[:40]:
        alt = "suolo" if r["on_ground"] else f"{int(r['alt_ft'] or 0)} ft"
        spd = f"{int(r['gs_kt'] or 0)} kt" if r["gs_kt"] else "—"
        icon = "🚁" if r["heli"] else "✈️"
        table_rows.append(
            "<tr>"
            f"<td>{icon} <b>{h(r['flight'])}</b></td>"
            f"<td>{h(r['desc'])}</td>"
            f"<td>{h(alt)}</td>"
            f"<td>{h(spd)}</td>"
            f"<td>{r['lat']:.2f}, {r['lon']:.2f}</td>"
            f"<td><a href='{h(r['map'])}'>mappa</a></td>"
            "</tr>"
        )
    table = (
        "<table class='live-table'><thead><tr>"
        "<th>Volo</th><th>Tipo</th><th>Quota</th><th>Velocità</th><th>Posizione</th><th></th>"
        "</tr></thead><tbody>"
        + "".join(table_rows)
        + "</tbody></table>"
        if shown
        else "<p>Nessun contatto in questa finestra.</p>"
    )
    map_html = _leaflet(points, (cfg["lat"], cfg["lon"]), 6) if points else ""
    body = (
        f"<h1>{cfg['emoji']} {h(title)} · {h(cfg['title'])}</h1>"
        + _live_tabs(kind, region)
        + _region_tabs(kind, region)
        + (
            f"<p class='lead'>In zona: {bundle.get('total', 0)} tracciati, "
            f"{bundle.get('airborne', 0)} in volo, {bundle.get('heli', 0)} eli. "
            f"Fonte: {h(bundle.get('source'))}. Aggiornato {_ago(bundle.get('ts'))}.</p>"
        )
        + f'<p class="meta"><a class="chip" href="/live/{kind}?r={h(region)}">🔄 Aggiorna</a> '
        f'<a class="chip" href="/live.json?kind={kind}&r={h(region)}">JSON</a></p>'
        + map_html
        + table
        + f'<p class="lead">{h(LIVE_NOTE)}</p>'
    )
    return layout(f"{title} · {cfg['title']}", body, extra_head=LEAFLET_HEAD)


def render_live_ships() -> str:
    bundle = fetch_ships()
    if not bundle.get("ok"):
        body = (
            "<h1>⚓ Navi</h1>"
            + _live_tabs("navi")
            + f"<p>Il feed AIS non ha risposto: {h(bundle.get('error') or 'timeout')}</p>"
            + '<p><a class="chip" href="/live/navi">Riprova</a></p>'
            + "<p>Il feed aperto copre le acque finlandesi (Digitraffic). Non è un AIS mondiale.</p>"
        )
        return layout("Navi", body)
    rows = (bundle.get("rows") or [])[:200]
    shown = rows[:40]
    points = [
        {
            "lat": r["lat"],
            "lon": r["lon"],
            "kind": "ship",
            "label": (
                f"<b>{html.escape(r['name'])}</b><br>"
                f"{html.escape(r['kind'])}"
                + (f"<br>→ {html.escape(r['dest'])}" if r.get("dest") else "")
                + f"<br>{(r['sog_kn'] or 0):.1f} kn"
            ),
        }
        for r in rows
    ]
    table_rows = []
    for r in shown:
        spd = f"{r['sog_kn']:.1f} kn" if r.get("sog_kn") is not None else "—"
        dest = h(r["dest"]) if r.get("dest") else "—"
        table_rows.append(
            "<tr>"
            f"<td>🚢 <b>{h(r['name'])}</b></td>"
            f"<td>{h(r['kind'])}</td>"
            f"<td>{dest}</td>"
            f"<td>{h(spd)}</td>"
            f"<td>{r['lat']:.2f}, {r['lon']:.2f}</td>"
            f"<td><a href='{h(r['map'])}'>mappa</a></td>"
            "</tr>"
        )
    table = (
        "<table class='live-table'><thead><tr>"
        "<th>Nave</th><th>Tipo AIS</th><th>Destinazione</th><th>Velocità</th><th>Posizione</th><th></th>"
        "</tr></thead><tbody>"
        + "".join(table_rows)
        + "</tbody></table>"
    )
    center = (rows[0]["lat"], rows[0]["lon"]) if rows else (61.5, 21.5)
    map_html = _leaflet(points, center, 5) if points else ""
    body = (
        "<h1>⚓ Navi live</h1>"
        + _live_tabs("navi")
        + (
            f"<p class='lead'>{h(bundle.get('title'))}. Contatti: {bundle.get('total', 0)} · "
            f"in moto: {bundle.get('moving', 0)}. Fonte: {h(bundle.get('source'))}. "
            f"Aggiornato {_ago(bundle.get('ts'))}.</p>"
        )
        + '<p class="meta"><a class="chip" href="/live/navi">🔄 Aggiorna</a> '
        '<a class="chip" href="/live.json?kind=ships">JSON</a></p>'
        + map_html
        + (table if shown else "<p>Nessuna nave in questo istante.</p>")
        + f'<p class="lead">{h(LIVE_NOTE)}</p>'
        + "<p>Non esiste un AIS mondiale gratis e stabile senza chiave: "
        "qui c'è un mare vero, in diretta, da un ente pubblico.</p>"
    )
    return layout("Navi", body, extra_head=LEAFLET_HEAD)


def render_live_iss() -> str:
    bundle = fetch_iss()
    if not bundle.get("ok"):
        body = (
            "<h1>🛰️ ISS</h1>"
            + _live_tabs("iss")
            + f"<p>Non riesco a interrogare la stazione: {h(bundle.get('error') or '')}</p>"
            + '<p><a class="chip" href="/live/iss">Riprova</a></p>'
        )
        return layout("ISS", body)
    vis = {"daylight": "al sole", "eclipsed": "in ombra", "visible": "visibile"}.get(
        bundle.get("visibility") or "", bundle.get("visibility") or "—"
    )
    place = bundle.get("place") or "posizione non etichettata"
    points = [
        {
            "lat": bundle["lat"],
            "lon": bundle["lon"],
            "kind": "iss",
            "label": (
                f"<b>ISS</b><br>{html.escape(place)}<br>"
                f"{(bundle.get('alt_km') or 0):.0f} km · {(bundle.get('vel_kmh') or 0):.0f} km/h"
            ),
        }
    ]
    body = (
        "<h1>🛰️ Stazione spaziale internazionale</h1>"
        + _live_tabs("iss")
        + (
            f"<p class='lead'>📍 {bundle['lat']:.2f}, {bundle['lon']:.2f} · {h(place)}<br>"
            f"📏 {bundle.get('alt_km') or 0:.0f} km · 💨 {bundle.get('vel_kmh') or 0:.0f} km/h · ☀️ {h(vis)}<br>"
            f"Fonte: {h(bundle.get('source'))}. Aggiornato {_ago(bundle.get('ts'))}.</p>"
        )
        + '<p class="meta"><a class="chip" href="/live/iss">🔄 Aggiorna</a> '
        '<a class="chip" href="/live.json?kind=iss">JSON</a> '
        f'<a class="chip" href="{h(bundle["map"])}">OpenStreetMap</a></p>'
        + _leaflet(points, (bundle["lat"], bundle["lon"]), 3)
        + f'<p class="lead">{h(LIVE_NOTE)}</p>'
    )
    return layout("ISS", body, extra_head=LEAFLET_HEAD)


def live_payload(kind: str, region: str) -> dict:
    region = region if region in REGIONS else "it"
    if kind in {"ac", "aircraft", "aerei"}:
        return fetch_aircraft(region)
    if kind in {"heli", "elicotteri"}:
        bundle = fetch_aircraft(region)
        if bundle.get("ok"):
            rows = [r for r in bundle.get("rows") or [] if r.get("heli")]
            bundle = dict(bundle)
            bundle["rows"] = rows
            bundle["filter"] = "heli"
        return bundle
    if kind in {"ships", "navi"}:
        return fetch_ships()
    if kind == "iss":
        return fetch_iss()
    snap = fetch_hub(region)
    ac = snap.get("ac") or {}
    ships = snap.get("ships") or {}
    iss = snap.get("iss") or {}
    if ac.get("ok"):
        ac = dict(ac)
        ac["rows"] = (ac.get("rows") or [])[:40]
    if ships.get("ok"):
        ships = dict(ships)
        ships["rows"] = (ships.get("rows") or [])[:40]
    return {"aircraft": ac, "ships": ships, "iss": iss, "note": LIVE_NOTE}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:
        print("[museum]", fmt % args)

    def _send(self, body: str, status: int = 200, *, content_type: str = "text/html; charset=utf-8") -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path).rstrip("/") or "/"
        qs = parse_qs(parsed.query)
        try:
            if path == "/":
                page = render_home()
            elif path == "/esplora":
                tiles = "".join(
                    f'<a class="card" href="/w/{key}"><h2>{m["emoji"]} {h(m["title"])}</h2><p>{h(m["blurb"])}</p></a>'
                    for key, m in WORLDS.items()
                )
                page = layout("Esplora", "<h1>🧭 Esplora</h1>" + telegramish(esplora_text()) + f"<div class='grid'>{tiles}</div>")
            elif path == "/aiuto":
                page = layout("Aiuto", "<h1>Aiuto</h1>" + telegramish(help_text()))
            elif path == "/oggi":
                page = render_entity(of_the_day()["id"])
            elif path == "/casuale":
                page = render_entity(random_item()["id"])
            elif path == "/cerca":
                page = render_cerca((qs.get("q") or [""])[0])
            elif path == "/quiz":
                page = render_quiz((qs.get("mode") or [None])[0], (qs.get("i") or [None])[0], (qs.get("sid") or [None])[0])
            elif path == "/live.json":
                kind = (qs.get("kind") or ["all"])[0]
                region = (qs.get("r") or ["it"])[0]
                payload = json.dumps(live_payload(kind, region), ensure_ascii=False, default=str)
                self._send(payload, content_type="application/json; charset=utf-8")
                return
            elif path == "/live":
                page = render_live_hub()
            elif path == "/live/ac":
                page = render_live_aircraft((qs.get("r") or ["it"])[0])
            elif path == "/live/heli":
                page = render_live_aircraft((qs.get("r") or ["it"])[0], heli=True)
            elif path == "/live/navi":
                page = render_live_ships()
            elif path == "/live/iss":
                page = render_live_iss()
            elif path == "/viaggia":
                page = render_viaggia()
            elif path.startswith("/era/"):
                parts = [p for p in path.split("/") if p]
                eid = parts[1] if len(parts) > 1 else ""
                view = parts[2] if len(parts) > 2 else "ov"
                page = render_era(eid, SLUG_FACET.get(view, view if view in {k for k, _e, _t in FACETS} else "ov"))
            elif path.startswith("/hc/"):
                page = render_hc(path.split("/", 2)[-1])
            elif path.startswith("/wd/"):
                page = render_wd(path.split("/", 2)[-1])
            elif path.startswith("/w/"):
                key = path.split("/", 2)[-1]
                if key not in WORLDS:
                    page = layout("Mondo assente", "<h1>Mondo non in mappa</h1>")
                else:
                    page = render_world(key)
            elif path.startswith("/e/"):
                page = render_entity(path.split("/", 2)[-1])
            elif path.startswith("/l/"):
                parts = path.split("/")
                page = render_list(parts[2] if len(parts) > 2 else "war", parts[3] if len(parts) > 3 else "all")
            else:
                page = layout("404", "<h1>Sala vuota</h1><p><a href='/'>Ingresso</a></p>")
                self._send(page, 404)
                return
            self._send(page)
        except Exception as exc:  # noqa: BLE001
            self._send(layout("Errore", f"<h1>Il museo ha inciampato</h1><p>{h(exc)}</p>"), 500)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"WARBOT museo web su http://127.0.0.1:{PORT}  ({len(ALL)} schede)")
    server.serve_forever()


if __name__ == "__main__":
    main()
