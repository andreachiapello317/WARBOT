#!/usr/bin/env python3
"""
WARBOT — museo Telegram di storia militare.

Stessa architettura di un bot a mondi e un solo messaggio in chat:
tastiere inline, callback a prefisso, Indietro/Inizio, webhook o polling.

I testi sono enciclopedia pubblica, non un manuale operativo.
"""

from __future__ import annotations

import asyncio
import html
import logging
import os
import sys
from typing import Any

from dotenv import load_dotenv
from telegram import BotCommand, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from services.catalog import (
    ALL,
    by_era,
    by_id,
    by_kind,
    clip,
    format_card,
    format_list,
    format_search,
    of_the_day,
    random_item,
    search,
)
from services.history.corpus import search_cards
from services.history.engine import (
    entity_card,
    format_entity,
    format_era_index,
    format_gallery,
    format_list as format_era_list,
    format_overview,
    format_timeline,
    format_travel,
    graph_card,
    list_for,
    overview,
    timeline,
    travel,
)
from services.history.eras import ERAS
from services.history.pack import FACET_TITLE
from services.live import (
    REGIONS,
    fetch_aircraft,
    fetch_hub,
    fetch_iss,
    fetch_ships,
    format_aircraft,
    format_iss,
    format_live_hub,
    format_ships,
)
from services.models import DISCLAIMER, ERA_LABELS
from services.quiz import build_quiz, format_question
from ui.keyboards import (
    after_quiz_keyboard,
    back_home_keyboard,
    entity_keyboard,
    era_hub_keyboard,
    era_index_keyboard,
    esplora_keyboard,
    home_keyboard,
    list_keyboard,
    live_hub_keyboard,
    live_misc_keyboard,
    live_region_keyboard,
    quiz_hub_keyboard,
    quiz_options_keyboard,
    rank_scale_keyboard,
    hc_card_keyboard,
    hc_list_keyboard,
    mixed_search_keyboard,
    wd_card_keyboard,
    world_keyboard,
)
from ui.texts import (
    cerca_text,
    esplora_text,
    help_text,
    home_text,
    quiz_hub_text,
    world_text,
)

TELEGRAM_MAX_LEN = 3900
LAST_BOT_MSG_KEY = "last_bot_msg"
NAV_STACK_KEY = "nav_stack"
NAV_HERE_KEY = "nav_here"
NAV_MAX = 24
ERA_HERE_KEY = "era_here"
SEARCH_KEY = "warbot_search"
QUIZ_KEY = "warbot_quiz"
EMPTY_KEYBOARD = InlineKeyboardMarkup([])

NAV_SKIP_EXACT = frozenset({"nav:back", "home:menu", "q:again"})
NAV_SKIP_PREFIXES = ("qa:",)
NAV_HOME_TOKENS = frozenset({"home:menu"})

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("warbot")


def e(text: Any) -> str:
    return html.escape(str(text), quote=False)


def _last_bot_msg(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any] | None:
    last = context.chat_data.get(LAST_BOT_MSG_KEY)
    return last if isinstance(last, dict) and "id" in last else None


def _remember_bot_msg(context: ContextTypes.DEFAULT_TYPE, message_id: int, kind: str) -> None:
    context.chat_data[LAST_BOT_MSG_KEY] = {"id": message_id, "kind": kind}


async def _delete_last_bot_msg(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    last = _last_bot_msg(context)
    if not last:
        return
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=int(last["id"]))
    except TelegramError:
        pass
    context.chat_data.pop(LAST_BOT_MSG_KEY, None)


def _is_not_modified(exc: TelegramError) -> bool:
    return "not modified" in str(exc).lower()


async def delete_user_command(update: Update) -> None:
    if update.callback_query is not None:
        return
    message = update.effective_message
    if message is None:
        return
    try:
        await message.delete()
    except TelegramError as exc:
        logger.info("Comando utente non cancellato: %s", exc)


async def deliver_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    preview: bool = False,
) -> None:
    chat = update.effective_chat
    if chat is None:
        return
    text = clip(text, TELEGRAM_MAX_LEN)
    last = _last_bot_msg(context)
    markup = reply_markup if reply_markup is not None else EMPTY_KEYBOARD
    hide_preview = not preview

    if last and last.get("kind") == "text":
        try:
            await context.bot.edit_message_text(
                chat_id=chat.id,
                message_id=int(last["id"]),
                text=text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=hide_preview,
                reply_markup=markup,
            )
            return
        except TelegramError as exc:
            if _is_not_modified(exc):
                return
            logger.info("Modifica testo non riuscita, sostituisco: %s", exc)

    await _delete_last_bot_msg(context, chat.id)
    sent = await context.bot.send_message(
        chat_id=chat.id,
        text=text,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=hide_preview,
        reply_markup=markup,
    )
    _remember_bot_msg(context, sent.message_id, "text")


async def reply_html(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    preview: bool = False,
) -> None:
    await deliver_text(update, context, text, reply_markup=reply_markup, preview=preview)


def _nav_should_skip(token: str) -> bool:
    if not token or token in NAV_SKIP_EXACT:
        return True
    return any(token.startswith(prefix) for prefix in NAV_SKIP_PREFIXES)


def nav_clear(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data[NAV_STACK_KEY] = []
    context.user_data[NAV_HERE_KEY] = "home:menu"


def nav_mark(context: ContextTypes.DEFAULT_TYPE, token: str) -> None:
    if _nav_should_skip(token):
        if token in NAV_HOME_TOKENS:
            nav_clear(context)
        return
    here = context.user_data.get(NAV_HERE_KEY)
    if here == token:
        return
    if here and here not in NAV_HOME_TOKENS:
        stack = context.user_data.get(NAV_STACK_KEY)
        if not isinstance(stack, list):
            stack = []
        if not stack or stack[-1] != here:
            stack.append(here)
        if len(stack) > NAV_MAX:
            del stack[:-NAV_MAX]
        context.user_data[NAV_STACK_KEY] = stack
    context.user_data[NAV_HERE_KEY] = token


def nav_pop(context: ContextTypes.DEFAULT_TYPE) -> str | None:
    stack = context.user_data.get(NAV_STACK_KEY)
    if not isinstance(stack, list) or not stack:
        context.user_data[NAV_HERE_KEY] = "home:menu"
        return None
    token = stack.pop()
    context.user_data[NAV_STACK_KEY] = stack
    context.user_data[NAV_HERE_KEY] = token if token else "home:menu"
    return token if isinstance(token, str) and token else None


def _cmd_begin(context: ContextTypes.DEFAULT_TYPE, token: str) -> None:
    context.user_data.pop(SEARCH_KEY, None)
    nav_mark(context, token)


def _remember_from_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is not None and query.message is not None:
        kind = "text" if query.message.text else "photo"
        _remember_bot_msg(context, query.message.message_id, kind)
    if query is not None and query.data:
        nav_mark(context, query.data)


def _quiz_state(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any]:
    state = context.user_data.get(QUIZ_KEY)
    if not isinstance(state, dict):
        state = {}
        context.user_data[QUIZ_KEY] = state
    return state


async def show_home(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    nav_clear(context)
    await reply_html(update, context, home_text(), reply_markup=home_keyboard())


async def show_world(update: Update, context: ContextTypes.DEFAULT_TYPE, key: str) -> None:
    if key == "epoche":
        await reply_html(update, context, format_era_index(), reply_markup=era_index_keyboard())
        return
    await reply_html(update, context, world_text(key), reply_markup=world_keyboard(key))


async def show_entity(update: Update, context: ContextTypes.DEFAULT_TYPE, eid: str, *, section_i: int | None = None) -> None:
    item = by_id(eid)
    if item is None:
        await reply_html(update, context, "Questa scheda non è in museo.", reply_markup=home_keyboard())
        return
    section = None
    if section_i is not None:
        secs = item.get("sections") or ()
        if 0 <= section_i < len(secs):
            section = secs[section_i][0]
    await reply_html(update, context, format_card(item, section=section), reply_markup=entity_keyboard(item))


async def show_filtered_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    kind: str,
    filt: str,
) -> None:
    kind_map = {"war": "war", "bat": "battle", "role": "role", "rank": "rank", "army": "army", "gear": "gear", "vehicle": "vehicle", "fort": "fort", "doc": "doc", "peace": "peace", "person": "person", "idea": "idea"}
    real = kind_map.get(kind, kind)
    if real == "war" and filt in ERA_LABELS:
        rows = by_era(filt)
        em, name = ERA_LABELS[filt]
        title, blurb = f"{em} {name}", "Guerre di quest'era."
    elif real == "battle" and filt in ERA_LABELS:
        rows = [item for item in by_kind("battle") if item.get("era") == filt]
        em, name = ERA_LABELS[filt]
        title, blurb = f"{em} Battaglie · {name}", "Schede di campo."
    elif real == "rank" and filt == "scale":
        await reply_html(
            update,
            context,
            "🎖️ <b>SCALA DEI GRADI</b>\n\n"
            "Allineamento didattico, non una tabella NATO ufficiale.\n\n"
            "🪖 Soldato → 🎖️ Caporale → ⭐ Sergente → 🎖️ Tenente\n"
            "→ ⭐ Capitano → ⭐⭐ Maggiore → ⭐⭐⭐ Colonnello → ⭐⭐⭐⭐ Generale\n\n"
            "Tocca un grado per il confronto tra eserciti e periodi.\n\n"
            f"<i>{DISCLAIMER}</i>",
            reply_markup=rank_scale_keyboard(),
        )
        return
    else:
        rows = by_kind(real)
        title = f"Schede · {real}"
        blurb = "Tocca una voce."
    await reply_html(update, context, format_list(rows, title, blurb), reply_markup=list_keyboard(rows))


async def send_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE, mode: str) -> None:
    state = _quiz_state(context)
    if mode == "again":
        mode = str(state.get("mode") or "war")
    quiz = build_quiz(mode)
    if not quiz:
        await reply_html(update, context, "Non ho una domanda pronta.", reply_markup=quiz_hub_keyboard())
        return
    state["quiz"] = quiz
    state["mode"] = mode
    if mode == "10" and "left" not in state:
        state["left"] = 9
        state["ok"] = 0
    await reply_html(update, context, format_question(quiz), reply_markup=quiz_options_keyboard(len(quiz["options"])))


async def answer_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE, index: int) -> None:
    state = _quiz_state(context)
    quiz = state.get("quiz")
    if not isinstance(quiz, dict):
        await send_quiz(update, context, "war")
        return
    options = quiz.get("options") or []
    if index < 0 or index >= len(options):
        return
    picked = options[index]
    ok = picked == quiz["answer"]
    mark = "✅ Giusto." if ok else f"❌ Era: {e(quiz['answer'])}"
    extra = ""
    if state.get("mode") == "10":
        state["ok"] = int(state.get("ok") or 0) + (1 if ok else 0)
        asked = int(state.get("asked") or 0) + 1
        state["asked"] = asked
        extra = f"\nPunteggio: {state['ok']}/{asked}"
        if asked >= 10:
            extra = f"\nFine del giro: <b>{state['ok']}/10</b>."
            state.pop("asked", None)
            state.pop("ok", None)
            state.pop("left", None)
    text = f"{mark}{extra}\n\n<i>{DISCLAIMER}</i>"
    await reply_html(update, context, text, reply_markup=after_quiz_keyboard(quiz.get("explain")))


async def open_token(update: Update, context: ContextTypes.DEFAULT_TYPE, token: str) -> None:
    if not token or token in NAV_HOME_TOKENS:
        await show_home(update, context)
        return
    prefix, _, rest = token.partition(":")
    action, _, extra = rest.partition(":")

    if prefix == "world" and action in {"epoche", "campi", "truppe", "bandiere", "ferro", "patti"}:
        await show_world(update, context, action)
        return
    if prefix == "home":
        if action == "esplora":
            await reply_html(update, context, esplora_text(), reply_markup=esplora_keyboard())
            return
        if action == "cerca":
            context.user_data[SEARCH_KEY] = True
            await reply_html(update, context, cerca_text(), reply_markup=back_home_keyboard())
            return
        if action == "quiz":
            await reply_html(update, context, quiz_hub_text(), reply_markup=quiz_hub_keyboard())
            return
        if action == "oggi":
            item = of_the_day()
            await show_entity(update, context, item["id"])
            return
        if action == "random":
            item = random_item()
            await show_entity(update, context, item["id"])
            return
        if action == "menu":
            await show_home(update, context)
            return
        if action == "aiuto":
            await reply_html(update, context, help_text(), reply_markup=back_home_keyboard())
            return
        if action == "live":
            await show_live_hub(update, context)
            return
    if prefix == "live":
        await open_live(update, context, action, extra)
        return
    if prefix == "era":
        await open_era(update, context, action, extra)
        return
    if prefix == "wd" and rest:
        await show_wd(update, context, rest)
        return
    if prefix == "hc" and rest:
        await show_history_card(update, context, rest)
        return
    if prefix == "h" and action == "go":
        await show_travel(update, context, None)
        return
    if prefix == "e" and action:
        await show_entity(update, context, action)
        return
    if prefix == "s" and action:
        idx = int(extra) if extra.isdigit() else 0
        await show_entity(update, context, action, section_i=idx)
        return
    if prefix == "l" and action:
        await show_filtered_list(update, context, action, extra or "all")
        return
    if prefix == "rnd" and action:
        item = random_item(world=action)
        await show_entity(update, context, item["id"])
        return
    if prefix == "q":
        if action == "again":
            await send_quiz(update, context, "again")
        else:
            if action == "10":
                _quiz_state(context).clear()
                _quiz_state(context)["mode"] = "10"
                _quiz_state(context)["asked"] = 0
                _quiz_state(context)["ok"] = 0
            await send_quiz(update, context, action or "war")
        return
    if prefix == "qa" and action.isdigit():
        await answer_quiz(update, context, int(action))
        return
    await show_home(update, context)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _cmd_begin(context, "home:menu")
    await show_home(update, context)
    await delete_user_command(update)


async def cmd_aiuto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _cmd_begin(context, "home:aiuto")
    await reply_html(update, context, help_text(), reply_markup=back_home_keyboard())
    await delete_user_command(update)


async def cmd_esplora(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _cmd_begin(context, "home:esplora")
    await reply_html(update, context, esplora_text(), reply_markup=esplora_keyboard())
    await delete_user_command(update)


async def cmd_world(update: Update, context: ContextTypes.DEFAULT_TYPE, key: str) -> None:
    _cmd_begin(context, f"world:{key}")
    await show_world(update, context, key)
    await delete_user_command(update)


async def cmd_epoche(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_world(update, context, "epoche")


async def cmd_viaggia(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _cmd_begin(context, "h:go")
    await show_travel(update, context, None)
    await delete_user_command(update)


async def cmd_campi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_world(update, context, "campi")


async def cmd_truppe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_world(update, context, "truppe")


async def cmd_bandiere(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_world(update, context, "bandiere")


async def cmd_ferro(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_world(update, context, "ferro")


async def cmd_patti(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_world(update, context, "patti")


async def cmd_cerca(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _cmd_begin(context, "home:cerca")
    query = " ".join(context.args).strip() if context.args else ""
    if query:
        await receive_search(update, context, query)
    else:
        context.user_data[SEARCH_KEY] = True
        await reply_html(update, context, cerca_text(), reply_markup=back_home_keyboard())
    await delete_user_command(update)


async def cmd_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _cmd_begin(context, "home:quiz")
    await reply_html(update, context, quiz_hub_text(), reply_markup=quiz_hub_keyboard())
    await delete_user_command(update)


async def cmd_oggi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _cmd_begin(context, "home:oggi")
    await show_entity(update, context, of_the_day()["id"])
    await delete_user_command(update)


async def cmd_casuale(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _cmd_begin(context, "home:random")
    await show_entity(update, context, random_item()["id"])
    await delete_user_command(update)


def _era_here(context: ContextTypes.DEFAULT_TYPE, eid: str | None = None) -> str | None:
    if eid:
        context.user_data[ERA_HERE_KEY] = eid
        return eid
    here = context.user_data.get(ERA_HERE_KEY)
    return here if isinstance(here, str) else None


async def show_era_hub(update: Update, context: ContextTypes.DEFAULT_TYPE, eid: str) -> None:
    if eid not in ERAS:
        await reply_html(update, context, "Epoca non in mappa.", reply_markup=era_index_keyboard())
        return
    _era_here(context, eid)
    data = overview(eid, fetch_media=False)
    await reply_html(update, context, format_overview(data), reply_markup=era_hub_keyboard(eid), preview=True)
    data = await asyncio.to_thread(overview, eid)
    await reply_html(update, context, format_overview(data), reply_markup=era_hub_keyboard(eid), preview=True)


async def show_history_card(update: Update, context: ContextTypes.DEFAULT_TYPE, cid: str) -> None:
    data = entity_card(cid, fetch_media=False)
    if not data:
        await reply_html(update, context, "Scheda assente nel database WARBOT.", reply_markup=era_index_keyboard())
        return
    era = data.get("era") or {}
    eid = era.get("id")
    if eid:
        _era_here(context, eid)
    await reply_html(
        update,
        context,
        format_entity(data),
        reply_markup=hc_card_keyboard(data["item"], data.get("related") or [], eid),
        preview=True,
    )
    data = await asyncio.to_thread(entity_card, cid)
    if data:
        await reply_html(
            update,
            context,
            format_entity(data),
            reply_markup=hc_card_keyboard(data["item"], data.get("related") or [], eid),
            preview=True,
        )


async def show_wd(update: Update, context: ContextTypes.DEFAULT_TYPE, qid: str) -> None:
    await reply_html(update, context, "🔗 Apro il grafo Wikidata (anagrafe, non la scheda)…", reply_markup=back_home_keyboard())
    data = await asyncio.to_thread(graph_card, qid)
    if not data:
        await reply_html(update, context, "Wikidata non ha risposto. Torna alla scheda WARBOT.", reply_markup=era_index_keyboard())
        return
    eid = _era_here(context)
    await reply_html(
        update,
        context,
        format_entity(data),
        reply_markup=wd_card_keyboard(data["item"], [], eid),
        preview=True,
    )


async def show_travel(update: Update, context: ContextTypes.DEFAULT_TYPE, eid: str | None) -> None:
    await reply_html(update, context, "🎲 <b>VIAGGIA NEL TEMPO</b>\n\nPesca una scheda del museo…", reply_markup=back_home_keyboard())
    data = await asyncio.to_thread(travel, eid)
    era_id = (data.get("era") or {}).get("id")
    if era_id:
        _era_here(context, era_id)
    event = data.get("event") or {}
    related = data.get("people") or []
    markup = hc_card_keyboard(event, related, era_id) if event.get("id") else era_hub_keyboard(era_id or "ww2")
    await reply_html(update, context, format_travel(data), reply_markup=markup, preview=True)


async def open_era(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, extra: str) -> None:
    if not action or action == "list":
        await reply_html(update, context, format_era_index(), reply_markup=era_index_keyboard())
        return
    if action not in ERAS:
        await reply_html(update, context, "Epoca non in mappa.", reply_markup=era_index_keyboard())
        return
    _era_here(context, action)
    extra = {"sld": "arm", "bat": "war"}.get(extra, extra)
    if extra in {"", "hub", "ov"}:
        await show_era_hub(update, context, action)
        return
    if extra == "go":
        await show_travel(update, context, action)
        return
    heading = FACET_TITLE.get(extra)
    if not heading:
        await show_era_hub(update, context, action)
        return
    if extra in {"img", "doc"}:
        await reply_html(
            update,
            context,
            f"{ERAS[action]['emoji']} <b>{ERAS[action]['title']}</b>\n\nInterrogo gli archivi pubblici…",
            reply_markup=era_hub_keyboard(action),
        )
        data = await asyncio.to_thread(list_for, action, extra)
        text = format_gallery(data, heading)
        await reply_html(update, context, text, reply_markup=era_hub_keyboard(action), preview=True)
        return
    if extra == "tl":
        data = timeline(action)
        text = format_timeline(data)
        rows: list[dict] = []
        for _year, chunk in data.get("years") or []:
            rows.extend(chunk)
        markup = hc_list_keyboard(rows, action) if rows else era_hub_keyboard(action)
        await reply_html(update, context, text, reply_markup=markup, preview=True)
        return
    data = list_for(action, extra)
    text = format_era_list(data, heading)
    rows = data.get("rows") or []
    markup = hc_list_keyboard(rows, action) if rows else era_hub_keyboard(action)
    await reply_html(update, context, text, reply_markup=markup, preview=True)


def _live_region(raw: str | None) -> str:
    key = (raw or "it").strip().lower()
    aliases = {"italia": "it", "italy": "it", "mediterraneo": "med", "europa": "eu", "manica": "uk", "usa": "us", "giappone": "jp", "japan": "jp"}
    key = aliases.get(key, key)
    return key if key in REGIONS else "it"


async def show_live_hub(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await reply_html(
        update,
        context,
        "📡 <b>POSIZIONI LIVE</b>\n\nInterrogo aerei, navi e la stazione spaziale…",
        reply_markup=live_hub_keyboard(),
    )
    snapshot = await asyncio.to_thread(fetch_hub)
    await reply_html(
        update,
        context,
        format_live_hub(snapshot),
        reply_markup=live_hub_keyboard(),
        preview=True,
    )


async def show_live_aircraft(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    region: str,
    *,
    heli: bool = False,
) -> None:
    region = _live_region(region)
    kind = "heli" if heli else "ac"
    await reply_html(
        update,
        context,
        "📡 <b>LIVE</b>\n\nInterrogo ADS-B pubblico…",
        reply_markup=live_region_keyboard(kind, region),
    )
    bundle = await asyncio.to_thread(fetch_aircraft, region)
    await reply_html(
        update,
        context,
        format_aircraft(bundle, heli_only=heli),
        reply_markup=live_region_keyboard(kind, region),
        preview=True,
    )


async def show_live_ships(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await reply_html(
        update,
        context,
        "📡 <b>LIVE</b>\n\nInterrogo AIS aperto del Baltico…",
        reply_markup=live_misc_keyboard("live:ships"),
    )
    bundle = await asyncio.to_thread(fetch_ships)
    await reply_html(update, context, format_ships(bundle), reply_markup=live_misc_keyboard("live:ships"), preview=True)


async def show_live_iss(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await reply_html(
        update,
        context,
        "📡 <b>LIVE</b>\n\nChiedo coordinate alla stazione…",
        reply_markup=live_misc_keyboard("live:iss"),
    )
    bundle = await asyncio.to_thread(fetch_iss)
    await reply_html(update, context, format_iss(bundle), reply_markup=live_misc_keyboard("live:iss"), preview=True)


async def open_live(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, extra: str) -> None:
    if action in {"hub", ""}:
        await show_live_hub(update, context)
        return
    if action == "ac":
        await show_live_aircraft(update, context, extra or "it")
        return
    if action == "heli":
        await show_live_aircraft(update, context, extra or "it", heli=True)
        return
    if action in {"ships", "navi"}:
        await show_live_ships(update, context)
        return
    if action == "iss":
        await show_live_iss(update, context)
        return
    await show_live_hub(update, context)


async def cmd_live(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _cmd_begin(context, "home:live")
    await show_live_hub(update, context)
    await delete_user_command(update)


async def cmd_aerei(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    region = _live_region(context.args[0] if context.args else "it")
    _cmd_begin(context, f"live:ac:{region}")
    await show_live_aircraft(update, context, region)
    await delete_user_command(update)


async def cmd_elicotteri(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    region = _live_region(context.args[0] if context.args else "it")
    _cmd_begin(context, f"live:heli:{region}")
    await show_live_aircraft(update, context, region, heli=True)
    await delete_user_command(update)


async def cmd_navi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _cmd_begin(context, "live:ships")
    await show_live_ships(update, context)
    await delete_user_command(update)


async def cmd_iss(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _cmd_begin(context, "live:iss")
    await show_live_iss(update, context)
    await delete_user_command(update)


async def receive_search(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    context.user_data[SEARCH_KEY] = False
    rows = search(text)
    hist = search_cards(text)
    if hist and not rows:
        from services.history.engine import format_search_hits

        await reply_html(
            update,
            context,
            format_search_hits(text, hist),
            reply_markup=mixed_search_keyboard([], hist),
        )
        return
    extra = ""
    if hist:
        extra = "\n\n🌍 <b>EPOCHE</b> ha anche " + str(len(hist)) + " schede curate."
    await reply_html(
        update,
        context,
        format_search(text, rows) + extra,
        reply_markup=mixed_search_keyboard(rows, hist),
    )


async def on_plain_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None or not message.text:
        return
    text = message.text.strip()
    if context.user_data.get(SEARCH_KEY):
        await receive_search(update, context, text)
        await delete_user_command(update)
        return
    rows = search(text, limit=8)
    if len(rows) == 1:
        await show_entity(update, context, rows[0]["id"])
        await delete_user_command(update)
        return
    if rows:
        await reply_html(update, context, format_search(text, rows), reply_markup=list_keyboard(rows))
        await delete_user_command(update)


async def on_home_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or not query.data:
        return
    _remember_from_callback(update, context)
    await query.answer()
    await open_token(update, context, query.data)


async def on_world_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or not query.data:
        return
    _remember_from_callback(update, context)
    await query.answer()
    await open_token(update, context, query.data)


async def on_entity_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or not query.data:
        return
    _remember_from_callback(update, context)
    await query.answer()
    await open_token(update, context, query.data)


async def on_quiz_tap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or not query.data:
        return
    _remember_from_callback(update, context)
    await query.answer()
    await open_token(update, context, query.data)


async def on_nav_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or not query.data:
        return
    await query.answer()
    _remember_from_callback(update, context)
    token = nav_pop(context)
    if not token:
        await show_home(update, context)
        return
    await open_token(update, context, token)


async def on_unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await reply_html(
        update,
        context,
        "Comando sconosciuto. /aiuto elenca i mondi del museo.",
        reply_markup=back_home_keyboard(),
    )


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Errore handler: %s", context.error)
    if isinstance(update, Update):
        try:
            await reply_html(update, context, "Qualcosa si è inceppato nel museo. Riprova da /start.", reply_markup=home_keyboard())
        except Exception:
            pass


async def post_init(application: Application) -> None:
    try:
        await application.bot.set_my_commands(
            [
                BotCommand("start", "I sei mondi del museo"),
                BotCommand("live", "Posizioni live: aerei, navi, ISS"),
                BotCommand("aerei", "Aerei in volo su una zona"),
                BotCommand("navi", "Navi AIS del Baltico"),
                BotCommand("iss", "Mappa della stazione spaziale"),
                BotCommand("esplora", "Mappa dei mondi"),
                BotCommand("epoche", "Timeline storica da archivi pubblici"),
                BotCommand("viaggia", "Un anno e un evento a caso"),
                BotCommand("campi", "Battaglie"),
                BotCommand("truppe", "Soldati e gradi"),
                BotCommand("bandiere", "Forze armate"),
                BotCommand("ferro", "Mezzi e fortificazioni"),
                BotCommand("patti", "Pace, trattati, personaggi"),
                BotCommand("cerca", "Ricerca universale"),
                BotCommand("quiz", "Quiz storico"),
                BotCommand("oggi", "Scheda del giorno"),
                BotCommand("casuale", "Una scheda a caso"),
                BotCommand("aiuto", "Elenco comandi"),
            ]
        )
    except TelegramError as exc:
        logger.warning("Impossibile impostare i comandi: %s", exc)
    logger.info("WARBOT inizializzato · %s schede", len(ALL))


def build_application(token: str) -> Application:
    application = (
        Application.builder()
        .token(token)
        .post_init(post_init)
        .build()
    )
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler(["aiuto", "help"], cmd_aiuto))
    application.add_handler(CommandHandler(["esplora", "explore"], cmd_esplora))
    application.add_handler(CommandHandler("epoche", cmd_epoche))
    application.add_handler(CommandHandler(["viaggia", "tempo"], cmd_viaggia))
    application.add_handler(CommandHandler(["campi", "battaglie"], cmd_campi))
    application.add_handler(CommandHandler(["truppe", "soldati", "gradi"], cmd_truppe))
    application.add_handler(CommandHandler(["bandiere", "eserciti"], cmd_bandiere))
    application.add_handler(CommandHandler(["ferro", "mezzi", "arsenale"], cmd_ferro))
    application.add_handler(CommandHandler(["patti", "pace"], cmd_patti))
    application.add_handler(CommandHandler(["cerca", "search"], cmd_cerca))
    application.add_handler(CommandHandler("quiz", cmd_quiz))
    application.add_handler(CommandHandler("oggi", cmd_oggi))
    application.add_handler(CommandHandler(["casuale", "random"], cmd_casuale))
    application.add_handler(CommandHandler(["live", "adsb", "ais"], cmd_live))
    application.add_handler(CommandHandler(["aerei", "aircraft"], cmd_aerei))
    application.add_handler(CommandHandler(["elicotteri", "eli"], cmd_elicotteri))
    application.add_handler(CommandHandler(["navi", "ships"], cmd_navi))
    application.add_handler(CommandHandler("iss", cmd_iss))
    application.add_handler(CallbackQueryHandler(on_nav_action, pattern=r"^nav:"))
    application.add_handler(CallbackQueryHandler(on_world_action, pattern=r"^world:"))
    application.add_handler(CallbackQueryHandler(on_home_action, pattern=r"^home:"))
    application.add_handler(CallbackQueryHandler(on_home_action, pattern=r"^live:"))
    application.add_handler(CallbackQueryHandler(on_home_action, pattern=r"^era:"))
    application.add_handler(CallbackQueryHandler(on_home_action, pattern=r"^wd:"))
    application.add_handler(CallbackQueryHandler(on_home_action, pattern=r"^hc:"))
    application.add_handler(CallbackQueryHandler(on_home_action, pattern=r"^h:"))
    application.add_handler(CallbackQueryHandler(on_entity_action, pattern=r"^(e|s|l|rnd):"))
    application.add_handler(CallbackQueryHandler(on_quiz_tap, pattern=r"^q"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_plain_text))
    application.add_handler(MessageHandler(filters.COMMAND, on_unknown_command))
    application.add_error_handler(on_error)
    return application


def main() -> None:
    load_dotenv()
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        logger.error("Manca TELEGRAM_BOT_TOKEN. Copia .env.example in .env, oppure avvia il museo web: python museum.py")
        sys.exit(1)

    application = build_application(token)
    webhook_url = (os.getenv("WEBHOOK_URL") or "").strip()
    if webhook_url:
        port = int(os.getenv("PORT") or "10000")
        url_path = (os.getenv("WEBHOOK_PATH") or "webhook").strip().strip("/")
        secret = (os.getenv("WEBHOOK_SECRET") or "").strip() or None
        public_url = f"{webhook_url.rstrip('/')}/{url_path}"
        logger.info("Avvio in modalità WEBHOOK su porta %s → %s", port, public_url)
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=url_path,
            webhook_url=public_url,
            secret_token=secret,
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )
    else:
        logger.info("Avvio in modalità POLLING (nessun WEBHOOK_URL)")
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
