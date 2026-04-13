from __future__ import annotations

import json
import logging
import time
from typing import Optional

from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.main import configure_logging
from app.models import BotState
from app.services.telegram_client import TelegramAPIError, TelegramClient
from app.services.update_processor import process_telegram_update

logger = logging.getLogger(__name__)


def load_offset() -> Optional[int]:
    db = SessionLocal()
    try:
        row = db.scalar(select(BotState).where(BotState.key == "telegram_polling_offset"))
        if row is None:
            return None
        offset = row.value_json.get("offset")
        return int(offset) if offset is not None else None
    finally:
        db.close()


def save_offset(offset: int) -> None:
    db = SessionLocal()
    try:
        row = db.scalar(select(BotState).where(BotState.key == "telegram_polling_offset"))
        payload = {"offset": offset}
        if row is None:
            db.add(BotState(key="telegram_polling_offset", value_json=payload))
        else:
            row.value_json = payload
        db.commit()
    finally:
        db.close()


def run_polling_worker() -> None:
    configure_logging()
    settings = get_settings()
    init_db()

    if settings.telegram_mode != "polling":
        logger.warning(
            json.dumps({"event": "polling_mode_disabled", "telegram_mode": settings.telegram_mode}, ensure_ascii=False)
        )
        return

    telegram_client = TelegramClient(settings)
    try:
        telegram_client.delete_webhook()
        logger.info(json.dumps({"event": "webhook_deleted_before_polling"}, ensure_ascii=False))
    except TelegramAPIError as exc:
        logger.warning(json.dumps({"event": "delete_webhook_failed", "error": str(exc)}, ensure_ascii=False))

    while True:
        db = SessionLocal()
        try:
            offset = load_offset()
            updates = telegram_client.get_updates(offset=offset, timeout=settings.polling_timeout_seconds)
            for update in updates:
                process_telegram_update(update=update, db=db, telegram_client=telegram_client, settings=settings)
                save_offset(int(update["update_id"]) + 1)
        except TelegramAPIError as exc:
            logger.error(json.dumps({"event": "polling_request_failed", "error": str(exc)}, ensure_ascii=False))
            time.sleep(settings.polling_retry_seconds)
        except Exception:
            logger.exception(json.dumps({"event": "polling_loop_failed"}, ensure_ascii=False))
            time.sleep(settings.polling_retry_seconds)
        finally:
            db.close()


if __name__ == "__main__":
    run_polling_worker()
