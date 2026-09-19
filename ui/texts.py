"""Testi di interfaccia OSM WORLD."""

from services.live.osm import OSM_NOTE


def help_text() -> str:
    return (
        "🌍 <b>OSM WORLD</b>\n\n"
        "Cerca una località, poi una categoria. Overpass parte solo quando tocchi.\n\n"
        "/start — cerca una città\n"
        "/osm Tokyo — vai dritto a Tokyo\n"
        "/aiuto — questo elenco\n\n"
        "✈️ Aeroporti · 🚆 Stazioni principali · 🏥 Ospedali\n"
        "⚓ Porti · 🏟️ Stadi · 🏬 Centri commerciali · 🏛️ Luoghi principali · 🗺️ Mappa\n\n"
        "Le stazioni sono query selettive (train=yes / UIC / train_station, NOT subway/tram/platform).\n"
        "Al massimo 20 per pagina, con ➡️ Altri risultati se ce ne sono di più.\n\n"
        "Ogni schermata ha ⬅️ Indietro e 🏠 Inizio.\n"
        "Un solo messaggio in chat: i bottoni lo aggiornano.\n\n"
        f"<i>{OSM_NOTE}</i>"
    )
