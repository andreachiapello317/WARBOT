"""Testi di interfaccia WARBOT."""

from services.live.osm import OSM_NOTE


def help_text() -> str:
    return (
        "🌍 <b>WARBOT</b>\n\n"
        "1. /start — inserisci una città\n"
        "2. Scegli un mondo\n"
        "3. Scegli una query di quel mondo\n\n"
        "🗺️ <b>OSM WORLD</b> — aeroporti, stazioni, ospedali, porti, stadi, shopping, luoghi\n"
        "✈️ <b>AIR TRAFFIC</b> — aerei LIVE\n"
        "🌤️ <b>SKY</b> — meteo, aria, mare, sole\n"
        "🌋 <b>EARTH</b> — terremoti, incendi, eventi, fiumi\n"
        "🛰️ <b>SPACE</b> — ISS, Starlink, satelliti\n\n"
        "La città si geocodifica una volta. Passare da un mondo all'altro non rifà il geocoding.\n"
        "Il menu mondi non chiama alcuna API.\n\n"
        "/osm /airtraffic /sky /earth /space — aprono il mondo se la città c'è già\n"
        "/aiuto — questo elenco\n\n"
        "⬅️ Indietro · 🌍 Mondi · 📍 Cambia città\n"
        "Un solo messaggio in chat: i bottoni lo aggiornano.\n\n"
        f"<i>{OSM_NOTE}</i>"
    )
