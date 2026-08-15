"""Notification providers behind a protocol with dedup/cooldown handled by service."""
from __future__ import annotations

import logging
from typing import Any, Protocol

import httpx

from app.config import settings

logger = logging.getLogger("app.notifications")


class NotificationProvider(Protocol):
    name: str

    async def send(self, *, subject: str, body: str,
                   metadata: dict[str, Any] | None = None) -> bool: ...


class LogProvider:
    name = "log"

    async def send(self, *, subject: str, body: str,
                   metadata: dict[str, Any] | None = None) -> bool:
        logger.info("notification subject=%r body=%r metadata=%s", subject, body, metadata or {})
        return True


class TelegramProvider:
    name = "telegram"

    async def send(self, *, subject: str, body: str,
                   metadata: dict[str, Any] | None = None) -> bool:
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        text = f"*{subject}*\n{body[:3500]}"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    url,
                    json={"chat_id": settings.telegram_chat_id, "text": text,
                          "parse_mode": "Markdown"},
                )
                resp.raise_for_status()
            return True
        except httpx.HTTPError as exc:
            logger.warning("telegram send failed: %s", exc)
            return False


class EmailProvider:
    name = "email"

    async def send(self, *, subject: str, body: str,
                   metadata: dict[str, Any] | None = None) -> bool:
        try:
            import smtplib
            from email.mime.text import MIMEText

            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = settings.email_from
            msg["To"] = metadata.get("to") or settings.email_username or "test-manager@local"
            with smtplib.SMTP(settings.email_host, settings.email_port, timeout=15) as s:
                s.starttls()
                s.login(settings.email_username, settings.email_password)
                s.send_message(msg)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("email send failed: %s", exc)
            return False


class WebhookProvider:
    name = "webhook"

    async def send(self, *, subject: str, body: str,
                   metadata: dict[str, Any] | None = None) -> bool:
        headers = {}
        if settings.webhook_token:
            headers["Authorization"] = f"Bearer {settings.webhook_token}"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    settings.webhook_url,
                    json={"subject": subject, "body": body, "metadata": metadata or {}},
                    headers=headers,
                )
                resp.raise_for_status()
            return True
        except httpx.HTTPError as exc:
            logger.warning("webhook send failed: %s", exc)
            return False


class WhatsAppProvider:
    name = "whatsapp"

    async def send(self, *, subject: str, body: str,
                   metadata: dict[str, Any] | None = None) -> bool:
        if not settings.whatsapp_api_url:
            logger.warning("whatsapp provider enabled but WHATSAPP_API_URL unset")
            return False
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    settings.whatsapp_api_url,
                    json={"subject": subject, "message": body},
                    headers={"Authorization": f"Bearer {settings.whatsapp_api_token}"}
                    if settings.whatsapp_api_token else {},
                )
                resp.raise_for_status()
            return True
        except httpx.HTTPError as exc:
            logger.warning("whatsapp send failed: %s", exc)
            return False


def build_provider() -> NotificationProvider:
    enabled = {
        "telegram": settings.telegram_enabled,
        "email": settings.email_enabled,
        "webhook": settings.webhook_enabled,
        "whatsapp": settings.whatsapp_enabled,
        "log": True,
    }
    for name, flag in enabled.items():
        if flag:
            if name == "telegram":
                return TelegramProvider()
            if name == "email":
                return EmailProvider()
            if name == "webhook":
                return WebhookProvider()
            if name == "whatsapp":
                return WhatsAppProvider()
    return LogProvider()
