from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status

from app.config import get_settings
from app.db import SessionLocal
from app.services.telegram_client import TelegramClient
from app.services.update_processor import process_telegram_update

logger = logging.getLogger(__name__)

router = APIRouter()


def process_update_in_background(update: dict) -> None:
    settings = get_settings()
    db = SessionLocal()
    telegram_client = TelegramClient(settings)
    try:
        process_telegram_update(update=update, db=db, telegram_client=telegram_client, settings=settings)
    except Exception:
        logger.exception(json.dumps({"event": "telegram_update_processing_failed"}, ensure_ascii=False))
    finally:
        db.close()


@router.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: Optional[str] = Header(default=None),
) -> dict[str, bool]:
    settings = get_settings()
    if settings.telegram_mode != "webhook":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Telegram webhook mode is disabled")
    if settings.webhook_secret and x_telegram_bot_api_secret_token != settings.webhook_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Telegram secret token")

    update = await request.json()
    background_tasks.add_task(process_update_in_background, update)
    return {"ok": True}
