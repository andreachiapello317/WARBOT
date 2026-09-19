"""Testi di interfaccia WARBOT live."""

from services.live import LIVE_NOTE


def help_text() -> str:
    return (
        "📡 <b>WARBOT live</b>\n\n"
        "Posizioni vere, adesso. Feed pubblici: niente radar militare.\n\n"
        "/start — hub: ISS, aerei sull'Italia, navi del Baltico\n"
        "/live — stesso hub, aggiornato\n"
        "/live milano — OSM: aeroporti, stazioni, ospedali (Overpass)\n"
        "/aerei — ADS-B su una zona (it, med, eu, uk, us, jp)\n"
        "/elicotteri — stesso ADS-B, solo eli\n"
        "/navi — AIS aperto del Baltico finlandese\n"
        "/iss — quota, velocità, mappa della stazione\n"
        "/aiuto — questo elenco\n\n"
        "Ogni schermata ha ⬅️ Indietro e 🏠 Inizio.\n"
        "Un solo messaggio in chat: i bottoni lo aggiornano.\n\n"
        f"<i>{LIVE_NOTE}</i>"
    )
