"""Testi di interfaccia WARBOT. Non sono contenuti enciclopedici."""

from services.catalog import DISCLAIMER, WORLDS
from services.quiz import kind_count


def home_text() -> str:
    return (
        "⚔️ <b>WARBOT</b>\n"
        "Museo della storia militare.\n\n"
        "Sei mondi, un filo: capire guerre, eserciti e pace senza trasformarli in un manuale.\n\n"
        "📡 <b>POSIZIONI LIVE</b> — il bottone in cima. Aerei, navi, ISS: coordinate vere, adesso.\n"
        "Comando: /live\n\n"
        "⚔️ <b>EPOCHE</b> — enciclopedia curata, dall'antichità allo spazio, con fonti\n"
        "🗺️ <b>CAMPI</b> — battaglie, fasi, conseguenze\n"
        "🪖 <b>TRUPPE</b> — ruoli del soldato e gradi\n"
        "🏳️ <b>BANDIERE</b> — forze armate e alleanze\n"
        "⚙️ <b>FERRO</b> — equipaggiamento, mezzi, fortificazioni\n"
        "🕊️ <b>PATTI</b> — trattati, personaggi, strategia come storia\n\n"
        "📖 <b>OGGI</b> pesca una scheda del giorno.\n"
        "🎲 <b>CASUALE</b> apre un cassetto a caso.\n\n"
        f"<i>{DISCLAIMER}</i>"
    )


def esplora_text() -> str:
    return (
        "🧭 <b>ESPLORA</b>\n\n"
        "Sei mondi. Tocca quello che vuoi aprire.\n\n"
        "⚔️ Epoche — i conflitti\n"
        "🗺️ Campi — le battaglie\n"
        "🪖 Truppe — chi c'era, e con quale grado\n"
        "🏳️ Bandiere — gli eserciti\n"
        "⚙️ Ferro — oggetti e opere\n"
        "🕊️ Patti — la pace e chi ha firmato\n"
        "📡 Posizioni live — aerei, navi, ISS in diretta\n"
        "🌍 Epoche — timeline, personaggi, immagini di musei\n\n"
        f"<i>{DISCLAIMER}</i>"
    )


def world_text(key: str) -> str:
    meta = WORLDS[key]
    extra = {
        "epoche": "Diciotto ere, schede curate, archivi (IWM, LoC, NASA…). Wikidata solo come grafo.",
        "campi": "Ogni battaglia ha data, luogo, forze, fasi narrative, comandanti, memoria.",
        "truppe": "Ruoli storici (fante, genio, medico…) e scala dei gradi, con confronti.",
        "bandiere": "Schede pubbliche: storia, organizzazione generale, tradizioni, missioni note.",
        "ferro": "Dal bronzo ai satelliti. Storia e caratteristiche generali, niente istruzioni.",
        "patti": "Westfalia, Vienna, Ginevra, ONU. E i concetti: logistica, assedio, comando.",
    }[key]
    return (
        f"{meta['emoji']} <b>{meta['title']}</b>\n\n"
        f"{meta['blurb']}\n{extra}\n\n"
        f"<i>{DISCLAIMER}</i>"
    )


def quiz_hub_text() -> str:
    return (
        "🎲 <b>QUIZ STORICO</b>\n\n"
        "Domande costruite sulle schede del museo.\n"
        "Se sbagli, la scheda è lì sotto.\n\n"
        f"{kind_count()}\n\n"
        f"<i>{DISCLAIMER}</i>"
    )


def cerca_text() -> str:
    return (
        "🔍 <b>CERCA</b>\n\n"
        "Scrivi un nome. Un esempio:\n"
        "<b>Stalingrado</b>\n\n"
        "WARBOT raggruppa guerra, battaglia, personaggi, mezzi, documenti.\n\n"
        "Altri tentativi: Waterloo, Maginot, Alpini, Westfalia, T-34, Folgore."
    )


def help_text() -> str:
    return (
        "📚 <b>Manuale del museo</b>\n\n"
        "/start — i sei mondi\n"
        "/esplora — mappa dei mondi\n"
        "/epoche — timeline curata (archivi, non un dump Wikidata)\n"
        "/viaggia — un anno, un evento, un luogo a caso\n"
        "/campi — battaglie\n"
        "/truppe — soldati e gradi\n"
        "/bandiere — forze armate\n"
        "/ferro — mezzi e fortificazioni\n"
        "/patti — pace, trattati, personaggi\n"
        "/cerca — ricerca universale\n"
        "/quiz — indovina guerra, battaglia, grado…\n"
        "/oggi — scheda del giorno\n"
        "/casuale — un cassetto a caso\n"
        "/live — posizioni live: aerei, navi, ISS (radio pubbliche)\n"
        "/aerei — ADS-B su una zona (it, med, eu, uk, us, jp)\n"
        "/navi — AIS aperto del Baltico finlandese\n"
        "/iss — mappa e quota della stazione spaziale\n"
        "/aiuto — questo elenco\n\n"
        "Ogni schermata ha ⬅️ Indietro e 🏠 Inizio.\n"
        "Un solo messaggio in chat: i bottoni lo aggiornano.\n\n"
        f"<i>{DISCLAIMER}</i>"
    )
