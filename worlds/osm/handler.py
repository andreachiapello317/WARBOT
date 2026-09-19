"""Handler Telegram del mondo OSM. Overpass solo sulle query, mai sul menu."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from core.session import (
    SCREEN_OSM_ITEM,
    SCREEN_OSM_MENU,
    SCREEN_OSM_NEAR,
    SCREEN_OSM_RESULTS,
    get_city,
    osm_state,
    set_screen,
    set_world,
)
from core.telegram import deliver
from services.live.engine import timed
from services.live.osm import (
    CATEGORIES,
    LIST_LIMIT,
    format_osm_category,
    format_osm_item,
    format_osm_item_map,
    format_osm_item_tags,
    format_osm_map,
    format_osm_nearby_menu,
)
from worlds.city import show_city_prompt
from worlds.osm.menu import (
    item_keyboard,
    item_side_keyboard,
    menu_keyboard,
    menu_text,
    nearby_keyboard,
    results_keyboard,
)
from worlds.osm.queries import engine_id, peek_query, public_id, run_near, run_query

log = logging.getLogger("warbot.osm")


def _filt(state: dict[str, Any]) -> dict[str, str]:
    raw = state.get("filt")
    return dict(raw) if isinstance(raw, dict) else {}


def _search_kwargs(state: dict[str, Any], cat: str) -> dict[str, Any]:
    filt = _filt(state)
    kwargs: dict[str, Any] = {"extra": ""}
    bits: list[str] = []
    if cat == "rail":
        if filt.get("rail") == "all":
            kwargs["min_score"] = 0
            bits.append("all")
        if filt.get("scope") == "ctr":
            kwargs["radius_m"] = 6000
            bits.append("ctr")
        elif filt.get("scope") == "wide":
            kwargs["radius_m"] = 20000
            bits.append("wide")
    if cat == "aero":
        if filt.get("aero") == "any":
            kwargs["min_score"] = 0
            bits.append("any")
        elif filt.get("aero") == "near":
            kwargs["radius_m"] = 22000
            bits.append("anear")
    kwargs["extra"] = ",".join(bits)
    return kwargs


def _current_item(state: dict[str, Any]) -> dict[str, Any] | None:
    rows = state.get("rows")
    idx = state.get("item")
    if isinstance(rows, list) and isinstance(idx, int) and 0 <= idx < len(rows):
        return rows[idx]
    row = state.get("item_row")
    return row if isinstance(row, dict) and "lat" in row else None


async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    city = get_city(context)
    if not city:
        await show_city_prompt(update, context)
        return
    set_world(context, "osm")
    set_screen(context, SCREEN_OSM_MENU)
    log.info("[OSM] menu city=%s", city.get("name"))
    await deliver(update, context, menu_text(city), reply_markup=menu_keyboard())


async def show_query(update: Update, context: ContextTypes.DEFAULT_TYPE, query_id: str) -> None:
    city = get_city(context)
    if not city:
        await show_city_prompt(update, context)
        return
    cat = engine_id(query_id)
    pub = public_id(query_id)
    if not cat or not pub:
        await show_menu(update, context)
        return
    state = osm_state(context)
    extra_kw = _search_kwargs(state, cat)
    extra = str(extra_kw.get("extra") or "")
    log.info("[OSM] category=%s city=%s", cat, city.get("name"))
    bundle = peek_query(city, pub, extra=extra, radius_m=extra_kw.get("radius_m"))
    if bundle is None:
        await deliver(
            update,
            context,
            f"🗺️ <b>OSM WORLD</b>\n\nInterrogo Overpass · {city.get('display') or city.get('name')}…",
            reply_markup=menu_keyboard(),
        )
        bundle = await asyncio.to_thread(
            run_query,
            city,
            pub,
            extra=extra,
            radius_m=extra_kw.get("radius_m"),
            min_score=extra_kw.get("min_score"),
        )
    rows = list(bundle.get("rows") or [])
    state["rows"] = rows
    state["city_rows"] = rows
    state["query"] = pub
    state["city_query"] = pub
    state["page"] = 0
    state["nearby"] = False
    set_screen(context, SCREEN_OSM_RESULTS)
    error = not bundle.get("ok")
    t_tg = time.time()
    await deliver(
        update,
        context,
        format_osm_category(bundle, city, offset=0, limit=LIST_LIMIT),
        reply_markup=results_keyboard(
            rows, page=0, query_id=pub, error=error, filt=_filt(state), nearby=False
        ),
        preview=True,
    )
    timed("telegram", t_tg, cat=cat, n=len(rows), ok=int(not error))


async def show_page(update: Update, context: ContextTypes.DEFAULT_TYPE, query_id: str | None, page: int) -> None:
    city = get_city(context)
    state = osm_state(context)
    rows = state.get("rows")
    pub = public_id(query_id) or public_id(str(state.get("query") or ""))
    if not isinstance(rows, list) or not pub or not city:
        await show_menu(update, context)
        return
    max_page = max(0, (len(rows) - 1) // LIST_LIMIT) if rows else 0
    page = max(0, min(int(page), max_page))
    state["page"] = page
    cat = engine_id(pub)
    meta = {
        "ok": True,
        "rows": rows,
        "title": (CATEGORIES.get(str(cat)) or {}).get("title"),
        "emoji": (CATEGORIES.get(str(cat)) or {}).get("emoji"),
        "total": len(rows),
        "pool": len(rows),
    }
    set_screen(context, SCREEN_OSM_RESULTS)
    await deliver(
        update,
        context,
        format_osm_category(meta, city, offset=page * LIST_LIMIT, limit=LIST_LIMIT),
        reply_markup=results_keyboard(
            rows,
            page=page,
            query_id=pub,
            filt=_filt(state),
            nearby=bool(state.get("nearby")),
        ),
        preview=True,
    )


async def show_item(update: Update, context: ContextTypes.DEFAULT_TYPE, index: int) -> None:
    city = get_city(context)
    state = osm_state(context)
    rows = state.get("rows")
    if not isinstance(rows, list) or index < 0 or index >= len(rows):
        qid = state.get("query")
        if qid:
            await show_query(update, context, str(qid))
            return
        await show_menu(update, context)
        return
    state["item"] = index
    state["item_row"] = rows[index]
    set_screen(context, SCREEN_OSM_ITEM)
    await deliver(
        update,
        context,
        format_osm_item(rows[index], city),
        reply_markup=item_keyboard(),
        preview=True,
    )


async def show_map(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    city = get_city(context)
    if not city:
        await show_city_prompt(update, context)
        return
    await deliver(update, context, format_osm_map(city), reply_markup=menu_keyboard(), preview=True)


async def show_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = osm_state(context)
    city_rows = state.get("city_rows")
    city_query = state.get("city_query")
    if isinstance(city_rows, list) and city_query:
        state["rows"] = city_rows
        state["query"] = city_query
        state["nearby"] = False
        state["page"] = 0
        await show_page(update, context, str(city_query), 0)
        return
    qid = state.get("query")
    if qid:
        await show_query(update, context, str(qid))
        return
    await show_menu(update, context)


async def show_item_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = osm_state(context)
    idx = state.get("item")
    if isinstance(idx, int):
        await show_item(update, context, idx)
        return
    row = _current_item(state)
    if row:
        await deliver(
            update,
            context,
            format_osm_item(row, get_city(context)),
            reply_markup=item_keyboard(),
            preview=True,
        )
        return
    await show_list(update, context)


async def show_item_map(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    row = _current_item(osm_state(context))
    if not row:
        await show_map(update, context)
        return
    await deliver(update, context, format_osm_item_map(row), reply_markup=item_side_keyboard(), preview=True)


async def show_item_tags(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    row = _current_item(osm_state(context))
    if not row:
        await show_list(update, context)
        return
    await deliver(update, context, format_osm_item_tags(row), reply_markup=item_side_keyboard(), preview=True)


async def show_nearby_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, *, zone: bool = False) -> None:
    state = osm_state(context)
    row = _current_item(state)
    if not row:
        await show_menu(update, context)
        return
    set_screen(context, SCREEN_OSM_NEAR)
    await deliver(
        update,
        context,
        format_osm_nearby_menu(row, zone=zone),
        reply_markup=nearby_keyboard(),
        preview=True,
    )


async def show_near_category(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str) -> None:
    state = osm_state(context)
    row = _current_item(state)
    if not row:
        await show_menu(update, context)
        return
    cat = engine_id(category) or category
    await deliver(
        update,
        context,
        f"🗺️ <b>OSM WORLD</b>\n\nVicino a <b>{row.get('name')}</b> · {(CATEGORIES.get(cat) or {}).get('title')}…",
        reply_markup=nearby_keyboard(),
    )
    log.info("[OSM] category=%s near=1", cat)
    bundle = await asyncio.to_thread(run_near, float(row["lat"]), float(row["lon"]), cat, hint=str(row.get("name") or ""))
    rows = list(bundle.get("rows") or [])
    pub = public_id(cat) or cat
    state["rows"] = rows
    state["query"] = pub
    state["page"] = 0
    state["nearby"] = True
    set_screen(context, SCREEN_OSM_RESULTS)
    await deliver(
        update,
        context,
        format_osm_category(bundle, {"display": row.get("name"), "name": row.get("name")}, offset=0, limit=LIST_LIMIT),
        reply_markup=results_keyboard(rows, page=0, query_id=pub, error=not bundle.get("ok"), nearby=True),
        preview=True,
    )


async def apply_filter(update: Update, context: ContextTypes.DEFAULT_TYPE, token: str) -> None:
    state = osm_state(context)
    filt = _filt(state)
    if token == "main":
        filt["rail"] = "main"
    elif token == "all":
        filt["rail"] = "all"
    elif token == "ctr":
        filt["scope"] = "ctr"
    elif token == "wide":
        filt["scope"] = "wide"
    elif token == "pax":
        filt["aero"] = "pax"
    elif token == "any":
        filt["aero"] = "any"
    elif token == "anear":
        filt["aero"] = "near"
    state["filt"] = filt
    qid = state.get("city_query") or state.get("query")
    if qid:
        await show_query(update, context, str(qid))
        return
    await show_menu(update, context)


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE, parts: list[str]) -> None:
    if not parts or parts[0] in {"menu", "here"}:
        await show_menu(update, context)
        return
    action, *rest = parts
    if action == "map":
        await show_map(update, context)
        return
    if action == "imap":
        await show_item_map(update, context)
        return
    if action in {"tags", "osm"}:
        await show_item_tags(update, context)
        return
    if action == "near":
        await show_nearby_menu(update, context, zone=False)
        return
    if action == "zone":
        await show_nearby_menu(update, context, zone=True)
        return
    if action == "n" and rest:
        await show_near_category(update, context, rest[0])
        return
    if action == "f" and rest:
        await apply_filter(update, context, rest[0])
        return
    if action == "backi":
        await show_item_back(update, context)
        return
    if action == "list":
        await show_list(update, context)
        return
    if action == "item" and rest and rest[0].isdigit():
        await show_item(update, context, int(rest[0]))
        return
    if public_id(action):
        if rest and rest[0] == "page" and len(rest) > 1 and rest[1].lstrip("-").isdigit():
            await show_page(update, context, action, int(rest[1]))
            return
        await show_query(update, context, action)
        return
    await show_menu(update, context)
