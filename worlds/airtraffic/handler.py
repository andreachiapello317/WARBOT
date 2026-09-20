"""Handler Telegram AIR TRAFFIC. Coordinate dalla città già salvata."""

from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from core.session import (
    SCREEN_AIRTRAFFIC_MENU,
    SCREEN_AIRTRAFFIC_RESULTS,
    city_label,
    get_city,
    airtraffic_state,
    set_screen,
    set_world,
)
from core.telegram import deliver
from services.live.aircraft import (
    PAGE_SIZE,
    format_aircraft,
    wait_text,
)
from worlds.city import show_city_prompt
from worlds.airtraffic.menu import menu_keyboard, menu_text, results_keyboard
from worlds.airtraffic.queries import get_query, run_aircraft

log = logging.getLogger("warbot.airtraffic")


async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    city = get_city(context)
    if not city:
        await show_city_prompt(update, context)
        return
    set_world(context, "airtraffic")
    set_screen(context, SCREEN_AIRTRAFFIC_MENU)
    log.info("[AIRTRAFFIC] menu city=%s", city.get("name"))
    await deliver(update, context, menu_text(city), reply_markup=menu_keyboard())


async def show_query(update: Update, context: ContextTypes.DEFAULT_TYPE, query_id: str) -> None:
    city = get_city(context)
    if not city:
        await show_city_prompt(update, context)
        return
    meta = get_query(query_id)
    if not meta:
        await show_menu(update, context)
        return
    log.info(
        "[AIRTRAFFIC] city=%s lat=%s lon=%s",
        city_label(city),
        city.get("lat"),
        city.get("lon"),
    )
    bundle = await asyncio.to_thread(run_aircraft, city, meta["id"])
    state = airtraffic_state(context)
    state["bundle"] = bundle
    state["query"] = meta["id"]
    state["page"] = 0
    state["city_lat"] = city.get("lat")
    state["city_lon"] = city.get("lon")
    set_screen(context, SCREEN_AIRTRAFFIC_RESULTS)
    rows = list(bundle.get("aircraft") or [])
    error = not bundle.get("ok")
    text = format_aircraft(bundle, city, offset=0, limit=PAGE_SIZE)
    await deliver(
        update,
        context,
        text,
        reply_markup=results_keyboard(rows, page=0, query_id=meta["id"], error=error),
    )


async def show_page(update: Update, context: ContextTypes.DEFAULT_TYPE, query_id: str, page: int) -> None:
    city = get_city(context)
    state = airtraffic_state(context)
    bundle = state.get("bundle")
    qid = query_id or state.get("query") or "aircraft"
    same_city = (
        city
        and state.get("city_lat") == city.get("lat")
        and state.get("city_lon") == city.get("lon")
    )
    if not isinstance(bundle, dict) or not city or not same_city:
        await show_query(update, context, qid)
        return
    rows = list(bundle.get("aircraft") or [])
    max_page = max(0, (len(rows) - 1) // PAGE_SIZE) if rows else 0
    page = max(0, min(int(page), max_page))
    if state.get("page") == page and get_city(context):
        # Stesso tasto «Pagina n/n»: non rifare la query, riedita lo stesso testo.
        set_screen(context, SCREEN_AIRTRAFFIC_RESULTS)
    state["page"] = page
    set_screen(context, SCREEN_AIRTRAFFIC_RESULTS)
    text = format_aircraft(bundle, city, offset=page * PAGE_SIZE, limit=PAGE_SIZE)
    await deliver(
        update,
        context,
        text,
        reply_markup=results_keyboard(rows, page=page, query_id=qid, error=not bundle.get("ok")),
    )


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE, parts: list[str]) -> None:
    if not parts or parts[0] in {"menu", "here"}:
        await show_menu(update, context)
        return
    action, *rest = parts
    if get_query(action):
        if rest and rest[0] == "page" and len(rest) > 1 and rest[1].lstrip("-").isdigit():
            await show_page(update, context, action, int(rest[1]))
            return
        await show_query(update, context, action)
        return
    await show_menu(update, context)
