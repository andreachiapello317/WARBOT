"""Tastiere di navigazione condivise tra i mondi."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from core.pagination import DEFAULT_PAGE_SIZE, page_count


def kb(label: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(label, callback_data=data)


def world_nav_row(*, back: str = "world:list", back_label: str = "⬅️ Indietro") -> list[InlineKeyboardButton]:
    return [
        kb(back_label, back),
        kb("🌍 Mondi", "world:list"),
        kb("📍 Cambia città", "city:ask"),
    ]


def results_markup(
    *,
    prefix: str,
    query_id: str,
    page: int,
    total: int,
    page_size: int = DEFAULT_PAGE_SIZE,
    error: bool = False,
    extra_rows: list[list[InlineKeyboardButton]] | None = None,
    menu_callback: str | None = None,
) -> InlineKeyboardMarkup:
    menu = menu_callback or f"{prefix}:menu"
    if error:
        rows = [[kb("🔄 Riprova", f"{prefix}:{query_id}")]]
        if extra_rows:
            rows.extend(extra_rows)
        rows.append(world_nav_row(back=menu, back_label="⬅️ Indietro"))
        return InlineKeyboardMarkup(rows)
    pages = page_count(total, page_size)
    page = max(0, min(int(page), pages - 1))
    grid: list[list[InlineKeyboardButton]] = []
    if extra_rows:
        grid.extend(extra_rows)
    if total > page_size:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(kb("⬅️", f"{prefix}:{query_id}:page:{page - 1}"))
        nav.append(kb(f"Pagina {page + 1}/{pages}", f"{prefix}:{query_id}:page:{page}"))
        if page + 1 < pages:
            nav.append(kb("➡️", f"{prefix}:{query_id}:page:{page + 1}"))
        grid.append(nav)
    grid.append(world_nav_row(back=menu, back_label="⬅️ Indietro"))
    return InlineKeyboardMarkup(grid)
