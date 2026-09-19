"""Tastiere inline: home a sei mondi e schede."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from services.catalog import related_items
from services.live import REGIONS
from services.models import WORLDS


def kb_btn(label: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(label, callback_data=data)


def nav_row() -> list[InlineKeyboardButton]:
    return [kb_btn("⬅️ Indietro", "nav:back"), kb_btn("🏠 Inizio", "home:menu")]


def _pairs(items: list[InlineKeyboardButton]) -> list[list[InlineKeyboardButton]]:
    rows: list[list[InlineKeyboardButton]] = []
    pair: list[InlineKeyboardButton] = []
    for btn in items:
        pair.append(btn)
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    return rows


def home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [kb_btn("📡 Posizioni live · aerei, navi, ISS", "home:live")],
            [kb_btn("⚔️ Epoche", "world:epoche"), kb_btn("🗺️ Campi", "world:campi")],
            [kb_btn("🪖 Truppe", "world:truppe"), kb_btn("🏳️ Bandiere", "world:bandiere")],
            [kb_btn("⚙️ Ferro", "world:ferro"), kb_btn("🕊️ Patti", "world:patti")],
            [kb_btn("📖 Oggi", "home:oggi"), kb_btn("🎲 Casuale", "home:random")],
            [kb_btn("🔍 Cerca", "home:cerca"), kb_btn("🎲 Quiz", "home:quiz")],
            [kb_btn("🧭 Esplora", "home:esplora")],
        ]
    )


def esplora_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [kb_btn("⚔️ Epoche", "world:epoche"), kb_btn("🗺️ Campi", "world:campi")],
            [kb_btn("🪖 Truppe", "world:truppe"), kb_btn("🏳️ Bandiere", "world:bandiere")],
            [kb_btn("⚙️ Ferro", "world:ferro"), kb_btn("🕊️ Patti", "world:patti")],
            [kb_btn("📡 Posizioni live", "home:live")],
            nav_row(),
        ]
    )


def world_keyboard(key: str) -> InlineKeyboardMarkup:
    extra = {
        "epoche": [
            [kb_btn("🏛️ Antichità", "l:war:ant"), kb_btn("🏰 Medioevo", "l:war:med")],
            [kb_btn("⚔️ Età moderna", "l:war:mod"), kb_btn("🌍 Contemporanea", "l:war:con")],
            [kb_btn("📚 Tutte le guerre", "l:war:all")],
        ],
        "campi": [
            [kb_btn("🏛️ Antiche", "l:bat:ant"), kb_btn("🏰 Medievali", "l:bat:med")],
            [kb_btn("⚔️ Moderne", "l:bat:mod"), kb_btn("🌍 Contemporanee", "l:bat:con")],
            [kb_btn("🗺️ Tutte le battaglie", "l:bat:all")],
        ],
        "truppe": [
            [kb_btn("🪖 Ruoli", "l:role:all"), kb_btn("🎖️ Gradi", "l:rank:all")],
            [kb_btn("🪜 Scala dei gradi", "l:rank:scale")],
        ],
        "bandiere": [
            [kb_btn("🇮🇹 Italia", "e:italia"), kb_btn("🇫🇷 Francia", "e:francia")],
            [kb_btn("🇬🇧 Regno Unito", "e:uk"), kb_btn("🇺🇸 Stati Uniti", "e:usa")],
            [kb_btn("🐺 Roma", "e:roma"), kb_btn("🟦 NATO", "e:nato")],
            [kb_btn("🏳️ Tutte le schede", "l:army:all")],
        ],
        "ferro": [
            [kb_btn("🛡️ Equipaggiamento", "l:gear:all"), kb_btn("🚁 Mezzi", "l:vehicle:all")],
            [kb_btn("🏰 Fortificazioni", "l:fort:all")],
            [kb_btn("🚙 Terra", "e:t34"), kb_btn("✈️ Aria", "e:spitfire")],
            [kb_btn("⚓ Mare", "e:portaerei"), kb_btn("🚀 Spazio", "e:satcom")],
            [kb_btn("📡 Posizioni live", "home:live")],
        ],
        "patti": [
            [kb_btn("📜 Documenti", "l:doc:all"), kb_btn("🕊️ Pace", "l:peace:all")],
            [kb_btn("👤 Personaggi", "l:person:all"), kb_btn("🧠 Strategia", "l:idea:all")],
        ],
    }[key]
    rows = extra + [[kb_btn("🎲 Casuale qui", f"rnd:{key}")], nav_row()]
    return InlineKeyboardMarkup(rows)


def list_keyboard(rows: list[dict], *, prefix: str = "e:") -> InlineKeyboardMarkup:
    buttons = [kb_btn(f"{item['emoji']} {item['title']}", f"{prefix}{item['id']}") for item in rows[:40]]
    grid = _pairs(buttons)
    grid.append(nav_row())
    return InlineKeyboardMarkup(grid)


def entity_keyboard(item: dict) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    sections = tuple(item.get("sections") or ())[:4]
    section_btns = [
        kb_btn(title, f"s:{item['id']}:{i}")
        for i, (title, _body) in enumerate(sections)
    ]
    if section_btns:
        rows.extend(_pairs(section_btns))
    rel = related_items(item)
    if rel:
        rel_btns = [kb_btn(f"{r['emoji']} {r['title']}", f"e:{r['id']}") for r in rel[:6]]
        rows.extend(_pairs(rel_btns))
    world = item.get("world") or "epoche"
    meta = WORLDS[world]
    rows.append([kb_btn(f"{meta['emoji']} {meta['title']}", f"world:{world}"), kb_btn("🎲 Un'altra", "home:random")])
    rows.append(nav_row())
    return InlineKeyboardMarkup(rows)


def rank_scale_keyboard() -> InlineKeyboardMarkup:
    order = ("soldato", "caporale", "sergente", "tenente", "capitano", "maggiore", "colonnello", "generale")
    labels = ("🪖 Soldato", "🎖️ Caporale", "⭐ Sergente", "🎖️ Tenente", "⭐ Capitano", "⭐⭐ Maggiore", "⭐⭐⭐ Colonnello", "⭐⭐⭐⭐ Generale")
    buttons = [kb_btn(label, f"e:{eid}") for label, eid in zip(labels, order)]
    grid = _pairs(buttons)
    grid.append(nav_row())
    return InlineKeyboardMarkup(grid)


def quiz_hub_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [kb_btn("🧠 Guerra", "q:war"), kb_btn("🗺️ Battaglia", "q:bat")],
            [kb_btn("🎖️ Grado", "q:rank"), kb_btn("🚁 Mezzo", "q:veh")],
            [kb_btn("🏳️ Nazione", "q:nat"), kb_btn("👤 Personaggio", "q:per")],
            [kb_btn("📜 Trattato", "q:trt"), kb_btn("📅 Anno", "q:year")],
            [kb_btn("⚔️ Vero o falso", "q:tf"), kb_btn("🎯 10 domande", "q:10")],
            nav_row(),
        ]
    )


def quiz_options_keyboard(n: int) -> InlineKeyboardMarkup:
    labels = ("A", "B", "C", "D")
    buttons = [kb_btn(labels[i], f"qa:{i}") for i in range(min(n, 4))]
    return InlineKeyboardMarkup([buttons, nav_row()])


def after_quiz_keyboard(eid: str | None) -> InlineKeyboardMarkup:
    rows = [[kb_btn("➡️ Prossima", "q:again"), kb_btn("🎲 Quiz", "home:quiz")]]
    if eid:
        rows.insert(0, [kb_btn("📖 Scheda", f"e:{eid}")])
    rows.append(nav_row())
    return InlineKeyboardMarkup(rows)


def back_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([nav_row()])


def live_hub_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [kb_btn("🔄 Aggiorna posizioni", "home:live")],
            [kb_btn("✈️ Aerei Italia", "live:ac:it"), kb_btn("🌊 Mediterraneo", "live:ac:med")],
            [kb_btn("🚁 Elicotteri", "live:heli:it"), kb_btn("⚓ Navi Baltico", "live:ships")],
            [kb_btn("🛰️ Mappa ISS", "live:iss")],
            nav_row(),
        ]
    )


def live_region_keyboard(kind: str, region: str) -> InlineKeyboardMarkup:
    region_btns = [
        kb_btn(f"{cfg['emoji']} {cfg['title']}", f"live:{kind}:{key}") for key, cfg in REGIONS.items()
    ]
    rows = _pairs(region_btns)
    if kind == "heli":
        rows.append(
            [
                kb_btn("✈️ Tutti gli aerei", f"live:ac:{region}"),
                kb_btn("🔄 Aggiorna", f"live:heli:{region}"),
            ]
        )
    else:
        rows.append(
            [
                kb_btn("🚁 Solo elicotteri", f"live:heli:{region}"),
                kb_btn("🔄 Aggiorna", f"live:ac:{region}"),
            ]
        )
    rows.append([kb_btn("⚓ Navi", "live:ships"), kb_btn("🛰️ ISS", "live:iss")])
    rows.append([kb_btn("📡 Posizioni live", "home:live")])
    rows.append(nav_row())
    return InlineKeyboardMarkup(rows)


def live_misc_keyboard(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [kb_btn("🔄 Aggiorna", token), kb_btn("✈️ Aerei", "live:ac:it")],
            [kb_btn("⚓ Navi", "live:ships"), kb_btn("🛰️ ISS", "live:iss")],
            [kb_btn("📡 Posizioni live", "home:live")],
            nav_row(),
        ]
    )
