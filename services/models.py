"""Modello comune delle schede enciclopediche."""

from __future__ import annotations

from typing import Any


DISCLAIMER = (
    "Museo di storia militare. Testi descrittivi e pubblici: "
    "non è un manuale operativo e non insegna a combattere."
)


def card(
    *,
    id: str,
    kind: str,
    world: str,
    emoji: str,
    title: str,
    subtitle: str = "",
    era: str = "",
    tags: tuple[str, ...] = (),
    aliases: tuple[str, ...] = (),
    summary: str,
    fields: tuple[tuple[str, str], ...] = (),
    sections: tuple[tuple[str, str], ...] = (),
    related: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "id": id,
        "kind": kind,
        "world": world,
        "emoji": emoji,
        "title": title,
        "subtitle": subtitle,
        "era": era,
        "tags": tags,
        "aliases": aliases,
        "summary": summary,
        "fields": fields,
        "sections": sections,
        "related": related,
    }


KIND_LABELS = {
    "war": ("🏛️", "Guerra"),
    "battle": ("⚔️", "Battaglia"),
    "role": ("🪖", "Ruolo"),
    "rank": ("🎖️", "Grado"),
    "army": ("🏳️", "Forza armata"),
    "gear": ("🛡️", "Equipaggiamento"),
    "vehicle": ("🚁", "Mezzo"),
    "fort": ("🏰", "Fortificazione"),
    "person": ("👤", "Personaggio"),
    "doc": ("📜", "Documento"),
    "peace": ("🕊️", "Pace"),
    "idea": ("🧠", "Concetto"),
}

ERA_LABELS = {
    "ant": ("🏛️", "Antichità"),
    "med": ("🏰", "Medioevo"),
    "mod": ("⚔️", "Età moderna"),
    "con": ("🌍", "Età contemporanea"),
}

WORLDS = {
    "epoche": {
        "emoji": "⚔️",
        "title": "EPOCHE",
        "blurb": "Schede curate di storia, con fonti d'archivio.",
        "kinds": ("war",),
    },
    "campi": {
        "emoji": "🗺️",
        "title": "CAMPI",
        "blurb": "Battaglie documentate, con fasi e conseguenze.",
        "kinds": ("battle",),
    },
    "truppe": {
        "emoji": "🪖",
        "title": "TRUPPE",
        "blurb": "Ruoli del soldato e gradi, ieri e oggi.",
        "kinds": ("role", "rank"),
    },
    "bandiere": {
        "emoji": "🏳️",
        "title": "BANDIERE",
        "blurb": "Eserciti, marine, aviazioni: organizzazione pubblica.",
        "kinds": ("army",),
    },
    "ferro": {
        "emoji": "⚙️",
        "title": "FERRO",
        "blurb": "Equipaggiamento, mezzi e fortificazioni nella storia.",
        "kinds": ("gear", "vehicle", "fort"),
    },
    "patti": {
        "emoji": "🕊️",
        "title": "PATTI",
        "blurb": "Trattati, diplomazia, personaggi, strategia come materia storica.",
        "kinds": ("person", "doc", "peace", "idea"),
    },
}
