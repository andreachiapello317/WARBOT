# WARBOT — città, mondi, query

START chiede una località (testo o posizione Telegram). Il geocoding crea il **CityContext** (nome, lat, lon, bbox). Poi il menu dei mondi. Ogni mondo ha le sue query. Passare da un mondo all'altro **non** rifà il geocoding. Il menu 🌎 MONDI non chiama API.

```
🌍 WARBOT
   → 📍 CITTÀ (geocoding una volta)
      → 🌎 MONDI
         → 🗺️ OSM WORLD     → Overpass (maps.mail.ru)
         → 🏙️ CITY LIFE     → OSM + Open-Meteo + Meteoalarm
         → ✈️ AIR TRAFFIC   → airplanes.live / ADSB.lol
         → 🌤️ SKY           → Open-Meteo (meteo, aria, pollini)
         → 🌋 EARTH         → USGS + EONET + GloFAS
         → 🛰️ SPACE         → ISS + CelesTrak + NOAA + JPL
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
start / osm / life / airtraffic / sky / earth / space / aiuto
```

Condividi la posizione in chat: imposta «Qui» e apre CITY LIFE → Vicino a me.

## CITY LIFE — cosa c'è e cosa no

Su questo piano, senza chiavi a pagamento:

- **Vicino a me**: aria/pollini Open-Meteo + POI OSM nel raggio
- **Mobilità**: fermate bus/tram/metro, bike/car sharing, parcheggi, webcam taggate OSM
- **Sicurezza**: ospedali/farmacie OSM + allerte Meteoalarm (Europa)
- **Vita in città**: cinema, teatri, mercati, musei, ristoranti; «aperto ora» se `opening_hours` è taggato
- **Servizi**: fontanelle, WiFi, bagni, webcam
- **Passeggiata**: elenco punti entro ~1,2 km
- **Storico**: meteo e aria ieri / 7 giorni (Open-Meteo)
- **Confronta**: città attuale vs precedente (stesso geocoding, niente seconda ricerca)

Non su questo piano (servono chiavi, feed locali o un database):

- Traffico live TomTom / Google
- Ritardi GTFS-RT (GTT e simili)
- Veicoli sharing e posti auto **liberi in questo istante**
- Tempi di attesa al Pronto Soccorso e farmacie di turno ufficiali
- Rumore ambientale live, qualità chimica dei fiumi, sagre/biglietti cinema
- Notifiche push, audio live della città

I link Street View aprono Google Maps sul telefono; il bot non chiama l'API Google.

## Architettura

Il core Telegram (sessione, CityContext, `deliver`, registry) non conosce gli endpoint dei mondi. Ogni mondo sta in `worlds/<id>/` e si registra in `worlds/registry.py`.

Overpass primario: `https://maps.mail.ru/osm/tools/overpass/api/interpreter`.
