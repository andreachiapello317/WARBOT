"""Client HTTP condiviso. Timeout, un retry su 429 breve, niente credenziali nel log."""

from __future__ import annotations

import json
import logging
import socket
import time
import urllib.error
import urllib.request
from typing import Any

log = logging.getLogger("warbot.http")

USER_AGENT = "WARBOT/1.0 (world explorer; public APIs)"
MAX_RETRY_WAIT = 4.0
DEFAULT_TIMEOUT = 12


def retry_after_s(headers: dict[str, str]) -> float:
    raw = (headers.get("retry-after") or "").strip()
    if not raw:
        return 0.0
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 0.0


def http_get(
    url: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    headers: dict[str, str] | None = None,
    user_agent: str | None = None,
) -> tuple[int, bytes, dict[str, str]]:
    hdrs = {"User-Agent": user_agent or USER_AGENT, "Accept": "application/json, text/plain;q=0.9,*/*;q=0.8"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            out = {str(k).lower(): str(v) for k, v in resp.headers.items()}
            return int(getattr(resp, "status", 200) or 200), body, out
    except TimeoutError:
        return 0, b"", {}
    except socket.timeout:
        return 0, b"", {}
    except urllib.error.HTTPError as exc:
        body = b""
        try:
            body = exc.read() or b""
        except Exception:
            body = b""
        out = {str(k).lower(): str(v) for k, v in (exc.headers.items() if exc.headers else [])}
        return int(exc.code), body, out
    except urllib.error.URLError as exc:
        reason = exc.reason
        text = str(reason).lower()
        if isinstance(reason, (TimeoutError, socket.timeout)) or "timed out" in text:
            return 0, b"", {}
        return -1, b"", {}
    except Exception:
        return -1, b"", {}


def http_get_retry(
    url: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    headers: dict[str, str] | None = None,
    user_agent: str | None = None,
) -> tuple[int, bytes, dict[str, str], float]:
    t0 = time.perf_counter()
    http, body, hdrs = http_get(url, timeout=timeout, headers=headers, user_agent=user_agent)
    if http == 429:
        wait = retry_after_s(hdrs)
        if wait <= 0:
            wait = 1.0
        if wait <= MAX_RETRY_WAIT:
            log.info("[HTTP] 429 wait=%.1fs", wait)
            time.sleep(wait)
            http, body, hdrs = http_get(url, timeout=timeout, headers=headers, user_agent=user_agent)
        else:
            log.info("[HTTP] 429 no_wait retry_after=%.1fs", wait)
    ms = (time.perf_counter() - t0) * 1000.0
    return http, body, hdrs, ms


def parse_json(body: bytes) -> tuple[Any | None, bool]:
    if not body:
        return None, False
    try:
        return json.loads(body.decode("utf-8")), False
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, True


def error_code(http: int, *, invalid_json: bool = False) -> str:
    if invalid_json:
        return "bad_json"
    if http == 0:
        return "timeout"
    if http == 429:
        return "rate"
    if http in {401, 403}:
        return "denied"
    if http == 404:
        return "not_found"
    if http >= 500:
        return "unavailable"
    if 400 <= http < 500:
        return "unavailable"
    if http < 0:
        return "network"
    return "unavailable"
