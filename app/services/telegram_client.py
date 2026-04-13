from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class TelegramAPIError(Exception):
    pass


class TelegramClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _log(self, level: str, event: str, **payload: Any) -> None:
        message = json.dumps({"event": event, **payload}, ensure_ascii=False, default=str)
        getattr(logger, level)(message)

    def _request(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.settings.telegram_api_base}/{method}"
        try:
            with httpx.Client(timeout=self.settings.request_timeout_seconds) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            self._log("error", "telegram_http_error", method=method, payload=payload, error=str(exc))
            raise TelegramAPIError(str(exc)) from exc

        if not data.get("ok", False):
            description = data.get("description", "Unknown Telegram API error")
            self._log("error", "telegram_api_error", method=method, payload=payload, response=data)
            raise TelegramAPIError(description)

        self._log("info", "telegram_api_success", method=method, payload=payload)
        return data.get("result", {})

    def _request_list(self, method: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        url = f"{self.settings.telegram_api_base}/{method}"
        timeout = max(self.settings.request_timeout_seconds, self.settings.polling_timeout_seconds + 5)
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            self._log("error", "telegram_http_error", method=method, payload=payload, error=str(exc))
            raise TelegramAPIError(str(exc)) from exc

        if not data.get("ok", False):
            description = data.get("description", "Unknown Telegram API error")
            self._log("error", "telegram_api_error", method=method, payload=payload, response=data)
            raise TelegramAPIError(description)

        self._log("info", "telegram_api_success", method=method, payload=payload)
        return data.get("result", [])

    def send_message(self, chat_id: int, text: str) -> dict[str, Any]:
        return self._request("sendMessage", {"chat_id": chat_id, "text": text})

    def approve_join_request(self, chat_id: int, user_id: int) -> bool:
        result = self._request("approveChatJoinRequest", {"chat_id": chat_id, "user_id": user_id})
        return bool(result)

    def get_chat_member(self, chat_id: int, user_id: int) -> dict[str, Any]:
        return self._request("getChatMember", {"chat_id": chat_id, "user_id": user_id})

    def set_webhook(self, url: str, secret_token: str) -> bool:
        result = self._request("setWebhook", {"url": url, "secret_token": secret_token})
        return bool(result)

    def delete_webhook(self) -> bool:
        result = self._request("deleteWebhook", {})
        return bool(result)

    def get_updates(self, offset: int | None = None, timeout: int | None = None) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {
            "timeout": timeout if timeout is not None else self.settings.polling_timeout_seconds,
            "allowed_updates": ["chat_join_request", "message"],
        }
        if offset is not None:
            payload["offset"] = offset
        return self._request_list("getUpdates", payload)
