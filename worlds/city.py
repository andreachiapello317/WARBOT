"""START, geocoding, menu dei mondi. Nessuna query Overpass/ADSB.lol."""

from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from core.session import (
    SCREEN_HITS,
    SCREEN_WORLDS,
    ask_city,
    city_label,
    get_city,
    get_hits,
    set_city,
    set_hits,
    set_screen,
    set_world,
)
from core.telegram import deliver
from services.live.geocode import geocode
from worlds.registry import get_world, world_menu_items

log = logging.getLogger("warbot.city")


def kb(label: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(label, callback_data=data)


def city_prompt_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[kb("❓ Aiuto", "home:aiuto")]])


def hits_keyboard(n: int) -> InlineKeyboardMarkup:
    buttons = [kb(str(i + 1), f"city:pick:{i}") for i in range(max(0, min(n, 5)))]
    rows: list[list[InlineKeyboardButton]] = []
    pair: list[InlineKeyboardButton] = []
    for btn in buttons:
        pair.append(btn)
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    rows.append([kb("📍 Cambia città", "city:ask")])
    return InlineKeyboardMarkup(rows)


def worlds_keyboard() -> InlineKeyboardMarkup:
    rows = [[kb(f"{item['icon']} {item['title']}", item["callback"])] for item in world_menu_items()]
    rows.append([kb("⬅️ Cambia città", "city:ask")])
    return InlineKeyboardMarkup(rows)


def city_prompt_text() -> str:
    return (
        "🌍 <b>WARBOT</b>\n"
        "📍 Inserisci una città o località:"
    )


def city_miss_text(query: str) -> str:
    return (
        "❌ Non riesco a trovare questa località.\n"
        "Prova con:\n"
        "Milano\n"
        "Tokyo\n"
        "New York\n"
        "London"
    )


def format_worlds(city: dict) -> str:
    name = city_label(city) or "qui"
    lines = [
        f"📍 <b>{name}</b>",
        "🌍 Scegli un mondo:",
        "",
    ]
    for item in world_menu_items():
        lines.append(f"{item['icon']} {item['title']}")
        if item.get("description"):
            lines.append(f"<i>{item['description']}</i>")
    return "\n".join(lines)


async def show_city_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ask_city(context)
    set_world(context, None)
    await deliver(update, context, city_prompt_text(), reply_markup=city_prompt_keyboard())


async def show_worlds(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    city = get_city(context)
    if not city:
        await show_city_prompt(update, context)
        return
    set_world(context, None)
    set_screen(context, SCREEN_WORLDS)
    log.info("[WORLD] menu city=%s", city_label(city))
    await deliver(update, context, format_worlds(city), reply_markup=worlds_keyboard())


async def lookup_city(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
    look = (query or "").strip()
    if len(look) < 2:
        await show_city_prompt(update, context)
        return
    log.info("[CITY] geocoding=%s", look)
    await deliver(
        update,
        context,
        f"🌍 <b>WARBOT</b>\n\nCerco <b>{look}</b>…",
        reply_markup=city_prompt_keyboard(),
    )
    result = await _geocode(look)
    if not result.get("ok"):
        ask_city(context)
        await deliver(update, context, city_miss_text(look), reply_markup=city_prompt_keyboard())
        return
    hits = list(result.get("hits") or [])
    set_hits(context, hits)
    if len(hits) == 1:
        set_city(context, hits[0])
        await show_worlds(update, context)
        return
    if not hits:
        ask_city(context)
        await deliver(update, context, city_miss_text(look), reply_markup=city_prompt_keyboard())
        return
    set_screen(context, SCREEN_HITS)
    lines = [
        "🌍 <b>WARBOT</b>",
        f"🔎 Più di un risultato per «{look}». Tocca il luogo.",
        "",
    ]
    for i, hit in enumerate(hits[:5], 1):
        lines.append(f"{i}. <b>{hit.get('display') or hit.get('name')}</b>")
        lines.append(f"{float(hit['lat']):.3f}, {float(hit['lon']):.3f}")
    await deliver(update, context, "\n".join(lines), reply_markup=hits_keyboard(len(hits)))


async def pick_city(update: Update, context: ContextTypes.DEFAULT_TYPE, index: int) -> None:
    hits = get_hits(context)
    if 0 <= index < len(hits):
        set_city(context, hits[index])
        await show_worlds(update, context)
        return
    await show_city_prompt(update, context)


async def open_world(update: Update, context: ContextTypes.DEFAULT_TYPE, world_id: str) -> None:
    if not get_city(context):
        await show_city_prompt(update, context)
        return
    world = get_world(world_id)
    if not world:
        await show_worlds(update, context)
        return
    set_world(context, world.id)
    await world.show_menu(update, context)


async def _geocode(query: str):
    import asyncio

    return await asyncio.to_thread(geocode, query)
