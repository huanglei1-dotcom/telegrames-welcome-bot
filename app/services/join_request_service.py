from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional
from typing import Any

from sqlalchemy.orm import Session

from app.config import AUTO_APPROVE_AFTER_DM, WELCOME_MESSAGE
from app.models import AdminEvent, JoinRequest
from app.services.telegram_client import TelegramAPIError, TelegramClient

logger = logging.getLogger(__name__)


def _utc_from_timestamp(timestamp: Optional[int]) -> Optional[datetime]:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def _full_name(user_payload: dict[str, Any]) -> str:
    parts = [user_payload.get("first_name"), user_payload.get("last_name")]
    return " ".join(part for part in parts if part).strip() or "Unknown"


class JoinRequestService:
    def __init__(self, db: Session, telegram_client: TelegramClient) -> None:
        self.db = db
        self.telegram_client = telegram_client

    def process_join_request(self, update: dict[str, Any]) -> None:
        chat_join_request = update["chat_join_request"]
        user = chat_join_request["from"]
        chat = chat_join_request["chat"]
        join_request = JoinRequest(
            telegram_user_id=user["id"],
            telegram_username=user.get("username"),
            full_name=_full_name(user),
            user_chat_id=chat_join_request["user_chat_id"],
            group_chat_id=chat["id"],
            invite_link=(chat_join_request.get("invite_link") or {}).get("invite_link"),
            requested_at=_utc_from_timestamp(chat_join_request.get("date")),
        )
        self.db.add(join_request)
        self.db.flush()

        dm_error: Optional[str] = None
        try:
            self.telegram_client.send_message(chat_join_request["user_chat_id"], WELCOME_MESSAGE)
            join_request.dm_sent = True
            join_request.dm_sent_at = datetime.now(timezone.utc)
        except TelegramAPIError as exc:
            dm_error = str(exc)
            join_request.dm_sent = False
            join_request.dm_error = dm_error
            logger.error(
                json.dumps(
                    {
                        "event": "join_request_dm_failed",
                        "telegram_user_id": user["id"],
                        "group_chat_id": chat["id"],
                        "error": dm_error,
                    },
                    ensure_ascii=False,
                )
            )

        if AUTO_APPROVE_AFTER_DM and join_request.dm_sent:
            try:
                self.telegram_client.approve_join_request(chat["id"], user["id"])
                join_request.approved = True
                join_request.approved_at = datetime.now(timezone.utc)
            except TelegramAPIError as exc:
                logger.error(
                    json.dumps(
                        {
                            "event": "join_request_approval_failed",
                            "telegram_user_id": user["id"],
                            "group_chat_id": chat["id"],
                            "error": str(exc),
                        },
                        ensure_ascii=False,
                    )
                )

        self.db.add(
            AdminEvent(
                event_type="join_request_processed",
                payload_json={
                    "join_request_id": join_request.id,
                    "telegram_user_id": join_request.telegram_user_id,
                    "dm_sent": join_request.dm_sent,
                    "approved": join_request.approved,
                    "dm_error": dm_error,
                },
            )
        )
        self.db.commit()
