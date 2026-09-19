#!/usr/bin/env python3
"""Mappa web di WARBOT: le stesse posizioni live del bot Telegram."""

from __future__ import annotations

import html
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from services.live import (
    LIVE_NOTE,
    REGIONS,
    fetch_aircraft,
    fetch_hub,
    fetch_iss,
    fetch_ships,
)

HOST = "0.0.0.0"
PORT = 47261


def h(text: object) -> str:
    return html.escape(str(text), quote=True)


def nav(active: str = "hub") -> str:
    links = [
        ("hub", "/", "📡 Hub"),
        ("ac", "/live/ac", "✈️ Aerei"),
        ("heli", "/live/heli", "🚁 Elicotteri"),
        ("navi", "/live/navi", "⚓ Navi"),
        ("iss", "/live/iss", "🛰️ ISS"),
        ("aiuto", "/aiuto", "❓ Aiuto"),
    ]
    chips = []
    for key, href, label in links:
        style = "border-color:var(--brass)" if key == active else ""
        chips.append(f'<a class="chip" href="{href}" style="{style}">{label}</a>')
    return f"""
    <header class="top">
      <a class="brand" href="/">📡 WARBOT live</a>
      <nav>{"".join(chips)}</nav>
    </header>"""


def layout(title: str, body: str, *, extra_head: str = "", extra_script: str = "", active: str = "hub") -> str:
    return f"""<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{h(title)} · WARBOT live</title>
  {extra_head}
  <style>
    :root {{
      --bg:#0e1210; --panel:#171d19; --ink:#e8e0c8; --muted:#b7aa8a;
      --brass:#c4a35a; --line:#3a3f32; --olive:#6b7f4a; --red:#8c2f2f;
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0; font-family:"Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif;
      background:
        radial-gradient(1100px 480px at 12% -12%, #24301c 0%, transparent 52%),
        var(--bg);
      color:var(--ink); min-height:100vh;
    }}
    a {{ color:var(--brass); text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    .top {{
      display:flex; flex-wrap:wrap; gap:12px 18px; align-items:center;
      justify-content:space-between; padding:18px 22px;
      border-bottom:1px solid var(--line); background:#121610cc; backdrop-filter:blur(8px);
      position:sticky; top:0; z-index:2;
    }}
    .brand {{ font-size:1.25rem; letter-spacing:.08em; color:var(--ink); font-weight:700; }}
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
      border-radius:14px; min-height:120px; display:flex; flex-direction:column; gap:8px;
    }}
    .card:hover {{ border-color:var(--brass); }}
    .card h2 {{ margin:0; font-size:1.25rem; }}
    .card p {{ margin:0; color:var(--muted); line-height:1.45; }}
    .meta {{ display:flex; flex-wrap:wrap; gap:8px 14px; color:var(--muted); margin:16px 0; }}
    .note {{ margin-top:28px; font-size:.92rem; color:var(--muted); border-top:1px solid var(--line); padding-top:14px; }}
    .empty {{
      margin-top:18px; padding:18px; border:1px dashed var(--line);
      border-radius:12px; color:var(--muted);
    }}
    .err {{ color:#e7a2a2; }}
    #map {{
      height:min(62vh, 520px); margin:18px 0; border-radius:14px;
      border:1px solid var(--line); background:#0e100c;
    }}
    .live-table {{ width:100%; border-collapse:collapse; margin-top:12px; font-size:.95rem; }}
    .live-table th, .live-table td {{
      text-align:left; padding:8px 6px; border-bottom:1px solid var(--line); vertical-align:top;
    }}
    .live-table th {{ color:var(--brass); font-size:.82rem; letter-spacing:.04em; text-transform:uppercase; }}
    @media (max-width:640px) {{
      .top {{ padding:12px; }}
      .brand {{ width:100%; }}
      .live-table {{ font-size:.85rem; }}
    }}
  </style>
</head>
<body>
  {nav(active)}
  <main class="wrap">
    {body}
    <p class="note">{h(LIVE_NOTE)}</p>
  </main>
  {extra_script}
</body>
</html>"""


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
        ("hub", "/", "📡 Hub"),
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
    map_html = _leaflet(points, center, zoom) if points else '<p class="empty">Nessun punto da mettere in mappa in questo istante.</p>'

    iss_line = "ISS non raggiungibile"
    if iss.get("ok"):
        iss_line = (
            f"{iss['lat']:.2f}, {iss['lon']:.2f} · {(iss.get('alt_km') or 0):.0f} km · "
            f"{html.escape(str(iss.get('place') or ''))}"
        )
    ac_line = "feed ADS-B assente"
    if ac.get("ok"):
        ac_line = f"{ac.get('airborne', 0)} in volo su {ac.get('total', 0)} tracciati in Italia"
    elif ac.get("error"):
        ac_line = f"feed ADS-B: {ac.get('error')}"
    ships_line = "AIS assente"
    if ships.get("ok"):
        ships_line = f"{ships.get('moving', 0)} in moto su {ships.get('total', 0)} nel Baltico"
    elif ships.get("error"):
        ships_line = f"AIS: {ships.get('error')}"

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
        "ISS da wheretheiss.at.</p>"
        + _live_tabs("hub")
        + stats
        + map_html
        + iss_map
        + cards
        + '<p class="meta"><a class="chip" href="/">🔄 Aggiorna</a> '
        '<a class="chip" href="/live.json">JSON</a></p>'
    )
    return layout("Posizioni live", body, extra_head=LEAFLET_HEAD, active="hub")


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
            + f'<p class="empty err">Il feed ADS-B non ha risposto: {h(bundle.get("error") or "timeout")}</p>'
            + f'<p class="meta"><a class="chip" href="/live/{kind}?r={h(region)}">Riprova</a></p>'
        )
        return layout(title, body, active=kind)
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
        else '<p class="empty">Nessun contatto in questa finestra. Cambia zona o riprova tra qualche secondo.</p>'
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
    )
    return layout(f"{title} · {cfg['title']}", body, extra_head=LEAFLET_HEAD, active=kind)


def render_live_ships() -> str:
    bundle = fetch_ships()
    if not bundle.get("ok"):
        body = (
            "<h1>⚓ Navi</h1>"
            + _live_tabs("navi")
            + f'<p class="empty err">Il feed AIS non ha risposto: {h(bundle.get("error") or "timeout")}</p>'
            + '<p class="meta"><a class="chip" href="/live/navi">Riprova</a></p>'
            + "<p class='lead'>Il feed aperto copre le acque finlandesi (Digitraffic). Non è un AIS mondiale.</p>"
        )
        return layout("Navi", body, active="navi")
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
        if shown
        else '<p class="empty">Nessuna nave in questo istante.</p>'
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
        + table
        + "<p class='lead'>Non esiste un AIS mondiale gratis e stabile senza chiave: "
        "qui c'è un mare vero, in diretta, da un ente pubblico.</p>"
    )
    return layout("Navi", body, extra_head=LEAFLET_HEAD, active="navi")


def render_live_iss() -> str:
    bundle = fetch_iss()
    if not bundle.get("ok"):
        body = (
            "<h1>🛰️ ISS</h1>"
            + _live_tabs("iss")
            + f'<p class="empty err">Non riesco a interrogare la stazione: {h(bundle.get("error") or "")}</p>'
            + '<p class="meta"><a class="chip" href="/live/iss">Riprova</a></p>'
        )
        return layout("ISS", body, active="iss")
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
    )
    return layout("ISS", body, extra_head=LEAFLET_HEAD, active="iss")


def render_help() -> str:
    body = """
    <h1>❓ Come funziona</h1>
    <p class="lead">WARBOT mostra solo posizioni live da radio pubbliche. I mondi enciclopedici non ci sono più.</p>
    <div class="grid">
      <div class="card"><h2>✈️ Aerei</h2><p>ADS-B da adsb.fi. Zone: Italia, Mediterraneo, Europa, Manica, costa est USA, Giappone. Raggio massimo 250 nm.</p></div>
      <div class="card"><h2>⚓ Navi</h2><p>AIS aperto Digitraffic (Finlandia). Copre il Baltico, non il mondo.</p></div>
      <div class="card"><h2>🛰️ ISS</h2><p>Coordinate da wheretheiss.at: quota, velocità, luce o ombra.</p></div>
    </div>
    <p class="lead">Su Telegram: /start /live /aerei /elicotteri /navi /iss /aiuto</p>
    """
    return layout("Aiuto", body, active="aiuto")


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
            if path in {"/", "/live"}:
                page = render_live_hub()
            elif path == "/aiuto":
                page = render_help()
            elif path == "/live.json":
                kind = (qs.get("kind") or ["all"])[0]
                region = (qs.get("r") or ["it"])[0]
                payload = json.dumps(live_payload(kind, region), ensure_ascii=False, default=str)
                self._send(payload, content_type="application/json; charset=utf-8")
                return
            elif path == "/live/ac":
                page = render_live_aircraft((qs.get("r") or ["it"])[0])
            elif path == "/live/heli":
                page = render_live_aircraft((qs.get("r") or ["it"])[0], heli=True)
            elif path == "/live/navi":
                page = render_live_ships()
            elif path == "/live/iss":
                page = render_live_iss()
            else:
                page = layout(
                    "404",
                    "<h1>Niente qui</h1><p>I mondi del museo non ci sono più. <a href='/'>Torna alle posizioni live</a>.</p>",
                    active="hub",
                )
                self._send(page, 404)
                return
            self._send(page)
        except Exception as exc:  # noqa: BLE001
            self._send(
                layout("Errore", f'<h1>Il live ha inciampato</h1><p class="err">{h(exc)}</p><p><a href="/">Riprova</a></p>'),
                500,
            )


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"WARBOT live su http://127.0.0.1:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
