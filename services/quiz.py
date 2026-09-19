"""Quiz storici costruiti sul catalogo, non su domande operative."""

from __future__ import annotations

import random
from typing import Any

from services.catalog import ALL, KIND_LABELS, by_kind
from services.models import ERA_LABELS


def _opts(correct: str, pool: list[str], k: int = 3) -> list[str]:
    others = [name for name in pool if name != correct]
    random.shuffle(others)
    choices = [correct] + others[:k]
    random.shuffle(choices)
    return choices


def _titles(kind: str) -> list[str]:
    return [item["title"] for item in by_kind(kind)]


def build_quiz(mode: str) -> dict[str, Any] | None:
    builders = {
        "war": _guess_kind("war", "🧠 Indovina la guerra", "Di quale conflitto si parla?"),
        "bat": _guess_kind("battle", "🗺️ Indovina la battaglia", "Quale battaglia è questa?"),
        "rank": _guess_rank,
        "veh": _guess_kind("vehicle", "🚁 Indovina il mezzo", "Che oggetto è?"),
        "nat": _guess_kind("army", "🏳️ Indovina la nazione", "Di quale forza si parla?"),
        "per": _guess_kind("person", "👤 Indovina il personaggio", "Chi è?"),
        "trt": _guess_kind("doc", "📜 Indovina il trattato", "Quale documento è?"),
        "year": _guess_year,
        "tf": _true_false,
        "10": _guess_kind("war", "🎯 Quiz storico", "Di quale conflitto si parla?"),
    }
    fn = builders.get(mode, builders["war"])
    return fn()


def _guess_kind(kind: str, title: str, prompt: str):
    def inner() -> dict[str, Any] | None:
        pool = by_kind(kind)
        if len(pool) < 3:
            pool = list(ALL)
        item = random.choice(pool)
        clue = item["summary"].split(".")[0] + "."
        if item.get("subtitle"):
            clue = f"{item['subtitle']}. {clue}"
        titles = [x["title"] for x in pool if x["kind"] == item["kind"]]
        if len(titles) < 3:
            titles = [x["title"] for x in ALL]
        options = _opts(item["title"], titles)
        return {
            "mode": kind,
            "title": title,
            "prompt": f"{prompt}\n\n{clue}",
            "options": options,
            "answer": item["title"],
            "explain": item["id"],
        }

    return inner


def _guess_rank() -> dict[str, Any] | None:
    ranks = by_kind("rank")
    item = random.choice(ranks)
    field = random.choice(item.get("fields") or (("Italia", item["title"]),))
    prompt = f"🎖️ Quale grado italiano (o analogo) corrisponde a questa riga?\n\n{field[0]}: {field[1]}"
    return {
        "mode": "rank",
        "title": "🎖️ Indovina il grado",
        "prompt": prompt,
        "options": _opts(item["title"], [r["title"] for r in ranks]),
        "answer": item["title"],
        "explain": item["id"],
    }


def _guess_year() -> dict[str, Any] | None:
    dated = [item for item in ALL if any(ch.isdigit() for ch in item.get("subtitle") or "")]
    item = random.choice(dated)
    years = ["490 a.C.", "216 a.C.", "1415", "1571", "1815", "1916", "1942", "1944", "1945", "1957", "1648"]
    sub = item["subtitle"]
    correct = sub.split("·")[0].strip() if "·" in sub else sub.split("–")[0].strip()
    options = _opts(correct, years + [correct])
    return {
        "mode": "year",
        "title": "📅 Indovina l'anno",
        "prompt": f"Quando si colloca <b>{item['title']}</b>?",
        "options": options,
        "answer": correct,
        "explain": item["id"],
    }


def _true_false() -> dict[str, Any] | None:
    facts = [
        ("La battaglia di Waterloo è del 18 giugno 1815.", True, "waterloo"),
        ("Le guerre puniche oppongono Roma a Cartagine.", True, "punic"),
        ("La Linea Maginot fu aggirata nel 1940.", True, "maginot"),
        ("Lo Spitfire è un carro armato sovietico.", False, "spitfire"),
        ("I trattati di Westfalia sono del 1648.", True, "westfalia"),
        ("Stalingrado si trova sul Reno.", False, "stlg"),
        ("La NATO nasce nel 1949.", True, "nato"),
        ("Annibale combatte nelle guerre greco-persiane.", False, "annibale"),
        ("La RAF è l'aeronautica britannica.", True, "raf"),
        ("Il T-34 è un caccia della Battaglia d'Inghilterra.", False, "t34"),
    ]
    text, truth, eid = random.choice(facts)
    return {
        "mode": "tf",
        "title": "⚔️ Vero o falso",
        "prompt": text,
        "options": ["Vero", "Falso"],
        "answer": "Vero" if truth else "Falso",
        "explain": eid,
    }


def format_question(quiz: dict[str, Any]) -> str:
    letters = "ABCD"
    lines = [f"{quiz['title']}", "", quiz["prompt"], ""]
    for i, opt in enumerate(quiz["options"]):
        lines.append(f"{letters[i]}) {opt}")
    return "\n".join(lines)


def kind_count() -> str:
    bits = []
    for kind, (em, label) in KIND_LABELS.items():
        n = len(by_kind(kind))
        if n:
            bits.append(f"{em} {label}: {n}")
    eras = " · ".join(f"{em} {name}" for em, name in ERA_LABELS.values())
    return "Schede in museo:\n" + "\n".join(bits) + f"\n\nEre: {eras}"
