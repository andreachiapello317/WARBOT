"""Webhook Telegram: URL pubblico e health check per Render (GET / non deve 404)."""

from __future__ import annotations

import logging

log = logging.getLogger("warbot.webhook")

DEFAULT_PATH = "webhook"


def resolve_webhook(base_url: str, path: str | None = None) -> tuple[str, str]:
    """Restituisce (url_path, public_url) senza duplicare /webhook."""
    slug = (path or DEFAULT_PATH).strip().strip("/") or DEFAULT_PATH
    base = (base_url or "").strip().rstrip("/")
    if not base:
        return slug, ""
    if base.endswith("/" + slug):
        return slug, base
    return slug, f"{base}/{slug}"


def install_health_routes() -> None:
    """GET/HEAD / /health /healthz → 200, stesso processo del POST Telegram."""
    import tornado.web
    from telegram.ext._utils import webhookhandler as wh

    if getattr(wh.WebhookAppClass, "_warbot_health", False):
        return

    class HealthHandler(tornado.web.RequestHandler):
        SUPPORTED_METHODS = ("GET", "HEAD")  # type: ignore[assignment]

        def get(self) -> None:
            self.set_header("Content-Type", "text/plain; charset=utf-8")
            self.write("WARBOT ok\n")

        def head(self) -> None:
            self.set_status(200)

    orig = wh.WebhookAppClass.__init__

    def patched(self, webhook_path, bot, update_queue, secret_token=None):
        self.shared_objects = {
            "bot": bot,
            "update_queue": update_queue,
            "secret_token": secret_token,
        }
        handlers = [
            (r"/", HealthHandler),
            (r"/health/?", HealthHandler),
            (r"/healthz/?", HealthHandler),
            (rf"{webhook_path}/?", wh.TelegramHandler, self.shared_objects),
        ]
        tornado.web.Application.__init__(self, handlers)

    patched._warbot_orig = orig  # type: ignore[attr-defined]
    wh.WebhookAppClass.__init__ = patched  # type: ignore[method-assign]
    wh.WebhookAppClass._warbot_health = True  # type: ignore[attr-defined]
    log.info("webhook health routes: / /health /healthz")
