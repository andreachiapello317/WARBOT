# WARBOT — città, mondi, query

START chiede una località. Il geocoding crea il **CityContext** (nome, lat, lon, bbox). Poi il menu dei mondi. Ogni mondo ha le sue query. Passare da OSM ad AIR TRAFFIC **non** rifà il geocoding.

```
🌍 WARBOT
   → 📍 CITTÀ (geocoding una volta)
      → 🌎 MONDI
         → 🗺️ OSM WORLD     → query Overpass
         → ✈️ AIR TRAFFIC   → ✈️ Aerei LIVE (ADSB.lol)
```

## Flusso

1. `/start` — «Inserisci una città o località»
2. Scrivi Milano — solo geocoding, **né Overpass né ADSB.lol**
3. 📍 Milano → scegli un mondo
4. 🗺️ OSM WORLD → menu categorie (ancora nessuna query)
5. 🚆 Stazioni → **solo** Overpass
6. ✈️ AIR TRAFFIC → menu (nessuna query)
7. ✈️ Aerei LIVE → **solo** ADSB.lol, stesse lat/lon, raggio ~50 km

⬅️ OSM / ⬅️ Air Traffic torna al menu del mondo. 🌍 Mondi torna al menu globale. 📍 Cambia città torna a START.

## Avvio locale

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python bot.py
```

Mappa web OSM: `python museum.py` → `http://127.0.0.1:47261`.

Senza `WEBHOOK_URL` il bot parte in polling. In produzione (Render) imposta `WEBHOOK_URL` HTTPS senza slash finale. Start command: `python bot.py`. Non avviare il polling in locale se il webhook è già attivo.

Su Render **non** servono credenziali per gli aerei LIVE: ADSB.lol è pubblico.

## Comandi

```
start - Inserisci una città
osm - OSM WORLD (opzionale: /osm Tokyo)
airtraffic - AIR TRAFFIC
aiuto - Come funziona
```

## Architettura

```
bot.py                      Telegram: città, sessione, dispatch ai mondi
core/session.py             CityContext + schermo/mondo
core/telegram.py            Un messaggio: edit, RetryAfter, un solo send
worlds/registry.py          Registry OSM + AIR TRAFFIC
worlds/city.py              START, geocoding, WORLD MENU
worlds/osm/                 Menu + query wrapper → services/live/osm.py
worlds/airtraffic/          Menu + query wrapper → services/live/aircraft.py
services/live/geocode.py    Photon / Nominatim
services/live/engine.py     Compilatore Overpass QL
services/live/osm.py        Motore OSM (filtri, ranking, cache, failover)
services/live/adsb_client.py  GET pubblica ADSB.lol (nessun token)
services/live/aircraft.py   Normalizzazione aircraft ADSB.lol
museum.py                   Web OSM WORLD (invariato)
```

Callback: `city:ask`, `world:list`, `world:osm`, `world:airtraffic`, `osm:rail`, `osm:rail:page:2`, `airtraffic:aircraft`, `airtraffic:aircraft:page:1`.

Overpass primary: `https://maps.mail.ru/osm/tools/overpass/api/interpreter`. Failover: overpass-api.de, lz4.overpass-api.de. Una replica con timestamp OSM invalido (es. overpass.osm.ch vuoto) non conta come «zero risultati». GET `/` e `/health` sul webhook rispondono 200 (Render non deve vedere 404).

AIR TRAFFIC: [ADSB.lol OpenAPI](https://api.adsb.lol/api/openapi.json) — `GET /v2/lat/{lat}/lon/{lon}/dist/{radius}` con raggio in miglia nautiche (0–250). Default WARBOT: 50 km ≈ 27 nm. Nessuna API key. Cache breve (pochi secondi) solo per callback ravvicinati. Niente polling.
