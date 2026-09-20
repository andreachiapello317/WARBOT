"""Handler Telegram EARTH."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from core.session import city_label, get_city
from worlds.earth.menu import menu_keyboard, menu_text, results_keyboard
from worlds.earth.queries import get_query, run_query
from worlds.earth.service import format_earth
from worlds.runtime import run_world_query, show_world_menu, show_world_page


async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    city = get_city(context)
    if not city:
        from worlds.city import show_city_prompt

        await show_city_prompt(update, context)
        return
    await show_world_menu(update, context, world_id="earth", menu_text=menu_text(city), menu_keyboard=menu_keyboard())


async def show_query(update: Update, context: ContextTypes.DEFAULT_TYPE, query_id: str) -> None:
    city = get_city(context)
    if not city or not get_query(query_id):
        await show_menu(update, context)
        return
    await run_world_query(
        update,
        context,
        world_id="earth",
        query_id=query_id,
        run=run_query,
        format_result=format_earth,
        wait_text=f"⏳ EARTH · {city_label(city)}…",
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
            world_id="earth",
            query_id=action,
            page=int(rest[1]),
            format_result=format_earth,
            results_keyboard=results_keyboard,
            rerun=show_query,
        )
        return
    if get_query(action):
        await show_query(update, context, action)
        return
    await show_menu(update, context)
