from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings
from app.services.join_request_service import JoinRequestService
from app.services.submission_service import SubmissionService
from app.services.telegram_client import TelegramClient

logger = logging.getLogger(__name__)


def is_private_message(update: dict[str, Any]) -> bool:
    message = update.get("message")
    if not message:
        return False
    chat = message.get("chat", {})
    return chat.get("type") == "private"


def process_telegram_update(
    *,
    update: dict[str, Any],
    db: Session,
    telegram_client: TelegramClient,
    settings: Settings,
) -> None:
    if "chat_join_request" in update:
        incoming_group_chat_id = update["chat_join_request"].get("chat", {}).get("id")
        if incoming_group_chat_id == settings.telegram_group_id:
            JoinRequestService(db, telegram_client).process_join_request(update)
            return

        logger.info(
            json.dumps(
                {
                    "event": "ignored_join_request_for_other_group",
                    "incoming_group_chat_id": incoming_group_chat_id,
                    "expected_group_chat_id": settings.telegram_group_id,
                    "telegram_user_id": update["chat_join_request"].get("from", {}).get("id"),
                },
                ensure_ascii=False,
            )
        )
        return

    if is_private_message(update):
        SubmissionService(db, telegram_client, settings.telegram_group_id).process_private_message(update["message"])
        return

    logger.info(json.dumps({"event": "ignored_update", "keys": list(update.keys())}, ensure_ascii=False))
