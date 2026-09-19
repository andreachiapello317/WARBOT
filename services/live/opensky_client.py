"""Client HTTP OpenSky Network — OAuth2 client credentials, sessione riutilizzabile.

Documentazione: https://openskynetwork.github.io/opensky-api/rest.html

GET https://opensky-network.org/api/states/all
  lamin, lomin, lamax, lomax

Auth: POST client_credentials su
  https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token

Credenziali SOLO da env:
  OPENSKY_CLIENT_ID
  OPENSKY_CLIENT_SECRET

Niente username/password, niente Basic Auth, niente accesso anonimo.
Niente credenziali nei log.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

log = logging.getLogger("warbot.opensky")

OPENSKY_ROOT = "https://opensky-network.org/api"
OPENSKY_STATES = OPENSKY_ROOT + "/states/all"
OPENSKY_TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/opensky-network"
    "/protocol/openid-connect/token"
)
USER_AGENT = "WARBOT/1.0 (OPEN SKY; OAuth2; not bulk)"
TOKEN_REFRESH_MARGIN = 30
MAX_429_WAIT = 5.0
TIMEOUT_DEFAULT = 12


def _int_env(name: str, default: int, *, lo: int | None = None, hi: int | None = None) -> int:
    raw = (os.getenv(name) or "").strip()
    try:
        value = int(raw) if raw else default
    except ValueError:
        value = default
    if lo is not None:
        value = max(lo, value)
    if hi is not None:
        value = min(hi, value)
    return value


TIMEOUT_S = _int_env("OPENSKY_TIMEOUT", TIMEOUT_DEFAULT, lo=5, hi=25)


def _header_get(headers: dict[str, str], *names: str) -> str:
    lower = {str(k).lower(): str(v) for k, v in headers.items()}
    for name in names:
        value = lower.get(name.lower())
        if value:
            return value
    return ""


def retry_after_seconds(headers: dict[str, str]) -> float | None:
    raw = _header_get(headers, "X-Rate-Limit-Retry-After-Seconds", "Retry-After")
    if not raw:
        return None
    try:
        return max(0.0, float(raw.strip().split()[0]))
    except ValueError:
        return None


def http_request(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    timeout: int = TIMEOUT_S,
) -> tuple[int, bytes, dict[str, str]]:
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(resp.status), resp.read(), {str(k): str(v) for k, v in resp.headers.items()}
    except urllib.error.HTTPError as exc:
        body = b""
        try:
            body = exc.read()
        except Exception:
            body = b""
        hdrs = {str(k): str(v) for k, v in dict(exc.headers or {}).items()}
        return int(exc.code or 0), body, hdrs
    except TimeoutError:
        return 0, b"", {}
    except urllib.error.URLError as exc:
        reason = str(exc.reason or exc)
        if "timed out" in reason.lower() or isinstance(exc.reason, TimeoutError):
            return 0, b"", {}
        return -1, b"", {}


class OpenSkyClient:
    """Un'istanza per processo: token riusato fino a ~30 minuti."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._token: str | None = None
        self._expires_at = 0.0

    def credentials(self) -> tuple[str, str] | None:
        client_id = (os.getenv("OPENSKY_CLIENT_ID") or "").strip()
        client_secret = (os.getenv("OPENSKY_CLIENT_SECRET") or "").strip()
        if client_id and client_secret:
            return client_id, client_secret
        return None

    def configured(self) -> bool:
        return self.credentials() is not None

    def _fetch_access_token(self) -> str | None:
        creds = self.credentials()
        if not creds:
            return None
        client_id, client_secret = creds
        body = urllib.parse.urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            }
        ).encode("utf-8")
        log.info("[OPENSKY] auth=token_fetch")
        status, raw, _headers = http_request(
            OPENSKY_TOKEN_URL,
            method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
            data=body,
            timeout=TIMEOUT_S,
        )
        if status != 200:
            log.info("[OPENSKY] auth=fail http=%s", status if status > 0 else "000")
            return None
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            log.info("[OPENSKY] auth=fail bad_json")
            return None
        token = str(payload.get("access_token") or "").strip()
        if not token:
            log.info("[OPENSKY] auth=fail empty_token")
            return None
        expires_in = int(payload.get("expires_in") or 1800)
        self._token = token
        self._expires_at = time.time() + max(60, expires_in - TOKEN_REFRESH_MARGIN)
        log.info("[OPENSKY] auth=ok expires_in=%s", expires_in)
        return token

    def bearer_token(self, *, force: bool = False) -> str | None:
        with self._lock:
            if not force and self._token and time.time() < self._expires_at:
                log.info("[OPENSKY] auth=reuse")
                return self._token
            return self._fetch_access_token()

    def _headers(self, token: str) -> dict[str, str]:
        return {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        }

    def states_url(self, bbox: tuple[float, float, float, float]) -> str:
        lamin, lomin, lamax, lomax = bbox
        query = urllib.parse.urlencode(
            {
                "lamin": f"{lamin:.6f}",
                "lomin": f"{lomin:.6f}",
                "lamax": f"{lamax:.6f}",
                "lomax": f"{lomax:.6f}",
            }
        )
        return f"{OPENSKY_STATES}?{query}"

    def get_states(self, bbox: tuple[float, float, float, float]) -> tuple[int, bytes]:
        """GET /states/all autenticata. 401: un refresh. 429: Retry-After breve. 5xx: un retry."""
        if not self.configured():
            log.info("[OPENSKY] not_configured")
            return -2, b""
        try:
            token = self.bearer_token()
        except Exception:
            log.info("[OPENSKY] auth=fail token_error")
            return 401, b""
        if not token:
            return 401, b""

        url = self.states_url(bbox)
        log.info("[AIRCRAFT] request_start")
        t0 = time.time()
        http, body, headers = http_request(url, headers=self._headers(token), timeout=TIMEOUT_S)

        if http == 401:
            # Un solo refresh del token, poi stop. 403: nessun retry.
            try:
                token = self.bearer_token(force=True)
            except Exception:
                token = None
            if token:
                http, body, headers = http_request(url, headers=self._headers(token), timeout=TIMEOUT_S)
        elif http == 403:
            log.info("[OPENSKY] auth=denied http=403")
        elif http == 429:
            wait = retry_after_seconds(headers)
            if wait is not None and 0 < wait <= MAX_429_WAIT:
                log.info("[OPENSKY] rate wait=%.1fs", wait)
                time.sleep(wait)
                http, body, headers = http_request(url, headers=self._headers(token), timeout=TIMEOUT_S)
            else:
                log.info("[OPENSKY] rate no_wait retry_after=%s", wait)
        elif http in {500, 502, 503, 504}:
            log.info("[OPENSKY] retry http=%s", http)
            http, body, headers = http_request(url, headers=self._headers(token), timeout=TIMEOUT_S)

        elapsed_ms = int(round((time.time() - t0) * 1000))
        log.info("[AIRCRAFT] request_end")
        log.info("[AIRCRAFT] http=%s", http if http > 0 else "000")
        log.info("[AIRCRAFT] elapsed=%sms", elapsed_ms)
        return http, body


_CLIENT: OpenSkyClient | None = None
_CLIENT_LOCK = threading.Lock()


def get_opensky_client() -> OpenSkyClient:
    """Stessa istanza per tutti i callback Telegram."""
    global _CLIENT
    with _CLIENT_LOCK:
        if _CLIENT is None:
            _CLIENT = OpenSkyClient()
        return _CLIENT


def reset_opensky_client() -> None:
    """Solo test."""
    global _CLIENT
    with _CLIENT_LOCK:
        _CLIENT = None
