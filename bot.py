#!/usr/bin/env python3
"""
WARBOT — posizioni live su Telegram.

Un solo messaggio in chat: tastiere inline, callback a prefisso,
Indietro/Inizio, webhook o polling. Aerei (ADS-B), navi (AIS), ISS.
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

from services.live import (
    REGIONS,
    clip,
    fetch_aircraft,
    fetch_hub,
    fetch_iss,
    fetch_ships,
    format_aircraft,
    format_iss,
    format_live_hub,
    format_ships,
)
from services.live.osm import (
    PLACES,
    format_osm_category,
    format_osm_place,
    resolve_category,
    resolve_place,
    search_place,
)
from ui.keyboards import (
    back_home_keyboard,
    live_hub_keyboard,
    live_misc_keyboard,
    live_region_keyboard,
    osm_category_keyboard,
    osm_place_keyboard,
)
from ui.texts import help_text

TELEGRAM_MAX_LEN = 3900
LAST_BOT_MSG_KEY = "last_bot_msg"
NAV_STACK_KEY = "nav_stack"
NAV_HERE_KEY = "nav_here"
NAV_MAX = 24
EMPTY_KEYBOARD = InlineKeyboardMarkup([])

NAV_SKIP_EXACT = frozenset({"nav:back", "home:menu"})
NAV_HOME_TOKENS = frozenset({"home:menu", "home:live"})

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
    if not token or token in NAV_SKIP_EXACT:
        return True
    return False


def nav_clear(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data[NAV_STACK_KEY] = []
    context.user_data[NAV_HERE_KEY] = "home:live"


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
        context.user_data[NAV_HERE_KEY] = "home:live"
        return None
    token = stack.pop()
    context.user_data[NAV_STACK_KEY] = stack
    context.user_data[NAV_HERE_KEY] = token if token else "home:live"
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


def _live_region(raw: str | None) -> str:
    key = (raw or "it").strip().lower()
    aliases = {
        "italia": "it",
        "italy": "it",
        "mediterraneo": "med",
        "europa": "eu",
        "manica": "uk",
        "usa": "us",
        "giappone": "jp",
        "japan": "jp",
    }
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
    await reply_html(
        update,
        context,
        format_ships(bundle),
        reply_markup=live_misc_keyboard("live:ships"),
        preview=True,
    )


async def show_live_iss(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await reply_html(
        update,
        context,
        "📡 <b>LIVE</b>\n\nChiedo coordinate alla stazione…",
        reply_markup=live_misc_keyboard("live:iss"),
    )
    bundle = await asyncio.to_thread(fetch_iss)
    await reply_html(update, context, format_iss(bundle), reply_markup=live_misc_keyboard("live:iss"), preview=True)


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await reply_html(update, context, help_text(), reply_markup=back_home_keyboard())


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
    if action == "osm":
        place, _, cat = extra.partition(":")
        await show_osm(update, context, place or "milano", cat or None)
        return
    await show_live_hub(update, context)


async def open_token(update: Update, context: ContextTypes.DEFAULT_TYPE, token: str) -> None:
    if not token or token in NAV_HOME_TOKENS:
        await show_live_hub(update, context)
        return
    prefix, _, rest = token.partition(":")
    action, _, extra = rest.partition(":")

    if prefix == "home":
        if action == "aiuto":
            await show_help(update, context)
            return
        await show_live_hub(update, context)
        return
    if prefix == "live":
        await open_live(update, context, action, extra)
        return
    await show_live_hub(update, context)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _cmd_begin(context, "home:live")
    await show_live_hub(update, context)
    await delete_user_command(update)


async def cmd_aiuto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _cmd_begin(context, "home:aiuto")
    await show_help(update, context)
    await delete_user_command(update)


async def show_osm(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    place: str,
    category: str | None = None,
) -> None:
    meta = resolve_place(place)
    if meta is None:
        known = ", ".join(sorted(PLACES))
        await reply_html(
            update,
            context,
            f"🗺️ <b>LIVE OSM</b>\n\nLuogo non in mappa. Ora: {known}.\nEsempio: /live milano",
            reply_markup=back_home_keyboard(),
        )
        return
    place_id = meta["id"]
    cat = resolve_category(category) if category else None
    if category and not cat:
        await show_osm(update, context, place_id, None)
        return
    if cat:
        await reply_html(
            update,
            context,
            f"🗺️ <b>LIVE OSM</b>\n\nInterrogo OpenStreetMap su {meta['title']}…",
            reply_markup=osm_category_keyboard(place_id, cat),
        )
        bundle = await asyncio.to_thread(search_place, place_id, cat)
        await reply_html(
            update,
            context,
            format_osm_category(bundle),
            reply_markup=osm_category_keyboard(place_id, cat),
            preview=True,
        )
        return
    await reply_html(
        update,
        context,
        f"🗺️ <b>LIVE OSM</b>\n\nInterrogo OpenStreetMap su {meta['title']}…",
        reply_markup=osm_place_keyboard(place_id),
    )
    bundle = await asyncio.to_thread(search_place, place_id)
    await reply_html(
        update,
        context,
        format_osm_place(bundle),
        reply_markup=osm_place_keyboard(place_id),
        preview=True,
    )


async def cmd_live(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = [a.strip() for a in (context.args or []) if a.strip()]
    if args:
        place = args[0]
        category = args[1] if len(args) > 1 else None
        token = f"live:osm:{resolve_place(place)['id']}" if resolve_place(place) else f"live:osm:{place.lower()}"
        if category and resolve_category(category):
            token = f"{token}:{resolve_category(category)}"
        _cmd_begin(context, token)
        await show_osm(update, context, place, category)
        await delete_user_command(update)
        return
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
        await show_live_hub(update, context)
        return
    await open_token(update, context, token)


async def on_unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await reply_html(
        update,
        context,
        "Comando sconosciuto. /aiuto elenca aerei, navi e ISS.",
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
                reply_markup=live_hub_keyboard(),
            )
        except Exception:
            pass


async def post_init(application: Application) -> None:
    try:
        await application.bot.set_my_commands(
            [
                BotCommand("start", "Posizioni live: aerei, navi, ISS"),
                BotCommand("live", "Hub live, o /live milano per OSM"),
                BotCommand("aerei", "Aerei in volo su una zona"),
                BotCommand("elicotteri", "Solo elicotteri, stessa zona"),
                BotCommand("navi", "Navi AIS del Baltico"),
                BotCommand("iss", "Mappa della stazione spaziale"),
                BotCommand("aiuto", "Elenco comandi"),
            ]
        )
    except TelegramError as exc:
        logger.warning("Impossibile impostare i comandi: %s", exc)
    logger.info("WARBOT live inizializzato")


def build_application(token: str) -> Application:
    application = Application.builder().token(token).post_init(post_init).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler(["aiuto", "help"], cmd_aiuto))
    application.add_handler(CommandHandler(["live", "adsb", "ais"], cmd_live))
    application.add_handler(CommandHandler(["aerei", "aircraft"], cmd_aerei))
    application.add_handler(CommandHandler(["elicotteri", "eli"], cmd_elicotteri))
    application.add_handler(CommandHandler(["navi", "ships"], cmd_navi))
    application.add_handler(CommandHandler("iss", cmd_iss))
    application.add_handler(CallbackQueryHandler(on_nav_action, pattern=r"^nav:"))
    application.add_handler(CallbackQueryHandler(on_callback, pattern=r"^home:"))
    application.add_handler(CallbackQueryHandler(on_callback, pattern=r"^live:"))
    application.add_handler(MessageHandler(filters.COMMAND, on_unknown_command))
    application.add_error_handler(on_error)
    return application


def main() -> None:
    load_dotenv()
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        logger.error(
            "Manca TELEGRAM_BOT_TOKEN. Copia .env.example in .env, oppure avvia la mappa web: python museum.py"
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
