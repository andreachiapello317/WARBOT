"""Client HTTP OpenSky Network — Python API 1.4.0, senza libreria ufficiale.

Documentazione:
  https://openskynetwork.github.io/opensky-api/python.html
  https://openskynetwork.github.io/opensky-api/rest.html

Allineato a opensky_api.OpenSkyApi / TokenManager 1.4.0:
  - OAuth2 client_credentials (TokenManager)
  - sessione HTTP riutilizzata (urllib opener, equivalente a requests.Session)
  - GET /states/all con lamin/lamax/lomin/lomax + extended=1
  - rate client-side autenticato: 5s tra get_states

Credenziali SOLO da env (mai credentials.json, mai anonymous):
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

log = logging.getLogger("warbot.opensky")

OPENSKY_ROOT = "https://opensky-network.org/api"
OPENSKY_STATES = OPENSKY_ROOT + "/states/all"
OPENSKY_TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/opensky-network"
    "/protocol/openid-connect/token"
)
USER_AGENT = "WARBOT/1.0 (OPEN SKY; OAuth2; not bulk)"
# Official TokenManager: refresh this many seconds before expiry.
TOKEN_REFRESH_MARGIN = 30
# Official OpenSkyApi._check_rate_limit(10, 5, get_states) — authenticated.
AUTH_GET_STATES_MIN_S = 5.0
MAX_429_WAIT = 5.0
TIMEOUT_DEFAULT = 8


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
    opener: urllib.request.OpenerDirector | None = None,
) -> tuple[int, bytes, dict[str, str]]:
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    open_fn = opener.open if opener is not None else urllib.request.urlopen
    try:
        with open_fn(req, timeout=timeout) as resp:
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


def _proxy_url() -> str:
    return _clean_env(os.getenv("OPENSKY_PROXY") or os.getenv("HTTPS_PROXY") or os.getenv("https_proxy"))


def _build_opener() -> urllib.request.OpenerDirector:
    proxy = _proxy_url()
    if proxy:
        log.info("[OPENSKY] proxy=on")
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({"https": proxy, "http": proxy})
        )
    return urllib.request.build_opener()


def _clean_env(raw: str | None) -> str:
    text = (raw or "").strip().strip("\ufeff")
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        text = text[1:-1].strip()
    return text


def env_credentials() -> tuple[str, str] | None:
    client_id = _clean_env(os.getenv("OPENSKY_CLIENT_ID"))
    client_secret = _clean_env(os.getenv("OPENSKY_CLIENT_SECRET"))
    if client_id and client_secret:
        return client_id, client_secret
    return None


class TokenManager:
    """OAuth2 client-credentials, come opensky_api.TokenManager 1.4.0.

    Differenza voluta: le credenziali arrivano da OPENSKY_CLIENT_ID /
    OPENSKY_CLIENT_SECRET, non da credentials.json.
    """

    def __init__(self, client_id: str, client_secret: str) -> None:
        self._lock = threading.Lock()
        self._client_id = client_id
        self._client_secret = client_secret
        self._token: str | None = None
        self._expires_at = 0.0
        self.last_status: int | None = None

    @classmethod
    def from_env(cls) -> TokenManager | None:
        creds = env_credentials()
        if not creds:
            return None
        client_id, client_secret = creds
        return cls(client_id, client_secret)

    def get_token(
        self,
        *,
        force: bool = False,
        opener: urllib.request.OpenerDirector | None = None,
    ) -> str | None:
        with self._lock:
            if not force and self._token and time.time() < self._expires_at:
                log.info("[OPENSKY] auth=reuse")
                return self._token
            return self._refresh(opener=opener)

    def auth_headers(self, *, force: bool = False) -> dict[str, str] | None:
        token = self.get_token(force=force)
        if not token:
            return None
        return {"Authorization": f"Bearer {token}"}

    def _refresh(self, opener: urllib.request.OpenerDirector | None = None) -> str | None:
        body = urllib.parse.urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
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
            opener=opener,
        )
        self.last_status = status
        if status != 200:
            log.info("[OPENSKY] auth=fail http=%s", status if status > 0 else "000")
            self._token = None
            self._expires_at = 0.0
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
        self._expires_at = time.time() + max(1, expires_in - TOKEN_REFRESH_MARGIN)
        log.info("[OPENSKY] auth=ok expires_in=%s", expires_in)
        return token


def states_query(bbox: tuple[float, float, float, float]) -> dict[str, str]:
    """Query REST per GET /states/all.

    WARBOT/REST bbox: (lamin, lomin, lamax, lomax).

    Official Python OpenSkyApi.get_states(bbox=(min_lat, max_lat, min_lon, max_lon))
    mappa gli stessi quattro valori su lamin/lamax/lomin/lomax e manda extended=True.
    """
    lamin, lomin, lamax, lomax = bbox
    return {
        "lamin": f"{lamin:.6f}",
        "lamax": f"{lamax:.6f}",
        "lomin": f"{lomin:.6f}",
        "lomax": f"{lomax:.6f}",
        "extended": "1",
    }


class OpenSkyClient:
    """Un'istanza per processo: TokenManager + opener, come OpenSkyApi 1.4.0.

    Niente accesso anonimo: senza env il client non chiama l'API.
    """

    def __init__(self, token_manager: TokenManager | None = None) -> None:
        self._lock = threading.Lock()
        self._token_manager = token_manager
        self._opener = _build_opener()
        self._last_states_at = 0.0

    def credentials(self) -> tuple[str, str] | None:
        return env_credentials()

    def configured(self) -> bool:
        return self.credentials() is not None

    def token_manager(self) -> TokenManager | None:
        with self._lock:
            if self._token_manager is not None:
                return self._token_manager
            tm = TokenManager.from_env()
            if tm is not None:
                self._token_manager = tm
            return self._token_manager

    def bearer_token(self, *, force: bool = False) -> str | None:
        tm = self.token_manager()
        if tm is None:
            return None
        try:
            return tm.get_token(force=force, opener=self._opener)
        except Exception:
            log.info("[OPENSKY] auth=fail token_error")
            return None

    def _token_fail_http(self) -> int:
        tm = self._token_manager
        status = getattr(tm, "last_status", None) if tm is not None else None
        if status is None or status == 200:
            return 401
        return int(status)

    def _headers(self, token: str) -> dict[str, str]:
        return {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        }

    def states_url(self, bbox: tuple[float, float, float, float]) -> str:
        return f"{OPENSKY_STATES}?{urllib.parse.urlencode(states_query(bbox))}"

    def _respect_states_interval(self) -> None:
        """Official authenticated get_states: minimo 5s tra una chiamata e la successiva."""
        with self._lock:
            if self._last_states_at <= 0:
                return
            wait = AUTH_GET_STATES_MIN_S - (time.time() - self._last_states_at)
        if wait > 0:
            log.info("[OPENSKY] rate wait=%.1fs", wait)
            time.sleep(min(wait, AUTH_GET_STATES_MIN_S))

    def _mark_states(self) -> None:
        with self._lock:
            self._last_states_at = time.time()

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
            http = self._token_fail_http()
            log.info("[OPENSKY] auth=fail http=%s", http if http > 0 else "000")
            return http, b""

        self._respect_states_interval()
        url = self.states_url(bbox)
        log.info("[AIRCRAFT] request_start")
        t0 = time.time()
        http, body, headers = http_request(
            url, headers=self._headers(token), timeout=TIMEOUT_S, opener=self._opener
        )

        if http == 401:
            # Un solo refresh del token, poi stop. 403: nessun retry.
            try:
                token = self.bearer_token(force=True)
            except Exception:
                token = None
            if token:
                http, body, headers = http_request(
                    url, headers=self._headers(token), timeout=TIMEOUT_S, opener=self._opener
                )
        elif http == 403:
            log.info("[OPENSKY] auth=denied http=403")
        elif http == 429:
            wait = retry_after_seconds(headers)
            if wait is not None and 0 < wait <= MAX_429_WAIT:
                log.info("[OPENSKY] rate wait=%.1fs", wait)
                time.sleep(wait)
                http, body, headers = http_request(
                    url, headers=self._headers(token), timeout=TIMEOUT_S, opener=self._opener
                )
            else:
                log.info("[OPENSKY] rate no_wait retry_after=%s", wait)
        elif http in {500, 502, 503, 504}:
            log.info("[OPENSKY] retry http=%s", http)
            http, body, headers = http_request(
                url, headers=self._headers(token), timeout=TIMEOUT_S, opener=self._opener
            )

        if http == 200:
            self._mark_states()

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
