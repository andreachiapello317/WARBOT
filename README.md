# WARBOT — OSM WORLD

Cerca una località nel mondo, scegli una categoria, Overpass risponde. Bot Telegram e mappa web.

Non scarica una città intera: il geocoder trova il luogo, Overpass parte **solo** quando tocchi una categoria.

## Flusso

1. Scrivi Tokyo, Parigi, Milano…
2. 📍 Località trovata
3. Categoria: aeroporti, stazioni ferroviarie, ospedali, porti, stadi, luoghi, centri commerciali, mappa
4. Lista → scheda (coordinate, sito, Wikipedia, Wikidata)

Le **stazioni ferroviarie** tengono `train=yes`, `building=train_station`, UIC. Fuori metro, bus, fermate, piattaforme, ingressi.

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
services/live/geocode.py  Photon / Nominatim, cache, sostituibile
services/live/osm.py      Overpass per categoria
```

Callback: `live:ow`, `live:ow:c:rail`, `live:ow:i:0`, `live:ow:map`, `nav:back`, `home:menu`.

Geocoder: `OSM_GEOCODER=photon` (default) o `nominatim`. `OSM_GEOCODER_URL` per un'istanza tua.
