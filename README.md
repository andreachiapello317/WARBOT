# WARBOT — OSM WORLD

Cerca una località nel mondo, scegli una categoria, Overpass risponde. Bot Telegram e mappa web.

Non scarica una città intera: il geocoder trova il luogo, Overpass parte **solo** quando tocchi una categoria. Geocoding e risultati categoria restano in cache (memoria + `data/osm_cache.json`) con TTL configurabile.

## Flusso

1. Scrivi Tokyo, Parigi, Milano… — solo geocoding, nessuna query Overpass
2. 📍 Località e menu categorie, subito
3. Tocca una categoria: Overpass QL selettivo sul punto
4. Lista ordinata per rilevanza OSM (operator, binari, sito, mappa)
5. Scheda del risultato: dove si trova, dati OSM, mappa, **cosa c'è vicino**, esplora zona
6. I dintorni usano `around` Overpass **una categoria alla volta**
7. Filtri Telegram su stazioni (principali/tutte, centro/città) e aeroporti (passeggeri/tutti/vicino)
8. Frasi tipo `stazioni vicino al Duomo` o `aeroporti Milano`

Overpass Turbo **non** è l'endpoint: è solo il modello mentale (Wizard AND/OR, corso «oltre il wizard»). Runtime: `https://maps.mail.ru/osm/tools/overpass/api/interpreter`. Niente scorciatoie `{{bbox}}` / `{{geocodeArea}}`.

Le **stazioni ferroviarie** chiedono `railway=station` + `train=yes`, escludono subway/tram/halt/platform/bus in query e in filtro. `out center N` restituisce centroide e tag, senza recurse sui membri. Se l'interpreter risponde 504 si prova un secondo host. Un timeout sul primo host (6s) non blocca: si tenta il secondo, poi Riprova.

## Avvio locale

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python museum.py
```

Apri `http://127.0.0.1:47261`.

Bot Telegram: `TELEGRAM_BOT_TOKEN` in `.env`, poi `python bot.py`.

Senza `WEBHOOK_URL` parte in polling. In produzione (Render) imposta `WEBHOOK_URL` HTTPS senza slash finale. Start command: `python bot.py`. Non avviare il polling in locale se il webhook è già attivo.

## Comandi

```
start - OSM WORLD
osm - OSM WORLD (opzionale: /osm Tokyo)
aiuto - Come funziona
```

In chat puoi anche scrivere solo il nome del luogo.

## Architettura

```
bot.py                    Telegram: un messaggio, callback live:ow
museum.py                 Web OSM WORLD (porta 47261)
ui/keyboards.py           Tastiere
ui/texts.py               Aiuto
services/live/geocode.py  Photon (fail-fast) / Nominatim, cache
services/live/engine.py   Compilatore Overpass QL (AND/union/difference/around; non Turbo)
services/live/osm.py      Categorie, ranking, fallback, cache
services/live/cache.py    Cache memoria + file, TTL
```

Callback: `live:ow`, `live:ow:c:rail`, `live:ow:i:0`, `live:ow:map`, `nav:back`, `home:menu`.

Geocoder: `OSM_GEOCODER=photon` (default) o `nominatim`. `OSM_GEOCODER_URL` per un'istanza tua.

Cache: `OSM_CACHE_TTL_GEOCODE` (default 6h), `OSM_CACHE_TTL_OVERPASS` (default 3h), `OSM_CACHE_FILE`.
