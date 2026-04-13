from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.db import init_db
from app.routes.admin import router as admin_router
from app.routes.webhook import router as webhook_router
from app.services.telegram_client import TelegramAPIError, TelegramClient


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app_dir = Path(__file__).resolve().parent

    app = FastAPI(title="Telegram Welcome Bot", version="1.0.0")
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        same_site="lax",
        https_only=settings.app_env == "production",
    )
    app.mount("/static", StaticFiles(directory=app_dir / "static"), name="static")

    app.include_router(webhook_router)
    app.include_router(admin_router)

    @app.on_event("startup")
    def on_startup() -> None:
        init_db()
        if settings.telegram_mode == "webhook" and settings.auto_set_webhook_on_startup and settings.base_url:
            client = TelegramClient(settings)
            try:
                client.set_webhook(settings.webhook_url, settings.webhook_secret)
            except TelegramAPIError as exc:
                logging.getLogger(__name__).warning(
                    json.dumps({"event": "set_webhook_failed_on_startup", "error": str(exc)}, ensure_ascii=False)
                )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
