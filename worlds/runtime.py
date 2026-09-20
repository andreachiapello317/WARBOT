"""Handler generico per mondi a query: menu → attesa → risultati → pagine in sessione."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from telegram import InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from core.pagination import DEFAULT_PAGE_SIZE, clamp_page
from core.session import city_label, get_city, set_screen, set_world, world_state
from core.telegram import deliver

log = logging.getLogger("warbot.world")

RunFn = Callable[[dict[str, Any], str], dict[str, Any]]
FormatFn = Callable[..., str]
KeyboardFn = Callable[..., InlineKeyboardMarkup]


async def show_world_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    world_id: str,
    menu_text: str,
    menu_keyboard: InlineKeyboardMarkup,
) -> None:
    city = get_city(context)
    if not city:
        from worlds.city import show_city_prompt

        await show_city_prompt(update, context)
        return
    set_world(context, world_id)
    set_screen(context, f"{world_id}_menu")
    log.info("[WORLD] world=%s menu city=%s", world_id, city_label(city))
    await deliver(update, context, menu_text, reply_markup=menu_keyboard)


async def run_world_query(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    world_id: str,
    query_id: str,
    run: RunFn,
    format_result: FormatFn,
    wait_text: str,
    wait_keyboard: InlineKeyboardMarkup,
    results_keyboard: KeyboardFn,
    page_size: int = DEFAULT_PAGE_SIZE,
    rows_key: str = "rows",
) -> None:
    city = get_city(context)
    if not city:
        from worlds.city import show_city_prompt

        await show_city_prompt(update, context)
        return
    log.info("[WORLD] world=%s query=%s city=%s", world_id, query_id, city_label(city))
    await deliver(update, context, wait_text, reply_markup=wait_keyboard)
    bundle = await asyncio.to_thread(run, city, query_id)
    state = world_state(context, world_id)
    state["bundle"] = bundle
    state["query"] = query_id
    state["page"] = 0
    state["city_lat"] = city.get("lat")
    state["city_lon"] = city.get("lon")
    set_world(context, world_id)
    set_screen(context, f"{world_id}_results")
    rows = list(bundle.get(rows_key) or [])
    text = format_result(bundle, city, offset=0, limit=page_size)
    await deliver(
        update,
        context,
        text,
        reply_markup=results_keyboard(bundle, page=0, query_id=query_id, error=not bundle.get("ok"), rows=rows),
    )


async def show_world_page(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    world_id: str,
    query_id: str,
    page: int,
    format_result: FormatFn,
    results_keyboard: KeyboardFn,
    rerun: Callable[..., Awaitable[None]],
    page_size: int = DEFAULT_PAGE_SIZE,
    rows_key: str = "rows",
) -> None:
    city = get_city(context)
    state = world_state(context, world_id)
    bundle = state.get("bundle")
    qid = query_id or state.get("query")
    same_city = (
        city
        and state.get("city_lat") == city.get("lat")
        and state.get("city_lon") == city.get("lon")
    )
    if not isinstance(bundle, dict) or not city or not same_city or not qid:
        await rerun(update, context, qid or query_id)
        return
    rows = list(bundle.get(rows_key) or [])
    page = clamp_page(page, len(rows), page_size)
    state["page"] = page
    set_screen(context, f"{world_id}_results")
    text = format_result(bundle, city, offset=page * page_size, limit=page_size)
    await deliver(
        update,
        context,
        text,
        reply_markup=results_keyboard(bundle, page=page, query_id=qid, error=not bundle.get("ok"), rows=rows),
    )
