# WARBOT — città, mondi, query

START chiede una località. Il geocoding crea il **CityContext** (nome, lat, lon, bbox). Poi il menu dei mondi. Ogni mondo ha le sue query. Passare da OSM a OpenSky **non** rifà il geocoding.

```
🌍 WARBOT
   → 📍 CITTÀ (geocoding una volta)
      → 🌎 MONDI
         → 🗺️ OSM WORLD     → query Overpass
         → ✈️ OPEN SKY      → query OpenSky
```

## Flusso

1. `/start` — «Inserisci una città o località»
2. Scrivi Milano — solo geocoding, **né Overpass né OpenSky**
3. 📍 Milano → scegli un mondo
4. 🗺️ OSM WORLD → menu categorie (ancora nessuna query)
5. 🚆 Stazioni → **solo** Overpass
6. ✈️ OPEN SKY → menu (nessuna query)
7. ✈️ Aerei LIVE → **solo** OpenSky, stesse lat/lon

⬅️ OSM / ⬅️ OpenSky torna al menu del mondo. 🌍 Mondi torna al menu globale. 📍 Cambia città torna a START.

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

## Comandi

```
start - Inserisci una città
osm - OSM WORLD (opzionale: /osm Tokyo)
opensky - OPEN SKY
aiuto - Come funziona
```

## Architettura

```
bot.py                      Telegram: città, sessione, dispatch ai mondi
core/session.py             CityContext + schermo/mondo
core/telegram.py            Un messaggio: edit, RetryAfter, un solo send
worlds/registry.py          Registry OSM + OpenSky
worlds/city.py              START, geocoding, WORLD MENU
worlds/osm/                 Menu + query wrapper → services/live/osm.py
worlds/opensky/             Menu + query wrapper → services/live/aircraft.py
services/live/geocode.py    Photon / Nominatim
services/live/engine.py     Compilatore Overpass QL
services/live/osm.py        Motore OSM (filtri, ranking, cache, failover)
services/live/opensky_client.py  OAuth2 client (token riusato)
services/live/aircraft.py   Normalizzazione GET /states/all
museum.py                   Web OSM WORLD (invariato)
```

Callback: `city:ask`, `world:list`, `world:osm`, `world:opensky`, `osm:rail`, `osm:rail:page:2`, `opensky:aircraft`, `opensky:aircraft:page:1`.

Overpass primary: `https://overpass.osm.ch/api/interpreter`. Failover: overpass-api.de, maps.mail.ru. Una risposta 200 vuota non ferma il failover. GET `/` e `/health` sul webhook rispondono 200 (Render non deve vedere 404).

OpenSky: [REST](https://openskynetwork.github.io/opensky-api/rest.html) e [Python API 1.4.0](https://openskynetwork.github.io/opensky-api/python.html) — `GET /api/states/all` con bbox (`lamin`/`lamax`/`lomin`/`lomax`) e `extended=1`. Token OAuth2 riusato (TokenManager), sessione HTTP persistente, minimo 5s tra `get_states` autenticati. Niente accesso anonimo.

Su Render imposta **obbligatorie**:

- `OPENSKY_CLIENT_ID`
- `OPENSKY_CLIENT_SECRET`

OAuth2 client credentials. **Non** usare `OPENSKY_USERNAME` / `OPENSKY_PASSWORD`. Niente file `credentials.json` nel repo. Senza `OPENSKY_CLIENT_ID` e `OPENSKY_CLIENT_SECRET` il mondo OpenSky resta visibile nel menu ma non chiama l'API: log `not_configured`, nessun accesso anonimo.
