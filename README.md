# WARBOT

Posizioni **live** di aerei, navi e della stazione spaziale. Bot Telegram e mappa web. Un messaggio in chat, tastiere inline, ⬅️ Indietro e 🏠 Inizio.

Non è un radar militare e non serve a inseguire bersagli. I dati sono quelli che aerei e navi trasmettono apertamente.

## Cosa vedi

| Feed | Fonte | Cosa vedi |
| --- | --- | --- |
| ✈️ Aerei | ADS-B pubblico ([adsb.fi](https://opendata.adsb.fi)) | Italia, Mediterraneo, Europa, Manica, costa est USA, Giappone |
| 🚁 Elicotteri | stesso ADS-B, categoria eli | Stesse zone |
| ⚓ Navi | AIS aperto [Digitraffic](https://www.digitraffic.fi) (Finlandia) | Mar Baltico / acque finlandesi — un mare vero, non un AIS mondiale |
| 🛰️ ISS | [wheretheiss.at](https://wheretheiss.at) | Lat/lon, quota, velocità, luce o ombra |
| 🗺️ OSM WORLD | Overpass + geocoder (Photon, Nominatim in fallback) | Cerchi una località, poi una categoria. Overpass parte solo al tap |

Nel web: `/` e `/live` (hub con mappa), `/live/ac`, `/live/heli`, `/live/navi`, `/live/iss`, `/live.json`.

## Avvio locale

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Mappa nel browser (senza token):

```bash
python museum.py
```

Apri `http://127.0.0.1:47261`.

Bot Telegram: metti `TELEGRAM_BOT_TOKEN` in `.env`, poi:

```bash
python bot.py
```

Senza `WEBHOOK_URL` parte in **polling**. In produzione (Render) imposta `WEBHOOK_URL` HTTPS senza slash finale; `PORT` lo mette la piattaforma. Start command: `python bot.py`.

Non avviare il polling in locale se il bot è già in webhook su Render: Telegram accetta un solo ricevitore.

## Comandi Telegram

```
start - Hub live: ISS, aerei, navi
live - Hub live
osm - OSM WORLD: cerca una città, poi le categorie
aerei - ADS-B su una zona (it, med, eu, uk, us, jp)
elicotteri - Solo elicotteri
navi - AIS aperto del Baltico
iss - Posizione della stazione spaziale
aiuto - Elenco comandi
```

## Architettura

```
bot.py                 Telegram: nav, un solo messaggio, webhook/polling
museum.py              Mappa web sugli stessi feed (porta 47261)
ui/keyboards.py        Tastiere inline
ui/texts.py            Testi di interfaccia
services/live/feeds.py    ADS-B, AIS, ISS
services/live/geocode.py  Geocoder sostituibile + cache (Photon / Nominatim)
services/live/osm.py      Overpass per categoria, filtri stazioni, schede
```

🌍 **OSM WORLD** (`/osm` o bottone dal hub): scrivi Tokyo / Parigi / Milano. Il geocoder dà nome, paese, coordinate, bbox. Le categorie (aeroporti, stazioni ferroviarie, ospedali, porti, stadi, luoghi, centri commerciali, mappa) interrogano Overpass **solo al tap**. Le stazioni tengono `train=yes` / `building=train_station` / UIC e scartano metro, bus, fermate, piattaforme, ingressi.

Callback: `home:live`, `live:ac:it`, `live:heli:med`, `live:ships`, `live:iss`, `live:ow`, `live:ow:c:rail`, `live:ow:i:0`, `nav:back`, `home:menu`.
