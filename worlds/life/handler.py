"""Handler Telegram CITY LIFE."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from core.session import city_label, get_city, get_previous_city
from worlds.life.menu import menu_keyboard, menu_text, results_keyboard
from worlds.life.queries import get_query, run_query
from worlds.life.service import format_life
from worlds.runtime import run_world_query, show_world_menu, show_world_page


async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    city = get_city(context)
    if not city:
        from worlds.city import show_city_prompt

        await show_city_prompt(update, context)
        return
    await show_world_menu(
        update,
        context,
        world_id="life",
        menu_text=menu_text(city),
        menu_keyboard=menu_keyboard(),
    )


async def show_query(update: Update, context: ContextTypes.DEFAULT_TYPE, query_id: str) -> None:
    city = get_city(context)
    if not city or not get_query(query_id):
        await show_menu(update, context)
        return
    other = get_previous_city(context)

    def _run(place: dict, qid: str) -> dict:
        return run_query(place, qid, other=other)

    await run_world_query(
        update,
        context,
        world_id="life",
        query_id=query_id,
        run=_run,
        format_result=format_life,
        wait_text=f"⏳ CITY LIFE · {city_label(city)}…",
        wait_keyboard=menu_keyboard(),
        results_keyboard=results_keyboard,
    )


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE, parts: list[str]) -> None:
    if not parts or parts[0] in {"menu", "here"}:
        await show_menu(update, context)
        return
    action, *rest = parts
    if rest and rest[0] == "page" and len(rest) > 1 and rest[1].lstrip("-").isdigit():
        await show_world_page(
            update,
            context,
            world_id="life",
            query_id=action,
            page=int(rest[1]),
            format_result=format_life,
            results_keyboard=results_keyboard,
            rerun=show_query,
        )
        return
    if get_query(action):
        await show_query(update, context, action)
        return
    await show_menu(update, context)
