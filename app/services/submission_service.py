from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import INTERNAL_ERROR_REPLY, INVALID_SUBMISSION_REPLY, VALID_SUBMISSION_REPLY
from app.models import AdminEvent, Submission
from app.services.parser import parse_submission_text
from app.services.telegram_client import TelegramAPIError, TelegramClient

logger = logging.getLogger(__name__)

CURRENT_MEMBER_STATUSES = {"creator", "administrator", "member", "restricted"}


def _full_name(user_payload: dict[str, Any]) -> str:
    parts = [user_payload.get("first_name"), user_payload.get("last_name")]
    return " ".join(part for part in parts if part).strip() or "Unknown"


class SubmissionService:
    def __init__(self, db: Session, telegram_client: TelegramClient, group_chat_id: int) -> None:
        self.db = db
        self.telegram_client = telegram_client
        self.group_chat_id = group_chat_id

    def process_private_message(self, message: dict[str, Any]) -> None:
        sender = message["from"]
        chat = message["chat"]
        raw_text = message.get("text", "") or message.get("caption", "") or ""
        parsed = parse_submission_text(raw_text)

        duplicate_candidate = False
        if parsed.parse_valid:
            existing_valid_count = self.db.scalar(
                select(func.count(Submission.id)).where(
                    Submission.sender_user_id == sender["id"],
                    Submission.parse_valid.is_(True),
                )
            )
            duplicate_candidate = bool(existing_valid_count)

        submission = Submission(
            sender_user_id=sender["id"],
            sender_username=sender.get("username"),
            sender_full_name=_full_name(sender),
            raw_text=raw_text,
            inviter_username=parsed.inviter_username,
            hashtag_present=parsed.hashtag_present,
            parse_valid=parsed.parse_valid,
            duplicate_candidate=duplicate_candidate,
            source_message_id=message.get("message_id"),
            received_at=datetime.fromtimestamp(message["date"], tz=timezone.utc)
            if message.get("date")
            else datetime.now(timezone.utc),
            review_status="pending",
        )
        self.db.add(submission)
        self.db.flush()

        self._safe_enrich_membership(submission)

        reply_text = VALID_SUBMISSION_REPLY if parsed.parse_valid else INVALID_SUBMISSION_REPLY
        try:
            self.telegram_client.send_message(chat["id"], reply_text)
        except TelegramAPIError as exc:
            logger.error(
                json.dumps(
                    {
                        "event": "submission_reply_failed",
                        "submission_id": submission.id,
                        "sender_user_id": sender["id"],
                        "error": str(exc),
                    },
                    ensure_ascii=False,
                )
            )
            try:
                self.telegram_client.send_message(chat["id"], INTERNAL_ERROR_REPLY)
            except TelegramAPIError:
                logger.error(
                    json.dumps(
                        {
                            "event": "internal_error_reply_failed",
                            "submission_id": submission.id,
                            "sender_user_id": sender["id"],
                        },
                        ensure_ascii=False,
                    )
                )

        self.db.add(
            AdminEvent(
                event_type="submission_received",
                payload_json={
                    "submission_id": submission.id,
                    "sender_user_id": submission.sender_user_id,
                    "parse_valid": submission.parse_valid,
                    "duplicate_candidate": submission.duplicate_candidate,
                    "inviter_username": submission.inviter_username,
                },
            )
        )
        self.db.commit()

    def update_review_status(self, submission_id: int, status: str, note: Optional[str]) -> Optional[Submission]:
        submission = self.db.get(Submission, submission_id)
        if submission is None:
            return None

        submission.review_status = status
        submission.review_note = note.strip() if note else None
        submission.reviewed_at = datetime.now(timezone.utc)

        self.db.add(
            AdminEvent(
                event_type="submission_review_updated",
                payload_json={
                    "submission_id": submission.id,
                    "status": status,
                    "note": submission.review_note,
                },
            )
        )
        self.db.commit()
        self.db.refresh(submission)
        return submission

    def _safe_enrich_membership(self, submission: Submission) -> None:
        try:
            member = self.telegram_client.get_chat_member(self.group_chat_id, submission.sender_user_id)
        except TelegramAPIError as exc:
            logger.warning(
                json.dumps(
                    {
                        "event": "chat_member_lookup_failed",
                        "submission_id": submission.id,
                        "sender_user_id": submission.sender_user_id,
                        "error": str(exc),
                    },
                    ensure_ascii=False,
                )
            )
            return

        status = member.get("status")
        submission.member_status = status
        submission.is_current_member = status in CURRENT_MEMBER_STATUSES if status else None
