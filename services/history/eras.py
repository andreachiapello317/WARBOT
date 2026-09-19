"""Catalogo delle ere: anni, Q-id Wikidata, ricerche per immagini. Non è un manuale."""

from __future__ import annotations

from typing import Any

# id corto per i callback Telegram (max 64 byte).
ERAS: dict[str, dict[str, Any]] = {
    "pre": {
        "emoji": "🏺",
        "title": "Preistoria",
        "years": "fino al IV millennio a.C.",
        "start": -10000,
        "end": -3500,
        "qid": "Q11756",
        "wiki": "Preistoria",
        "media": "prehistoric archaeology cave painting",
        "people": ("Q1422", "Q102818"),  # Ötzi, Lucy se presenti
    },
    "ant": {
        "emoji": "🏛️",
        "title": "Antichità",
        "years": "IV millennio a.C. – V secolo",
        "start": -3500,
        "end": 500,
        "qid": "Q41493",
        "wiki": "Storia_antica",
        "media": "ancient egypt mesopotamia antiquity",
        "people": ("Q37140", "Q3801", "Q129255"),  # Hammurabi, Ramses, Gilgamesh
        "wars": ("Q83159", "Q202161", "Q2029"),  # greco-persiane, peloponneso, troia
    },
    "gre": {
        "emoji": "🏺",
        "title": "Antica Grecia",
        "years": "VIII–I secolo a.C.",
        "start": -800,
        "end": -30,
        "qid": "Q11772",
        "wiki": "Antica_Grecia",
        "media": "ancient greece hoplite parthenon",
        "people": ("Q8409", "Q868", "Q12872", "Q131671"),  # Alessandro, Platone, Pericle, Erodoto
        "wars": ("Q83159", "Q202161", "Q2029"),
    },
    "rom": {
        "emoji": "🦅",
        "title": "Roma",
        "years": "753 a.C. – 476",
        "start": -753,
        "end": 476,
        "qid": "Q1747689",
        "wiki": "Antica_Roma",
        "media": "ancient rome legionary forum",
        "people": ("Q1048", "Q40787", "Q1398", "Q1418"),  # Cesare, Augusto, Annibale, Scipione
        "wars": ("Q202161", "Q2029", "Q12554"),
    },
    "tarda": {
        "emoji": "✝️",
        "title": "Tarda Antichità",
        "years": "III–VII secolo",
        "start": 284,
        "end": 632,
        "qid": "Q217050",
        "wiki": "Tarda_antichità",
        "media": "late antiquity byzantine constantinople",
        "people": ("Q8413", "Q41670", "Q184437"),  # Costantino, Giustiniano, Agostino
    },
    "med": {
        "emoji": "🏰",
        "title": "Medioevo",
        "years": "V–XV secolo",
        "start": 476,
        "end": 1492,
        "qid": "Q12554",
        "wiki": "Medioevo",
        "media": "medieval castle knight crusades manuscript",
        "people": ("Q43959", "Q191054", "Q133600", "Q180020"),  # Carlo Magno, Saladino, Gengis Khan, Giovanna
        "wars": ("Q12201", "Q51600", "Q12570"),  # crociate, cento anni, guerra delle rose
    },
    "rin": {
        "emoji": "⚔️",
        "title": "Rinascimento",
        "years": "XIV–XVI secolo",
        "start": 1350,
        "end": 1600,
        "qid": "Q4692",
        "wiki": "Rinascimento",
        "media": "renaissance italy leonardo armor",
        "people": ("Q762", "Q5681", "Q1399", "Q191681"),  # Leonardo, Machiavelli, Michelangelo, Carlo V
        "wars": ("Q51604", "Q12577"),  # guerre d'Italia, ottanta anni
    },
    "mod": {
        "emoji": "👑",
        "title": "Età moderna",
        "years": "1492–1789",
        "start": 1492,
        "end": 1789,
        "qid": "Q5308718",
        "wiki": "Età_moderna",
        "media": "early modern europe thirty years war sail",
        "people": ("Q129247", "Q1511", "Q4604"),  # Richelieu, Luigi XIV, Newton
        "wars": ("Q2487", "Q12577", "Q182890"),  # trent'anni, ottanta anni, successione spagnola
    },
    "riv": {
        "emoji": "🌎",
        "title": "Età delle rivoluzioni",
        "years": "1775–1848",
        "start": 1775,
        "end": 1848,
        "qid": "Q6534",
        "wiki": "Rivoluzione_francese",
        "media": "french revolution napoleon 1789",
        "people": ("Q22686", "Q517", "Q1511", "Q1511"),
        "wars": ("Q17921", "Q78994", "Q6534"),
    },
    "ind": {
        "emoji": "🏭",
        "title": "Rivoluzione industriale",
        "years": "1760–1914",
        "start": 1760,
        "end": 1914,
        "qid": "Q2269",
        "wiki": "Rivoluzione_industriale",
        "media": "industrial revolution factory steam locomotive",
        "people": ("Q1519", "Q9095", "Q355"),  # Watt, Marx, Stephenson se Q ok
    },
    "xix": {
        "emoji": "👑",
        "title": "XIX secolo",
        "years": "1801–1900",
        "start": 1801,
        "end": 1900,
        "qid": "Q6955",
        "wiki": "XIX_secolo",
        "media": "nineteenth century victorian american civil war",
        "people": ("Q517", "Q22686", "Q1313", "Q91"),  # Napoleone, Lincoln, Garibaldi, Bismarck
        "wars": ("Q78994", "Q8676", "Q1983"),  # napoleoniche, secessione, franco-prussiana
    },
    "ww1": {
        "emoji": "🌍",
        "title": "Prima guerra mondiale",
        "years": "1914–1918",
        "start": 1914,
        "end": 1918,
        "qid": "Q361",
        "wiki": "Prima_guerra_mondiale",
        "media": "world war I trench uniform 1916",
        "people": ("Q7737", "Q40767", "Q159631", "Q1511"),  # Giolitti?, Joffre, Haig - will skip missing
        "wars": ("Q361",),
    },
    "int": {
        "emoji": "🌍",
        "title": "Periodo interbellico",
        "years": "1918–1939",
        "start": 1918,
        "end": 1939,
        "qid": "Q154611",
        "wiki": "Periodo_interbellico",
        "media": "interwar 1920s 1930s depression fascism",
        "people": ("Q352", "Q8016", "Q22686"),
        "wars": ("Q10829", "Q215609"),  # Spagna, Etiopia
    },
    "ww2": {
        "emoji": "⚔️",
        "title": "Seconda guerra mondiale",
        "years": "1939–1945",
        "start": 1939,
        "end": 1945,
        "qid": "Q362",
        "wiki": "Seconda_guerra_mondiale",
        "media": "world war II 1944 photograph",
        "people": ("Q352", "Q8016", "Q855", "Q40025", "Q9916", "Q2188"),
        "wars": ("Q362", "Q189266", "Q154720"),  # WWII, Pacific, Eastern Front
    },
    "cold": {
        "emoji": "🧊",
        "title": "Guerra fredda",
        "years": "1947–1991",
        "start": 1947,
        "end": 1991,
        "qid": "Q8683",
        "wiki": "Guerra_fredda",
        "media": "cold war berlin wall sputnik 1962",
        "people": ("Q855", "Q8007", "Q44306", "Q1124"),  # Stalin, Kennedy, Gorbaciov, Che?
        "wars": ("Q8663", "Q8740", "Q37643"),  # Corea, Vietnam, Afghanistan 1979
    },
    "con": {
        "emoji": "🌐",
        "title": "Età contemporanea",
        "years": "dal 1945",
        "start": 1945,
        "end": 2026,
        "qid": "Q6495391",
        "wiki": "Età_contemporanea",
        "media": "united nations contemporary history 1990",
        "people": ("Q44306", "Q1124", "Q8023"),
    },
    "spa": {
        "emoji": "🚀",
        "title": "Era spaziale",
        "years": "dal 1957",
        "start": 1957,
        "end": 2026,
        "qid": "Q938328",
        "wiki": "Era_spaziale",
        "media": "space race apollo sputnik nasa",
        "people": ("Q43316", "Q1615", "Q44078"),  # Gagarin, von Braun, Armstrong
    },
    "dig": {
        "emoji": "💻",
        "title": "Era digitale",
        "years": "dal 1970 circa",
        "start": 1970,
        "end": 2026,
        "qid": "Q956129",
        "wiki": "Società_dell'informazione",
        "media": "personal computer internet 1990s digital",
        "people": ("Q5284", "Q80", "Q92"),  # Turing, Berners-Lee, Gates
    },
}

ERA_ORDER = (
    "pre", "ant", "gre", "rom", "tarda", "med", "rin", "mod",
    "riv", "ind", "xix", "ww1", "int", "ww2", "cold", "con", "spa", "dig",
)


def era_by_id(eid: str) -> dict[str, Any] | None:
    row = ERAS.get(eid)
    if not row:
        return None
    return {"id": eid, **row}


def all_eras() -> list[dict[str, Any]]:
    return [era_by_id(eid) for eid in ERA_ORDER if era_by_id(eid)]
