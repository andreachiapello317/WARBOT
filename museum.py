#!/usr/bin/env python3
"""Museo web di WARBOT: gli stessi sei mondi del bot Telegram, da sfogliare nel browser."""

from __future__ import annotations

import html
import random
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
      </nav>
    </header>"""


def layout(title: str, body: str, *, lead: str = "") -> str:
    return f"""<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{h(title)} · WARBOT</title>
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
    .ok {{ color:#b6d48a; }}
    .ko {{ color:#e7a2a2; }}
    @media (max-width:640px) {{
      .top {{ padding:12px; }}
      .brand {{ width:100%; }}
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
      <a class="card" href="/oggi"><h2>📖 Oggi</h2><p>La scheda del giorno, come COSMICO ma da museo.</p></a>
      <a class="card" href="/casuale"><h2>🎲 Casuale</h2><p>Un cassetto a caso.</p></a>
      <a class="card" href="/cerca"><h2>🔍 Cerca</h2><p>Scrivi Stalingrado e vedi i ponti.</p></a>
      <a class="card" href="/quiz"><h2>🎲 Quiz</h2><p>Dieci modi per mettere alla prova il catalogo.</p></a>
    </div>"""
    body = f"{telegramish(home_text())}<div class='grid'>{worlds}</div>{extras}"
    return layout("Museo", body)


def render_world(key: str) -> str:
    meta = WORLDS[key]
    rows = [item for item in ALL if item["world"] == key]
    filters = ""
    if key == "epoche":
        filters = "".join(
            f'<a class="chip" href="/l/war/{era}">{em} {name}</a>' for era, (em, name) in ERA_LABELS.items()
        )
        filters = f'<p class="meta">{filters}</p>'
    tiles = "".join(card_tile(item) for item in rows)
    body = f"<h1>{meta['emoji']} {h(meta['title'])}</h1>{telegramish(world_text(key))}{filters}<div class='grid'>{tiles}</div>"
    return layout(meta["title"], body)


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
    tiles = "".join(card_tile(item) for item in rows) or "<p>Nessuna scheda.</p>"
    body = form + telegramish(format_search(q, rows).replace("<b>", "").replace("</b>", "")) + f"<div class='grid'>{tiles}</div>"
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


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:
        print("[museum]", fmt % args)

    def _send(self, body: str, status: int = 200) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
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
