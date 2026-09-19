"""Consegna un solo messaggio: edit preferito, RetryAfter gestito, niente loop."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from telegram import InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import RetryAfter, TelegramError
from telegram.ext import ContextTypes

from services.live.osm import clip

log = logging.getLogger("warbot.tg")

TELEGRAM_MAX_LEN = 3900
LAST_BOT_MSG_KEY = "last_bot_msg"
EMPTY_KEYBOARD = InlineKeyboardMarkup([])
MAX_FLOOD_WAIT = 4.0


def _last(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any] | None:
    last = context.chat_data.get(LAST_BOT_MSG_KEY)
    return last if isinstance(last, dict) and "id" in last else None


def remember(context: ContextTypes.DEFAULT_TYPE, message_id: int, kind: str = "text") -> None:
    context.chat_data[LAST_BOT_MSG_KEY] = {"id": message_id, "kind": kind}


def remember_from_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.message is None:
        return
    kind = "text" if query.message.text else "photo"
    remember(context, query.message.message_id, kind)


def _not_modified(exc: BaseException) -> bool:
    return "not modified" in str(exc).lower()


async def _sleep_retry_after(exc: RetryAfter) -> None:
    wait = float(getattr(exc, "retry_after", 1) or 1)
    wait = max(0.3, min(wait, MAX_FLOOD_WAIT))
    log.info("[TG] retry_after=%.1fs", wait)
    await asyncio.sleep(wait)


async def _edit(
    bot: Any,
    chat_id: int,
    message_id: int,
    text: str,
    markup: InlineKeyboardMarkup,
    hide_preview: bool,
) -> bool:
    async def once() -> None:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=hide_preview,
            reply_markup=markup,
        )

    try:
        await once()
        return True
    except RetryAfter as exc:
        await _sleep_retry_after(exc)
        try:
            await once()
            return True
        except TelegramError as exc2:
            return _not_modified(exc2)
    except TelegramError as exc:
        return _not_modified(exc)


async def _send(
    bot: Any,
    chat_id: int,
    text: str,
    markup: InlineKeyboardMarkup,
    hide_preview: bool,
) -> Any | None:
    async def once() -> Any:
        return await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=hide_preview,
            reply_markup=markup,
        )

    try:
        return await once()
    except RetryAfter as exc:
        await _sleep_retry_after(exc)
        try:
            return await once()
        except TelegramError as exc2:
            log.info("[TG] send retry failed: %s", exc2)
            return None
    except TelegramError as exc:
        log.info("[TG] send failed: %s", exc)
        return None


async def deliver(
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
    markup = reply_markup if reply_markup is not None else EMPTY_KEYBOARD
    hide_preview = not preview
    last = _last(context)
    if last and last.get("kind") == "text":
        if await _edit(context.bot, chat.id, int(last["id"]), text, markup, hide_preview):
            return
        log.info("[TG] edit skipped, one send")
    sent = await _send(context.bot, chat.id, text, markup, hide_preview)
    if sent is not None:
        remember(context, sent.message_id, "text")


async def answer_callback(update: Update) -> None:
    query = update.callback_query
    if query is None:
        return
    try:
        await query.answer()
    except RetryAfter as exc:
        await _sleep_retry_after(exc)
        try:
            await query.answer()
        except TelegramError:
            pass
    except TelegramError:
        pass


async def delete_user_command(update: Update) -> None:
    if update.callback_query is not None:
        return
    message = update.effective_message
    if message is None:
        return
    try:
        await message.delete()
    except RetryAfter:
        return
    except TelegramError:
        pass
