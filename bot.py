#!/usr/bin/env python3
"""
WARBOT — città, poi mondi, poi query.

START chiede la località. Il geocoding crea il CityContext.
Ogni mondo (OSM, CITY LIFE, AIR TRAFFIC, SKY, EARTH, SPACE) usa quelle coordinate. Nessun secondo geocoding
quando si passa da un mondo all'altro.

Webhook / token / Render: invariati.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from dotenv import load_dotenv
from telegram import BotCommand, Update
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from core.webhook import install_health_routes, resolve_webhook
from core.session import (
    SCREEN_OSM_ITEM,
    SCREEN_OSM_NEAR,
    SCREEN_OSM_RESULTS,
    SCREEN_WORLDS,
    get_city,
    get_screen,
    get_world_id,
    waiting_city,
)
from core.telegram import answer_callback, delete_user_command, deliver, remember_from_callback
from ui.texts import help_text
from worlds.city import (
    city_prompt_keyboard,
    lookup_city,
    open_world,
    pick_city,
    show_city_prompt,
    show_worlds,
)
from worlds.registry import callback_pattern, get_world, parse_callback, world_ids

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("warbot")


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await deliver(update, context, help_text(), reply_markup=city_prompt_keyboard())


async def go_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    screen = get_screen(context)
    world_id = get_world_id(context)
    if screen in {SCREEN_OSM_RESULTS, SCREEN_OSM_ITEM, SCREEN_OSM_NEAR}:
        world = get_world("osm")
        if world:
            await world.show_menu(update, context)
            return
    if screen.endswith("_results"):
        prefix = screen[: -len("_results")]
        world = get_world(prefix) or (get_world(world_id) if world_id else None)
        if world:
            await world.show_menu(update, context)
            return
    if screen.endswith("_menu") or world_id:
        await show_worlds(update, context)
        return
    if screen == SCREEN_WORLDS and get_city(context):
        await show_city_prompt(update, context)
        return
    await show_city_prompt(update, context)


async def dispatch(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str) -> None:
    prefix, parts = parse_callback(data)
    if prefix in {"nav"} and parts and parts[0] == "back":
        await go_back(update, context)
        return
    if prefix == "home":
        if parts and parts[0] == "aiuto":
            await show_help(update, context)
            return
        if get_city(context):
            await show_worlds(update, context)
            return
        await show_city_prompt(update, context)
        return
    if prefix == "city":
        if not parts or parts[0] == "ask":
            await show_city_prompt(update, context)
            return
        if parts[0] == "pick" and len(parts) > 1 and parts[1].isdigit():
            await pick_city(update, context, int(parts[1]))
            return
        await show_city_prompt(update, context)
        return
    if prefix == "world":
        if not parts or parts[0] == "list":
            await show_worlds(update, context)
            return
        await open_world(update, context, parts[0])
        return
    if prefix in {"osm", *world_ids()}:
        world = get_world(prefix)
        if world:
            await world.handle(update, context, parts)
            return
        await show_worlds(update, context)
        return
    # Vecchi callback live:ow* → nuova navigazione, senza rompere messaggi in chat.
    if prefix == "live":
        if get_city(context):
            await show_worlds(update, context)
        else:
            await show_city_prompt(update, context)
        return
    if get_city(context):
        await show_worlds(update, context)
        return
    await show_city_prompt(update, context)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await show_city_prompt(update, context)
    await delete_user_command(update)


async def cmd_aiuto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await show_help(update, context)
    await delete_user_command(update)


async def cmd_osm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = [a.strip() for a in (context.args or []) if a.strip()]
    if args:
        await lookup_city(update, context, " ".join(args))
        if get_city(context) and not waiting_city(context):
            await open_world(update, context, "osm")
        await delete_user_command(update)
        return
    if get_city(context):
        await open_world(update, context, "osm")
    else:
        await show_city_prompt(update, context)
    await delete_user_command(update)


async def cmd_world(update: Update, context: ContextTypes.DEFAULT_TYPE, world_id: str) -> None:
    args = [a.strip() for a in (context.args or []) if a.strip()]
    if args:
        await lookup_city(update, context, " ".join(args))
    if get_city(context) and not waiting_city(context):
        await open_world(update, context, world_id)
    else:
        await show_city_prompt(update, context)
    await delete_user_command(update)


async def cmd_airtraffic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_world(update, context, "airtraffic")


async def cmd_sky(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_world(update, context, "sky")


async def cmd_earth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_world(update, context, "earth")


async def cmd_space(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_world(update, context, "space")


async def cmd_life(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_world(update, context, "life")


async def on_plain_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None or not message.text:
        return
    query = message.text.strip()
    if len(query) < 2:
        return
    await lookup_city(update, context, query)
    await delete_user_command(update)


async def on_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    loc = message.location if message is not None else None
    if loc is None:
        return
    lat, lon = float(loc.latitude), float(loc.longitude)
    logger.info("[CITY] location lat=%s lon=%s", lat, lon)
    from core.session import set_city
    from services.live.geocode import reverse_geocode
    from worlds.life.service import location_hit

    reverse = await asyncio.to_thread(reverse_geocode, lat, lon)
    hit = location_hit(lat, lon, reverse)
    set_city(context, hit)
    world = get_world("life")
    if world:
        await world.handle(update, context, ["near"])
        return
    await show_worlds(update, context)


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or not query.data:
        return
    remember_from_callback(update, context)
    await answer_callback(update)
    await dispatch(update, context, query.data)


async def on_unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await deliver(
        update,
        context,
        "Comando sconosciuto. /start oppure scrivi una città.",
        reply_markup=city_prompt_keyboard(),
    )


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Errore handler: %s", context.error)
    if isinstance(update, Update):
        try:
            await deliver(
                update,
                context,
                "Qualcosa si è inceppato. Riprova da /start.",
                reply_markup=city_prompt_keyboard(),
            )
        except Exception:
            pass


async def post_init(application: Application) -> None:
    try:
        await application.bot.set_my_commands(
            [
                BotCommand("start", "Inserisci una città"),
                BotCommand("osm", "OSM WORLD"),
                BotCommand("life", "CITY LIFE"),
                BotCommand("airtraffic", "AIR TRAFFIC"),
                BotCommand("sky", "SKY"),
                BotCommand("earth", "EARTH"),
                BotCommand("space", "SPACE"),
                BotCommand("aiuto", "Come funziona"),
            ]
        )
    except TelegramError as exc:
        logger.warning("Impossibile impostare i comandi: %s", exc)
    logger.info("WARBOT inizializzato (città → mondi → query)")


def build_application(token: str) -> Application:
    application = Application.builder().token(token).post_init(post_init).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler(["aiuto", "help"], cmd_aiuto))
    application.add_handler(CommandHandler(["osm", "live", "overpass"], cmd_osm))
    application.add_handler(CommandHandler(["life", "citta", "vita"], cmd_life))
    application.add_handler(CommandHandler(["airtraffic", "aerei"], cmd_airtraffic))
    application.add_handler(CommandHandler("sky", cmd_sky))
    application.add_handler(CommandHandler("earth", cmd_earth))
    application.add_handler(CommandHandler("space", cmd_space))
    application.add_handler(CallbackQueryHandler(on_callback, pattern=callback_pattern()))
    application.add_handler(MessageHandler(filters.LOCATION, on_location))
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
        url_path, public_url = resolve_webhook(webhook_url, os.getenv("WEBHOOK_PATH"))
        secret = (os.getenv("WEBHOOK_SECRET") or "").strip() or None
        install_health_routes()
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
