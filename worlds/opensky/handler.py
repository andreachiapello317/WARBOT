"""Handler Telegram OPEN SKY. Solo OpenSky, coordinate dalla città già salvata."""

from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from core.session import (
    SCREEN_OPENSKY_MENU,
    SCREEN_OPENSKY_RESULTS,
    city_label,
    get_city,
    opensky_state,
    set_screen,
    set_world,
)
from core.telegram import deliver
from services.live.aircraft import (
    PAGE_SIZE,
    e,
    format_aircraft,
    wait_text,
)
from worlds.city import show_city_prompt
from worlds.opensky.menu import menu_keyboard, menu_text, results_keyboard
from worlds.opensky.queries import get_query, run_aircraft

log = logging.getLogger("warbot.opensky")


def _summary_text(bundle: dict, city: dict) -> str:
    name = city_label(city).upper()
    rows = list(bundle.get("aircraft") or [])
    airborne = sum(1 for r in rows if r.get("on_ground") is False)
    ground = sum(1 for r in rows if r.get("on_ground") is True)
    nearest = min(rows, key=lambda r: float(r.get("distance_km") or 9e9), default=None)
    lines = [
        f"✈️ <b>OPEN SKY — {e(name)}</b>",
        "📡 Traffico aereo",
        "",
        f"🛫 In volo: {airborne}",
        f"🛬 A terra: {ground}",
        f"✈️ Totale: {len(rows)}",
    ]
    if nearest:
        label = nearest.get("callsign") or str(nearest.get("icao24") or "").upper()
        dist = nearest.get("distance_km")
        if isinstance(dist, (int, float)):
            lines.append(f"📍 Più vicino: {e(label)} · {int(round(dist))} km")
    if not rows and bundle.get("ok"):
        lines.append("")
        lines.append("✈️ Nessun aereo rilevato nell'area.")
    return "\n".join(lines)


async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    city = get_city(context)
    if not city:
        await show_city_prompt(update, context)
        return
    set_world(context, "opensky")
    set_screen(context, SCREEN_OPENSKY_MENU)
    log.info("[OPENSKY] menu city=%s", city.get("name"))
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
    log.info("[OPENSKY] query=%s city=%s", meta["id"], city.get("name"))
    await deliver(update, context, wait_text(city), reply_markup=menu_keyboard())
    bundle = await asyncio.to_thread(run_aircraft, city, meta["id"])
    state = opensky_state(context)
    state["bundle"] = bundle
    state["query"] = meta["id"]
    state["page"] = 0
    set_screen(context, SCREEN_OPENSKY_RESULTS)
    rows = list(bundle.get("aircraft") or [])
    error = not bundle.get("ok")
    if meta["mode"] == "summary" and bundle.get("ok"):
        text = _summary_text(bundle, city)
    else:
        text = format_aircraft(bundle, city, offset=0, limit=PAGE_SIZE)
    await deliver(
        update,
        context,
        text,
        reply_markup=results_keyboard(rows, page=0, query_id=meta["id"], error=error),
    )


async def show_page(update: Update, context: ContextTypes.DEFAULT_TYPE, query_id: str, page: int) -> None:
    city = get_city(context)
    state = opensky_state(context)
    bundle = state.get("bundle")
    qid = query_id or state.get("query") or "aircraft"
    if not isinstance(bundle, dict) or not city:
        await show_query(update, context, qid)
        return
    rows = list(bundle.get("aircraft") or [])
    max_page = max(0, (len(rows) - 1) // PAGE_SIZE) if rows else 0
    page = max(0, min(int(page), max_page))
    state["page"] = page
    set_screen(context, SCREEN_OPENSKY_RESULTS)
    meta = get_query(qid)
    if meta and meta.get("mode") == "summary" and bundle.get("ok"):
        text = _summary_text(bundle, city)
    else:
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
