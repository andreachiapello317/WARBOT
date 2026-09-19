"""Testi di interfaccia OSM WORLD."""

from services.live.osm import OSM_NOTE


def help_text() -> str:
    return (
        "🌍 <b>OSM WORLD</b>\n\n"
        "Cerca una località, una stazione, un duomo. Poi una categoria. Overpass parte solo al tap.\n\n"
        "/start — cerca una città\n"
        "/osm Tokyo — vai dritto a Tokyo\n"
        "/osm stazioni vicino al Duomo\n"
        "/aiuto — questo elenco\n\n"
        "✈️ Aeroporti · 🚆 Stazioni ferroviarie · 🏥 Ospedali\n"
        "⚓ Porti · 🏟️ Stadi · 🏬 Shopping · 🏛️ Luoghi importanti · 🗺️ Mappa\n\n"
        "Dalla scheda: mappa, dati OSM, cosa c'è vicino (around), esplora zona.\n"
        "Filtri sulle stazioni: principali / tutte, centro / tutta la città.\n\n"
        "Ogni schermata ha ⬅️ Indietro e 🏠 Inizio.\n"
        "Un solo messaggio in chat: i bottoni lo aggiornano.\n\n"
        f"<i>{OSM_NOTE}</i>"
    )
