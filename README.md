# WARBOT

Museo Telegram (e web) di **storia militare**. Stessa architettura a mondi di un bot enciclopedico: un messaggio in chat, tastiere inline, callback a prefisso, ⬅️ Indietro e 🏠 Inizio.

Non è un manuale operativo. I testi descrivono guerre, eserciti, mezzi e trattati come materia storica e culturale.

## Sei mondi

| Mondo | Cosa contiene |
| --- | --- |
| ⚔️ **Epoche** | Guerre storiche per era (antichità → contemporanea) |
| 🗺️ **Campi** | Battaglie: date, forze, fasi narrative, conseguenze |
| 🪖 **Truppe** | Ruoli (fanteria, genio, medici…) e scala dei gradi |
| 🏳️ **Bandiere** | Forze armate (Italia, Francia, UK, USA, Roma, NATO) |
| ⚙️ **Ferro** | Equipaggiamento, mezzi, fortificazioni, spazio militare |
| 🕊️ **Patti** | Trattati, pace, personaggi, strategia come storia |

## Epoche (timeline viva)

Non sono più solo le schede statiche. **🌍 Epoche** apre diciotto ere (Preistoria → era digitale). Per ognuna: panoramica Wikipedia/Wikidata, timeline, guerre, personaggi, luoghi, soldati, tecnologia, galleria (Commons + Library of Congress, Europeana se `EUROPEANA_API_KEY`).

Una sola scheda per Q-id Wikidata: Napoleone non si duplica tra moduli. **🎲 Viaggia nel tempo** (`/viaggia`) pesca anno, evento, persone, immagine.

Le 85 schede del cassetto restano sotto **📚 Cassetto del museo**. Campi, Truppe, Bandiere, Ferro, Patti non sono toccati.

## Live (aerei, navi, ISS)

Quadro **📡 Posizioni live**: all'apertura mostra già ISS, aerei sull'Italia e navi del Baltico. Non è un radar militare e non serve a inseguire bersagli.

| Feed | Fonte | Cosa vedi |
| --- | --- | --- |
| ✈️ Aerei | ADS-B pubblico (adsb.fi) | Zone: Italia, Mediterraneo, Europa, Manica, costa est USA, Giappone |
| 🚁 Elicotteri | stesso ADS-B, categoria eli | Stesse zone |
| ⚓ Navi | AIS aperto Digitraffic (Finlandia) | Mar Baltico / acque finlandesi — un mare vero, non un AIS mondiale |
| 🛰️ ISS | wheretheiss.at | Lat/lon, altezza, velocità |

Nel museo web: `/live`, `/live/ac`, `/live/navi`, `/live/iss` (mappa OpenStreetMap) e `/live.json`.

## Architettura

```
bot.py              Telegram: nav, un solo messaggio, webhook/polling
museum.py           Museo web sugli stessi cataloghi (anteprima)
ui/keyboards.py     Tastiere inline
ui/texts.py         Testi di interfaccia
services/           Schede per mondo + ricerca + quiz + live ADS-B/AIS
```

Callback come nel bot a mondi: `world:epoche`, `e:stlg`, `l:war:ant`, `q:bat`, `nav:back`, `home:menu`.

## Avvio locale

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Museo nel browser (senza token):

```bash
python museum.py
```

Apri `http://127.0.0.1:47261`. Live: `http://127.0.0.1:47261/live`.

Bot Telegram: metti `TELEGRAM_BOT_TOKEN` in `.env`, poi:

```bash
python bot.py
```

Senza `WEBHOOK_URL` parte in **polling**. In produzione (Render) imposta `WEBHOOK_URL` HTTPS senza slash finale; `PORT` lo mette la piattaforma. Start command: `python bot.py`.

## Comandi Telegram

```
start - I sei mondi del museo
esplora - Mappa dei mondi
epoche - Timeline storica da archivi pubblici
viaggia - Un anno e un evento a caso
campi - Battaglie
truppe - Soldati e gradi
bandiere - Forze armate
ferro - Mezzi e fortificazioni
patti - Pace, trattati, personaggi
cerca - Ricerca universale
quiz - Quiz storico
oggi - Scheda del giorno
casuale - Una scheda a caso
live - Posizioni live: aerei, navi, ISS
aerei - ADS-B pubblico su una zona
navi - AIS aperto del Baltico
iss - Posizione della stazione spaziale
aiuto - Elenco comandi
```

Scrivi **Stalingrado** in chat (o dopo 🔍 Cerca): il bot raggruppa guerra, battaglia, personaggi, mezzi.

## Cosa non c’è (volutamente)

Istruzioni di combattimento, costruzione o modifica di armi, tavole di tiro, procedure di sbarco, dettagli operativi contemporanei. Le armi e i mezzi hanno storia, caratteristiche generali e impiego documentato.
