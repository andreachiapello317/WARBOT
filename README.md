# WARBOT — città, mondi, query

START chiede una località. Il geocoding crea il **CityContext** (nome, lat, lon, bbox). Poi il menu dei mondi. Ogni mondo ha le sue query. Passare da un mondo all'altro **non** rifà il geocoding. Il menu 🌎 MONDI non chiama API.

```
🌍 WARBOT
   → 📍 CITTÀ (geocoding una volta)
      → 🌎 MONDI
         → 🗺️ OSM WORLD     → Overpass (maps.mail.ru)
         → ✈️ AIR TRAFFIC   → airplanes.live / ADSB.lol
         → 🌤️ SKY           → Open-Meteo
         → 🌋 EARTH         → USGS + EONET + GloFAS
         → 🛰️ SPACE         → ISS + CelesTrak TLE
```

## Avvio

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python bot.py
```

Senza `WEBHOOK_URL` il bot parte in polling. Su Render: `WEBHOOK_URL` HTTPS, start command `python bot.py`. Nessuna API key per i mondi (solo `TELEGRAM_BOT_TOKEN`).

## Comandi

```
start / osm / airtraffic / sky / earth / space / aiuto
```

## Architettura

Il core Telegram (sessione, CityContext, `deliver`, registry) non conosce gli endpoint dei mondi. Ogni mondo sta in `worlds/<id>/` e si registra in `worlds/registry.py`.

Overpass primario: `https://maps.mail.ru/osm/tools/overpass/api/interpreter`.
