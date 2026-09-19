#!/usr/bin/env python3
"""Mappa web OSM WORLD: stessa ricerca e categorie del bot Telegram."""

from __future__ import annotations

import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlencode, urlparse

from services.live.geocode import geocode
from services.live.osm import CATEGORIES, OSM_NOTE, WORLD_CATEGORIES, osm_url, search

HOST = "0.0.0.0"
PORT = 47261
LEAFLET_HEAD = """
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
  integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>
"""


def h(text: object) -> str:
    return html.escape(str(text), quote=True)


def layout(title: str, body: str, *, extra_head: str = "") -> str:
    return f"""<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{h(title)} · OSM WORLD</title>
  {extra_head}
  <style>
    :root {{
      --bg:#0e1210; --panel:#171d19; --ink:#e8e0c8; --muted:#b7aa8a;
      --brass:#c4a35a; --line:#3a3f32;
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0; font-family:"Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif;
      background: radial-gradient(1100px 480px at 12% -12%, #24301c 0%, transparent 52%), var(--bg);
      color:var(--ink); min-height:100vh;
    }}
    a {{ color:var(--brass); text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    .top {{
      display:flex; flex-wrap:wrap; gap:12px 18px; align-items:center;
      justify-content:space-between; padding:18px 22px;
      border-bottom:1px solid var(--line); background:#121610cc; position:sticky; top:0; z-index:2;
    }}
    .brand {{ font-size:1.25rem; letter-spacing:.08em; color:var(--ink); font-weight:700; }}
    .wrap {{ max-width:980px; margin:0 auto; padding:28px 18px 80px; }}
    h1 {{ font-size:clamp(1.8rem, 4vw, 2.6rem); margin:0 0 8px; }}
    .lead {{ color:var(--muted); font-size:1.12rem; line-height:1.5; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:14px; margin-top:22px; }}
    .card {{
      background:var(--panel); border:1px solid var(--line); padding:18px 16px;
      border-radius:14px; min-height:100px; display:flex; flex-direction:column; gap:8px;
    }}
    .card:hover {{ border-color:var(--brass); }}
    .card h2 {{ margin:0; font-size:1.2rem; }}
    .card p {{ margin:0; color:var(--muted); }}
    .chip {{
      display:inline-block; padding:7px 12px; border:1px solid var(--line);
      background:var(--panel); color:var(--ink); border-radius:999px; font-size:.92rem; margin:4px 4px 0 0;
    }}
    form {{ display:flex; gap:8px; margin-top:18px; flex-wrap:wrap; }}
    input[type=search] {{
      flex:1; min-width:180px; padding:12px 14px; border-radius:10px; border:1px solid var(--line);
      background:#0e100c; color:var(--ink); font:inherit;
    }}
    button {{
      font:inherit; cursor:pointer; background:var(--brass); color:#1a1408;
      border:0; padding:12px 16px; border-radius:10px; font-weight:700;
    }}
    .note {{ margin-top:28px; font-size:.92rem; color:var(--muted); border-top:1px solid var(--line); padding-top:14px; }}
    .empty {{ margin-top:18px; padding:18px; border:1px dashed var(--line); border-radius:12px; color:var(--muted); }}
    .err {{ color:#e7a2a2; }}
    #map {{ height:min(56vh, 480px); margin:18px 0; border-radius:14px; border:1px solid var(--line); background:#0e100c; }}
    .live-table {{ width:100%; border-collapse:collapse; margin-top:12px; font-size:.95rem; }}
    .live-table th, .live-table td {{ text-align:left; padding:8px 6px; border-bottom:1px solid var(--line); }}
    .live-table th {{ color:var(--brass); font-size:.82rem; letter-spacing:.04em; text-transform:uppercase; }}
    @media (max-width:640px) {{ .top {{ padding:12px; }} .brand {{ width:100%; }} }}
  </style>
</head>
<body>
  <header class="top">
    <a class="brand" href="/">🌍 OSM WORLD</a>
    <nav><a class="chip" href="/">🔎 Cerca</a><a class="chip" href="/aiuto">❓ Aiuto</a></nav>
  </header>
  <main class="wrap">
    {body}
    <p class="note">{h(OSM_NOTE)}</p>
  </main>
</body>
</html>"""


def search_form(value: str = "") -> str:
    return f"""
    <form action="/" method="get">
      <input type="search" name="q" placeholder="Tokyo, Parigi, Milano…" value="{h(value)}" autofocus/>
      <button>Cerca</button>
    </form>"""


def _place_qs(place: dict) -> str:
    south, west, north, east = place["bbox"]
    return urlencode(
        {
            "name": place.get("display") or place.get("name") or "",
            "lat": f"{place['lat']:.6f}",
            "lon": f"{place['lon']:.6f}",
            "s": f"{south:.5f}",
            "w": f"{west:.5f}",
            "n": f"{north:.5f}",
            "e": f"{east:.5f}",
        }
    )


def _place_from_qs(qs: dict[str, list[str]]) -> dict | None:
    try:
        lat, lon = float((qs.get("lat") or [""])[0]), float((qs.get("lon") or [""])[0])
        bbox = (
            float((qs.get("s") or [""])[0]),
            float((qs.get("w") or [""])[0]),
            float((qs.get("n") or [""])[0]),
            float((qs.get("e") or [""])[0]),
        )
    except (TypeError, ValueError):
        return None
    name = (qs.get("name") or [""])[0]
    return {"name": name, "display": name, "lat": lat, "lon": lon, "bbox": bbox, "country": ""}


def _leaflet(points: list[dict], center: tuple[float, float], zoom: int) -> str:
    payload = json.dumps(points, ensure_ascii=False).replace("<", "\\u003c")
    return f"""
<div id="map" role="img" aria-label="Mappa OSM WORLD"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
  integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
<script>
(function () {{
  const POINTS = {payload};
  const map = L.map("map").setView([{center[0]}, {center[1]}], {zoom});
  L.tileLayer("https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
    maxZoom: 16, attribution: "&copy; OpenStreetMap"
  }}).addTo(map);
  const layer = L.featureGroup();
  POINTS.forEach(function (p) {{
    const marker = L.circleMarker([p.lat, p.lon], {{ radius: 6, color: "#c4a35a", weight: 1, fillOpacity: 0.85 }});
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


def render_home(q: str) -> str:
    body = (
        "<h1>🌍 OSM WORLD</h1>"
        "<p class='lead'>Scrivi una città, un paese, una località. Poi scegli una categoria. "
        "Overpass parte solo allora.</p>"
        + search_form(q)
    )
    if not q:
        return layout("Cerca", body)
    result = geocode(q)
    if not result.get("ok"):
        body += f"<p class='empty err'>Nessun luogo per «{h(q)}»: {h(result.get('error') or '')}</p>"
        return layout(q, body)
    hits = result.get("hits") or []
    if len(hits) > 1:
        tiles = "".join(
            f'<a class="card" href="/luogo?{_place_qs(hit)}"><h2>{h(hit["display"])}</h2>'
            f'<p>{hit["lat"]:.3f}, {hit["lon"]:.3f}</p></a>'
            for hit in hits[:8]
        )
        body += f"<p class='lead'>Più risultati. Scegli il luogo.</p><div class='grid'>{tiles}</div>"
        return layout(q, body)
    return render_place(hits[0])


def render_place(place: dict) -> str:
    qs = _place_qs(place)
    cats = "".join(
        f'<a class="card" href="/cat/{key}?{qs}"><h2>{CATEGORIES[key]["emoji"]} {h(CATEGORIES[key]["title"])}</h2>'
        f"<p>Overpass solo su questa categoria.</p></a>"
        for key in WORLD_CATEGORIES
    )
    cats += f'<a class="card" href="/mappa?{qs}"><h2>🗺️ Mappa</h2><p>Foglio OpenStreetMap del luogo.</p></a>'
    note = place.get("bbox_note") or ""
    extra = f"<p class='lead'>{h(note)}</p>" if note else ""
    points = [{"lat": place["lat"], "lon": place["lon"], "label": html.escape(place.get("display") or "")}]
    body = (
        f"<h1>📍 {h(place.get('display') or place.get('name'))}</h1>"
        f"<p class='lead'>{place['lat']:.4f}, {place['lon']:.4f}</p>"
        + extra
        + search_form(place.get("name") or "")
        + _leaflet(points, (place["lat"], place["lon"]), 12)
        + f"<div class='grid'>{cats}</div>"
    )
    return layout(place.get("display") or "Luogo", body, extra_head=LEAFLET_HEAD)


def render_category(place: dict, cat: str) -> str:
    meta = CATEGORIES.get(cat)
    if not meta:
        return layout("Categoria", "<h1>Categoria assente</h1><p><a href='/'>Cerca</a></p>")
    bundle = search(place["bbox"], cat)
    qs = _place_qs(place)
    if not bundle.get("ok"):
        body = (
            f"<h1>{meta['emoji']} {h(meta['title'])}</h1>"
            f"<p class='empty err'>Overpass: {h(bundle.get('error') or 'errore')}</p>"
            f'<p><a class="chip" href="/cat/{cat}?{qs}">Riprova</a> <a class="chip" href="/luogo?{qs}">Località</a></p>'
        )
        return layout(meta["title"], body)
    rows = bundle.get("rows") or []
    points = [
        {
            "lat": r["lat"],
            "lon": r["lon"],
            "label": f"<b>{html.escape(r['name'])}</b>",
        }
        for r in rows[:80]
    ]
    table_rows = []
    for r in rows[:40]:
        extra = " / ".join(p for p in (r.get("iata"), r.get("icao"), r.get("uic")) if p)
        table_rows.append(
            "<tr>"
            f"<td><b>{h(r['name'])}</b></td>"
            f"<td>{h(extra or r.get('operator') or '—')}</td>"
            f"<td>{r['lat']:.4f}, {r['lon']:.4f}</td>"
            f"<td><a href='{h(r['map'])}'>OSM</a></td>"
            "</tr>"
        )
    table = (
        "<table class='live-table'><thead><tr><th>Nome</th><th>Dettaglio</th><th>Posizione</th><th></th></tr></thead><tbody>"
        + "".join(table_rows)
        + "</tbody></table>"
        if table_rows
        else "<p class='empty'>Niente in questa categoria nel riquadro.</p>"
    )
    body = (
        f"<h1>{meta['emoji']} {h(meta['title'])} · {h(place.get('display') or '')}</h1>"
        f"<p class='lead'>{bundle.get('total', 0)} elementi. Overpass solo su questa categoria.</p>"
        f'<p><a class="chip" href="/luogo?{qs}">📍 Località</a> <a class="chip" href="/mappa?{qs}">🗺️ Mappa</a></p>'
        + _leaflet(points, (place["lat"], place["lon"]), 12)
        + table
    )
    return layout(meta["title"], body, extra_head=LEAFLET_HEAD)


def render_map(place: dict) -> str:
    qs = _place_qs(place)
    points = [{"lat": place["lat"], "lon": place["lon"], "label": html.escape(place.get("display") or "")}]
    body = (
        f"<h1>🗺️ Mappa · {h(place.get('display') or '')}</h1>"
        f"<p class='lead'>{place['lat']:.4f}, {place['lon']:.4f}</p>"
        f'<p><a class="chip" href="{h(osm_url(place["lat"], place["lon"], 12))}">OpenStreetMap</a> '
        f'<a class="chip" href="/luogo?{qs}">📍 Località</a></p>'
        + _leaflet(points, (place["lat"], place["lon"]), 12)
    )
    return layout("Mappa", body, extra_head=LEAFLET_HEAD)


def render_help() -> str:
    body = """
    <h1>❓ Come funziona</h1>
    <p class="lead">OSM WORLD è solo questo: cerchi un luogo, scegli una categoria, Overpass risponde.</p>
    <div class="grid">
      <div class="card"><h2>🔎 Luogo</h2><p>Geocoder OSM (Photon, Nominatim in fallback), con cache. Non scarica la città intera.</p></div>
      <div class="card"><h2>🚆 Stazioni principali</h2><p>Treni passeggeri: train=yes, UIC, train_station. Niente metro, tram, bus, piattaforme, fermate.</p></div>
      <div class="card"><h2>🗺️ Mappa</h2><p>Foglio OpenStreetMap del riquadro. Le liste restano Overpass per categoria.</p></div>
    </div>
    """
    return layout("Aiuto", body)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:
        print("[osm]", fmt % args)

    def _send(self, body: str, status: int = 200) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
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
                page = render_home((qs.get("q") or [""])[0].strip())
            elif path == "/aiuto":
                page = render_help()
            elif path == "/luogo":
                place = _place_from_qs(qs)
                page = render_place(place) if place else render_home("")
            elif path.startswith("/cat/"):
                cat = path.split("/", 2)[-1]
                place = _place_from_qs(qs)
                page = render_category(place, cat) if place else render_home("")
            elif path == "/mappa":
                place = _place_from_qs(qs)
                page = render_map(place) if place else render_home("")
            else:
                self._send(layout("404", "<h1>Niente qui</h1><p><a href='/'>OSM WORLD</a></p>"), 404)
                return
            self._send(page)
        except Exception as exc:  # noqa: BLE001
            self._send(layout("Errore", f"<h1>OSM WORLD ha inciampato</h1><p class='err'>{h(exc)}</p>"), 500)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"OSM WORLD su http://127.0.0.1:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
