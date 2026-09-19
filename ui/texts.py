"""Testi di interfaccia OSM WORLD."""

from services.live.osm import OSM_NOTE


def help_text() -> str:
    return (
        "🌍 <b>OSM WORLD</b>\n\n"
        "Cerca una località, poi una categoria. Overpass parte solo quando tocchi.\n\n"
        "/start — cerca una città\n"
        "/osm Tokyo — vai dritto a Tokyo\n"
        "/aiuto — questo elenco\n\n"
        "✈️ Aeroporti · 🚆 Stazioni ferroviarie · 🏥 Ospedali\n"
        "⚓ Porti · 🏟️ Stadi · 🏛️ Luoghi · 🛍️ Centri · 🗺️ Mappa\n\n"
        "Le stazioni sono treni (train=yes / UIC / train_station), non metro o fermate.\n\n"
        "Ogni schermata ha ⬅️ Indietro e 🏠 Inizio.\n"
        "Un solo messaggio in chat: i bottoni lo aggiornano.\n\n"
        f"<i>{OSM_NOTE}</i>"
    )
