"""Schema delle sale EPOCHE e costruttore delle schede curate."""

from __future__ import annotations

from typing import Any

FACETS: tuple[tuple[str, str, str], ...] = (
    ("tl", "📅", "Cronologia"),
    ("civ", "👑", "Civiltà e imperi"),
    ("war", "⚔️", "Guerre"),
    ("arm", "🪖", "Eserciti"),
    ("ppl", "👤", "Personaggi"),
    ("ter", "🗺️", "Territori"),
    ("cty", "🏛️", "Città"),
    ("sci", "🔬", "Scienza"),
    ("art", "🎨", "Arte"),
    ("lit", "📚", "Letteratura"),
    ("rel", "⛪", "Religioni"),
    ("eco", "💰", "Economia"),
    ("tec", "⚙️", "Tecnologia"),
    ("trn", "🚢", "Trasporti"),
    ("arc", "🏰", "Architettura"),
    ("plc", "🧭", "Luoghi"),
    ("doc", "📜", "Documenti"),
    ("img", "📸", "Immagini"),
)

FACET_EMOJI = {key: emoji for key, emoji, _title in FACETS}
FACET_TITLE = {key: title for key, _emoji, title in FACETS}


def C(
    id: str,
    era: str,
    kind: str,
    title: str,
    years: str,
    summary: str,
    *,
    start: int | None = None,
    end: int | None = None,
    qid: str = "",
    src: tuple[str, ...] = (),
    url: str = "",
    media: str = "",
    related: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "id": id,
        "era": era,
        "kind": kind,
        "title": title,
        "years": years,
        "start": start,
        "end": end,
        "summary": summary.strip(),
        "qid": qid,
        "src": src,
        "url": url,
        "media": media or title,
        "related": related,
        "db": "warbot",
        "emoji": FACET_EMOJI.get(kind, "📖"),
        "world": "epoche",
        "subtitle": years,
    }
