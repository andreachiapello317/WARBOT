#!/usr/bin/env python3
"""
WARBOT — OSM WORLD su Telegram.

Un solo messaggio in chat: tastiere inline, callback a prefisso,
Indietro/Inizio, webhook o polling.
"""

from __future__ import annotations

import asyncio
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

from services.live.geocode import geocode
from services.live.osm import (
    clip,
    format_osm_category,
    format_osm_hits,
    format_osm_item,
    format_osm_map,
    format_osm_place,
    format_osm_world,
    peek as osm_peek,
    resolve_category,
    search as osm_search_bbox,
)
from ui.keyboards import (
    back_home_keyboard,
    osm_category_keyboard,
    osm_hits_keyboard,
    osm_item_keyboard,
    osm_place_keyboard,
    osm_world_keyboard,
)
from ui.texts import help_text

TELEGRAM_MAX_LEN = 3900
LAST_BOT_MSG_KEY = "last_bot_msg"
NAV_STACK_KEY = "nav_stack"
NAV_HERE_KEY = "nav_here"
NAV_MAX = 24
EMPTY_KEYBOARD = InlineKeyboardMarkup([])

NAV_SKIP_EXACT = frozenset({"nav:back", "home:menu"})
NAV_HOME_TOKENS = frozenset({"home:menu", "live:ow"})
OSM_WAIT_KEY = "osm_wait_text"
OSM_PLACE_KEY = "osm_place"
OSM_HITS_KEY = "osm_hits"
OSM_ROWS_KEY = "osm_rows"
OSM_CAT_KEY = "osm_cat"

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("warbot")


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
    return (not token) or token in NAV_SKIP_EXACT


def nav_clear(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data[NAV_STACK_KEY] = []
    context.user_data[NAV_HERE_KEY] = "live:ow"


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
        context.user_data[NAV_HERE_KEY] = "live:ow"
        return None
    token = stack.pop()
    context.user_data[NAV_STACK_KEY] = stack
    context.user_data[NAV_HERE_KEY] = token if token else "live:ow"
    return token if isinstance(token, str) and token else None


def _cmd_begin(context: ContextTypes.DEFAULT_TYPE, token: str) -> None:
    nav_mark(context, token)


def _remember_from_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is not None and query.message is not None:
        kind = "text" if query.message.text else "photo"
        _remember_bot_msg(context, query.message.message_id, kind)
    if query is not None and query.data:
        nav_mark(context, query.data)


def _osm_place(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any] | None:
    place = context.user_data.get(OSM_PLACE_KEY)
    return place if isinstance(place, dict) and "lat" in place else None


def _set_osm_wait(context: ContextTypes.DEFAULT_TYPE, waiting: bool) -> None:
    context.user_data[OSM_WAIT_KEY] = waiting


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _set_osm_wait(context, False)
    await reply_html(update, context, help_text(), reply_markup=back_home_keyboard())


async def show_osm_world(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _set_osm_wait(context, True)
    await reply_html(update, context, format_osm_world(), reply_markup=osm_world_keyboard())


async def show_osm_place(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    place = _osm_place(context)
    if not place:
        await show_osm_world(update, context)
        return
    _set_osm_wait(context, False)
    await reply_html(update, context, format_osm_place(place), reply_markup=osm_place_keyboard())


async def osm_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
    _set_osm_wait(context, False)
    await reply_html(
        update,
        context,
        f"🌍 <b>OSM WORLD</b>\n\nCerco <b>{query}</b>…",
        reply_markup=osm_world_keyboard(),
    )
    result = await asyncio.to_thread(geocode, query)
    if not result.get("ok"):
        _set_osm_wait(context, True)
        await reply_html(
            update,
            context,
            f"🌍 <b>OSM WORLD</b>\n\nNessun luogo per «{query}».\n"
            f"<i>{result.get('error') or 'geocoder vuoto'}</i>\n\nScrivi un'altra località.",
            reply_markup=osm_world_keyboard(),
        )
        return
    hits = list(result.get("hits") or [])
    context.user_data[OSM_HITS_KEY] = hits
    if len(hits) == 1:
        context.user_data[OSM_PLACE_KEY] = hits[0]
        context.user_data.pop(OSM_ROWS_KEY, None)
        context.user_data.pop(OSM_CAT_KEY, None)
        await show_osm_place(update, context)
        return
    await reply_html(update, context, format_osm_hits(query, hits), reply_markup=osm_hits_keyboard(len(hits)))


async def show_osm_category(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str) -> None:
    place = _osm_place(context)
    if not place:
        await show_osm_world(update, context)
        return
    cat = resolve_category(category)
    if not cat:
        await show_osm_place(update, context)
        return
    _set_osm_wait(context, False)
    bundle = osm_peek(place["bbox"], cat)
    if bundle is None:
        await reply_html(
            update,
            context,
            f"🌍 <b>OSM WORLD</b>\n\nInterrogo Overpass · {place.get('display')}…",
            reply_markup=osm_place_keyboard(),
        )
        bundle = await asyncio.to_thread(osm_search_bbox, place["bbox"], cat)
    rows = list(bundle.get("rows") or [])
    context.user_data[OSM_ROWS_KEY] = rows
    context.user_data[OSM_CAT_KEY] = cat
    await reply_html(
        update,
        context,
        format_osm_category(bundle, place),
        reply_markup=osm_category_keyboard(rows),
        preview=True,
    )


async def show_osm_item(update: Update, context: ContextTypes.DEFAULT_TYPE, index: int) -> None:
    rows = context.user_data.get(OSM_ROWS_KEY)
    if not isinstance(rows, list) or index < 0 or index >= len(rows):
        cat = context.user_data.get(OSM_CAT_KEY)
        if cat:
            await show_osm_category(update, context, str(cat))
            return
        await show_osm_place(update, context)
        return
    await reply_html(
        update,
        context,
        format_osm_item(rows[index], _osm_place(context)),
        reply_markup=osm_item_keyboard(),
        preview=True,
    )


async def show_osm_map(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    place = _osm_place(context)
    if not place:
        await show_osm_world(update, context)
        return
    await reply_html(update, context, format_osm_map(place), reply_markup=osm_place_keyboard(), preview=True)


async def show_osm_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cat = context.user_data.get(OSM_CAT_KEY)
    if cat:
        await show_osm_category(update, context, str(cat))
        return
    await show_osm_place(update, context)


async def open_ow(update: Update, context: ContextTypes.DEFAULT_TYPE, extra: str) -> None:
    extra = (extra or "").strip()
    if not extra:
        await show_osm_world(update, context)
        return
    kind, _, rest = extra.partition(":")
    if kind == "p" and rest.isdigit():
        hits = context.user_data.get(OSM_HITS_KEY)
        idx = int(rest)
        if isinstance(hits, list) and 0 <= idx < len(hits):
            context.user_data[OSM_PLACE_KEY] = hits[idx]
            context.user_data.pop(OSM_ROWS_KEY, None)
            context.user_data.pop(OSM_CAT_KEY, None)
            await show_osm_place(update, context)
            return
        await show_osm_world(update, context)
        return
    if kind == "c" and rest:
        await show_osm_category(update, context, rest)
        return
    if kind == "i" and rest.isdigit():
        await show_osm_item(update, context, int(rest))
        return
    if kind == "map":
        await show_osm_map(update, context)
        return
    if kind == "here":
        await show_osm_place(update, context)
        return
    if kind == "list":
        await show_osm_list(update, context)
        return
    query = extra.replace(":", " ").strip()
    if query and query not in {"q", "search"}:
        await osm_lookup(update, context, query)
        return
    await show_osm_world(update, context)


async def open_token(update: Update, context: ContextTypes.DEFAULT_TYPE, token: str) -> None:
    if not token or token in NAV_HOME_TOKENS:
        await show_osm_world(update, context)
        return
    prefix, _, rest = token.partition(":")
    action, _, extra = rest.partition(":")
    if prefix == "home":
        if action == "aiuto":
            await show_help(update, context)
            return
        await show_osm_world(update, context)
        return
    if prefix == "live":
        if action in {"ow", "osm", "hub", ""}:
            await open_ow(update, context, extra if action in {"ow", "osm"} else "")
            return
        await show_osm_world(update, context)
        return
    await show_osm_world(update, context)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _cmd_begin(context, "live:ow")
    await show_osm_world(update, context)
    await delete_user_command(update)


async def cmd_aiuto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _cmd_begin(context, "home:aiuto")
    await show_help(update, context)
    await delete_user_command(update)


async def cmd_osm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = [a.strip() for a in (context.args or []) if a.strip()]
    _cmd_begin(context, "live:ow")
    if args:
        await osm_lookup(update, context, " ".join(args))
    else:
        await show_osm_world(update, context)
    await delete_user_command(update)


async def on_plain_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None or not message.text:
        return
    query = message.text.strip()
    if len(query) < 2:
        return
    _cmd_begin(context, "live:ow")
    await osm_lookup(update, context, query)
    await delete_user_command(update)


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
        await show_osm_world(update, context)
        return
    await open_token(update, context, token)


async def on_unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await reply_html(
        update,
        context,
        "Comando sconosciuto. /start oppure scrivi una città.",
        reply_markup=back_home_keyboard(),
    )


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Errore handler: %s", context.error)
    if isinstance(update, Update):
        try:
            await reply_html(
                update,
                context,
                "Qualcosa si è inceppato. Riprova da /start.",
                reply_markup=osm_world_keyboard(),
            )
        except Exception:
            pass


async def post_init(application: Application) -> None:
    try:
        await application.bot.set_my_commands(
            [
                BotCommand("start", "OSM WORLD: cerca una località"),
                BotCommand("osm", "OSM WORLD"),
                BotCommand("aiuto", "Come funziona"),
            ]
        )
    except TelegramError as exc:
        logger.warning("Impossibile impostare i comandi: %s", exc)
    logger.info("OSM WORLD inizializzato")


def build_application(token: str) -> Application:
    application = Application.builder().token(token).post_init(post_init).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler(["aiuto", "help"], cmd_aiuto))
    application.add_handler(CommandHandler(["osm", "live", "overpass"], cmd_osm))
    application.add_handler(CallbackQueryHandler(on_nav_action, pattern=r"^nav:"))
    application.add_handler(CallbackQueryHandler(on_callback, pattern=r"^home:"))
    application.add_handler(CallbackQueryHandler(on_callback, pattern=r"^live:"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_plain_text))
    application.add_handler(MessageHandler(filters.COMMAND, on_unknown_command))
    application.add_error_handler(on_error)
    return application


def main() -> None:
    load_dotenv()
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        logger.error(
            "Manca TELEGRAM_BOT_TOKEN. Copia .env.example in .env, oppure avvia il web: python museum.py"
        )
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
