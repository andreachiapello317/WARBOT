"""Webhook URL e health check: niente 404 su GET /."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock

from core.webhook import install_health_routes, resolve_webhook


class ResolveWebhookTest(unittest.TestCase):
    def test_appends_path(self) -> None:
        path, url = resolve_webhook("https://warbot.onrender.com", "webhook")
        self.assertEqual(path, "webhook")
        self.assertEqual(url, "https://warbot.onrender.com/webhook")

    def test_no_double_webhook(self) -> None:
        path, url = resolve_webhook("https://warbot.onrender.com/webhook", "webhook")
        self.assertEqual(path, "webhook")
        self.assertEqual(url, "https://warbot.onrender.com/webhook")

    def test_trailing_slash_on_base(self) -> None:
        path, url = resolve_webhook("https://warbot.onrender.com/webhook/", "webhook")
        self.assertEqual(url, "https://warbot.onrender.com/webhook")
        self.assertEqual(path, "webhook")

    def test_empty_path_defaults(self) -> None:
        path, url = resolve_webhook("https://warbot.onrender.com", "")
        self.assertEqual(path, "webhook")
        self.assertEqual(url, "https://warbot.onrender.com/webhook")


class HealthRouteTest(unittest.TestCase):
    def test_get_root_is_not_404(self) -> None:
        install_health_routes()
        from telegram.ext._utils.webhookhandler import WebhookAppClass

        app = WebhookAppClass("/webhook", MagicMock(), asyncio.Queue())
        request = MagicMock()
        request.host = "localhost"
        request.path = "/"
        request.method = "GET"
        handler = app.find_handler(request)
        self.assertIsNotNone(handler)
        self.assertEqual(handler.handler_class.__name__, "HealthHandler")

    def test_post_webhook_still_telegram(self) -> None:
        install_health_routes()
        from telegram.ext._utils.webhookhandler import TelegramHandler, WebhookAppClass

        app = WebhookAppClass("/webhook", MagicMock(), asyncio.Queue())
        request = MagicMock()
        request.host = "localhost"
        request.path = "/webhook"
        request.method = "POST"
        handler = app.find_handler(request)
        self.assertIs(handler.handler_class, TelegramHandler)


if __name__ == "__main__":
    unittest.main()
