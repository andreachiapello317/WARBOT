"""Database interno di EPOCHE: schede curate WARBOT.

Le API esterne arricchiscono immagini e documenti; Wikidata resta un grafo opzionale.
"""

from __future__ import annotations

from typing import Any

from services.history.cards_ancient import CARDS as ANCIENT
from services.history.cards_middle import CARDS as MIDDLE
from services.history.cards_recent import CARDS as RECENT
from services.history.pack import FACET_EMOJI, FACET_TITLE, FACETS
from services.history.sources import resolve_sources

CARDS: tuple[dict[str, Any], ...] = tuple(ANCIENT + MIDDLE + RECENT)
BY_ID: dict[str, dict[str, Any]] = {row["id"]: row for row in CARDS}

ERA_PAGES: dict[str, dict[str, Any]] = {
    "pre": {
        "essay": (
            "Prima della scrittura la storia è scavo: pollini, selci, ossa, pitture. "
            "WARBOT non inventa re preistorici: tiene oggetti di museo (British Museum, Smithsonian) "
            "e campagne di scavo pubblicate. La violenza organizzata compare con i villaggi, "
            "non come destino eterno. Lascaux, Çatalhöyük, Ötzi sono documenti, non costume."
        ),
        "src": ("bm", "si", "loc", "europeana"),
    },
    "ant": {
        "essay": (
            "L'Antichità inizia quando un palazzo tiene i conti su tavoletta o papiro. "
            "Egitto e Mesopotamia costruiscono Stati-fiume; gli annali di guerra sono stele, non giornali. "
            "Le schede citano lastre del British Museum, calchi LoC, testi su Internet Archive. "
            "Wikidata, se c'è, è solo il filo tra un Q-id e un'altra sala."
        ),
        "src": ("bm", "loc", "ia", "europeana"),
    },
    "gre": {
        "essay": (
            "Le poleis combattono fra loro e contro l'impero persiano; Tucidide scrive mentre Atene perde. "
            "Oplita e trireme sono oggetti di vetrina. Il Partenone è anche tesoro della Lega. "
            "Fonti: marmi e vasi al British Museum, manoscritti su Internet Archive, stampe LoC."
        ),
        "src": ("bm", "ia", "loc", "europeana"),
    },
    "rom": {
        "essay": (
            "Roma passa da milizia cittadina a impero di province e di grano. "
            "Polibio, epigrafi, colonna Traiana: tre linguaggi per la stessa macchina. "
            "La legione in queste sale è un'istituzione da museo, non un regolamento."
        ),
        "src": ("bm", "loc", "ia", "europeana"),
    },
    "tarda": {
        "essay": (
            "Costantinopoli tiene; l'Occidente si frammenta in regni su popolazioni romane. "
            "Codici, mosaici, Notitia: fonti normative e visive. Giustiniano riconquista e svuota. "
            "Europeana e LoC tengono Ravenna e le edizioni dei giuristi."
        ),
        "src": ("europeana", "loc", "ia", "bm"),
    },
    "med": {
        "essay": (
            "Il Medioevo è plurale: cristianità latina, islam, steppe, comuni. "
            "Crociate e guerra dei cent'anni hanno cronache, processi, cartulari. "
            "TNA, LoC e Internet Archive tengono i testi; i musei tengono armature e miniature. "
            "Non è un tunnel buio e non è un romanzo unico."
        ),
        "src": ("tna", "loc", "ia", "europeana", "bm"),
    },
    "rin": {
        "essay": (
            "Umanesimo e guerre d'Italia nello stesso cantiere. Stampa, bastioni, argento americano. "
            "Machiavelli e Leonardo sono carte d'archivio prima che poster. "
            "Carlo V tiene un atlante di corone; Roma nel 1527 brucia."
        ),
        "src": ("loc", "europeana", "ia", "si"),
    },
    "mod": {
        "essay": (
            "Westfalia, eserciti permanenti, compagnie delle Indie, Versailles. "
            "Lo Stato fiscale-militare impara a tassare e a stampare gazzette. "
            "Vauban è un documento di ingegneria storica. I trattati hanno testo e data."
        ),
        "src": ("tna", "loc", "ia", "europeana"),
    },
    "riv": {
        "essay": (
            "Due rive atlantiche: indipendenza americana e Francia in rivoluzione, poi Napoleone. "
            "Costituzioni, levée, bollettini. LoC e NARA per Washington; IWM e Europeana per Waterloo. "
            "L'età delle rivoluzioni è un'età di carta pubblica."
        ),
        "src": ("loc", "nara", "iwm", "europeana", "tna"),
    },
    "ind": {
        "essay": (
            "Vapore, orario, impero. La fabbrica cambia la guerra prima delle trincee: ferrovie, fucili, inchieste parlamentari. "
            "Smithsonian tiene le macchine; TNA i blue books; Marx legge lo stesso fumo da un altro banco."
        ),
        "src": ("si", "tna", "loc", "ia"),
    },
    "xix": {
        "essay": (
            "Nazioni, fotografie, secessione americana, Sedan. Brady e Fenton rendono la guerra riproducibile. "
            "Library of Congress e NARA sono l'archivio di questo secolo visivo. Bismarck e Garibaldi sono stampe datate."
        ),
        "src": ("loc", "nara", "dpla", "europeana", "iwm"),
    },
    "ww1": {
        "essay": (
            "Guerra industriale: trincea, manifesto, film ufficiale della Somme. "
            "Imperial War Museums e The National Archives (UK) sono le fonti primarie di questa sala; "
            "LoC e Europeana le allargano. Ogni oggetto ha inventario. Non è un manuale di trincea."
        ),
        "src": ("iwm", "tna", "loc", "europeana"),
    },
    "int": {
        "essay": (
            "Tra due fuochi: debiti, radio, Spagna, riarmo. La Depressione si fotografa (FSA/LoC); "
            "i cinegiornali IWM tengono le parate. Versailles si sfalda a tavolino prima che in campo."
        ),
        "src": ("iwm", "loc", "nara", "europeana"),
    },
    "ww2": {
        "essay": (
            "Guerra totale, Shoah, due teatri. Le schede nascono da IWM, NARA, TNA, Library of Congress: "
            "fotografie con record number, processi, diari. Wikidata non racconta Stalingrado: lo fanno le lastre. "
            "Enciclopedia con fonte, data e originale. Non è un simulatore."
        ),
        "src": ("iwm", "nara", "tna", "loc", "europeana"),
    },
    "cold": {
        "essay": (
            "Blocco, Corea, Cuba, Vietnam, Muro. Dossier declassificati (NARA), foto NASA della corsa spaziale, "
            "manifesti IWM. La guerra fredda è un'età di archivi oggi aperti, non di mappe da usare."
        ),
        "src": ("nara", "iwm", "nasa", "loc"),
    },
    "con": {
        "essay": (
            "Dopo i blocchi: ONU, decolonizzazione, Sarajevo, memoriali. "
            "Fonti con URL stabile — IWM, LoC, Europeana — meglio dei telegiornali senza scheda. "
            "Il contemporaneo si racconta con data, non con l'ultima breaking news."
        ),
        "src": ("iwm", "loc", "europeana", "nara"),
    },
    "spa": {
        "essay": (
            "Sputnik, Gagarin, Apollo, ISS. La fonte principale è NASA Image and Video Library: "
            "ogni lastra ha id, missione, data. ESA per l'Europa, Smithsonian per gli oggetti. "
            "Lo spazio in WARBOT è museo e orbita (Posizioni live per l'ISS), non targeting."
        ),
        "src": ("nasa", "esa", "si", "loc"),
    },
    "dig": {
        "essay": (
            "Dal 4004 al web: oggetti di museo e snapshot di Internet Archive. "
            "Turing è biografia e TNA; Berners-Lee è un documento CERN. "
            "L'epoca digitale si cita con identificativo di item, non con un feed anonimo."
        ),
        "src": ("si", "ia", "loc", "tna"),
    },
}


def all_cards() -> list[dict[str, Any]]:
    return list(CARDS)


def card_by_id(cid: str) -> dict[str, Any] | None:
    return BY_ID.get(cid)


def cards_for(era_id: str, kind: str | None = None) -> list[dict[str, Any]]:
    rows = [row for row in CARDS if row["era"] == era_id]
    if kind:
        rows = [row for row in rows if row["kind"] == kind]
    return sorted(rows, key=lambda r: (r.get("start") is None, r.get("start") if r.get("start") is not None else 0, r["title"]))


def timeline_cards(era_id: str) -> list[dict[str, Any]]:
    rows = [row for row in CARDS if row["era"] == era_id and row.get("start") is not None]
    return sorted(rows, key=lambda r: (r["start"], r.get("end") if r.get("end") is not None else r["start"], r["title"]))


def related_cards(card: dict[str, Any], *, limit: int = 6) -> list[dict[str, Any]]:
    explicit = [BY_ID[cid] for cid in card.get("related") or () if cid in BY_ID]
    others = [row for row in CARDS if row["era"] == card["era"] and row["id"] != card["id"]]
    start = card.get("start")
    if start is not None:
        others.sort(key=lambda r: abs((r.get("start") if r.get("start") is not None else start) - start))
    seen = {card["id"]}
    out = []
    for row in explicit + others:
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        out.append(row)
        if len(out) >= limit:
            break
    return out


def page_for(era_id: str) -> dict[str, Any]:
    return ERA_PAGES.get(era_id) or {"essay": "", "src": ()}


def counts_for(era_id: str) -> dict[str, int]:
    out = {key: 0 for key, _e, _t in FACETS}
    for row in CARDS:
        if row["era"] == era_id and row["kind"] in out:
            out[row["kind"]] += 1
    return out


def search_cards(query: str, *, limit: int = 12) -> list[dict[str, Any]]:
    q = query.strip().lower()
    if len(q) < 2:
        return []
    scored: list[tuple[int, dict[str, Any]]] = []
    for row in CARDS:
        blob = " ".join(
            [
                row["id"],
                row["title"],
                row.get("years") or "",
                row.get("summary") or "",
                row.get("kind") or "",
            ]
        ).lower()
        score = 0
        if q == row["title"].lower() or q == row["id"]:
            score = 100
        elif q in row["title"].lower():
            score = 80
        elif q in blob:
            score = 40 + blob.count(q)
        if score:
            scored.append((score, row))
    scored.sort(key=lambda pair: (-pair[0], pair[1]["title"]))
    return [row for _score, row in scored[:limit]]


def decorate(card: dict[str, Any]) -> dict[str, Any]:
    row = dict(card)
    row["sources"] = resolve_sources(card.get("src") or ())
    row["emoji"] = FACET_EMOJI.get(card["kind"], "📖")
    row["kind_title"] = FACET_TITLE.get(card["kind"], card["kind"])
    return row


__all__ = [
    "BY_ID",
    "CARDS",
    "ERA_PAGES",
    "FACETS",
    "card_by_id",
    "cards_for",
    "counts_for",
    "decorate",
    "page_for",
    "related_cards",
    "search_cards",
    "timeline_cards",
]
