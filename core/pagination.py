"""Paginazione locale. Non rifà le API se i risultati sono già in sessione."""

from __future__ import annotations

from typing import Any, Sequence

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50


def page_count(total: int, size: int = DEFAULT_PAGE_SIZE) -> int:
    size = max(1, min(MAX_PAGE_SIZE, int(size)))
    if total <= 0:
        return 1
    return max(1, (int(total) + size - 1) // size)


def clamp_page(page: int, total: int, size: int = DEFAULT_PAGE_SIZE) -> int:
    return max(0, min(int(page), page_count(total, size) - 1))


def page_slice(rows: Sequence[Any], page: int, size: int = DEFAULT_PAGE_SIZE) -> list[Any]:
    size = max(1, min(MAX_PAGE_SIZE, int(size)))
    start = max(0, int(page)) * size
    return list(rows[start : start + size])
