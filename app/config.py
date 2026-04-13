from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

WELCOME_MESSAGE = """¡Bienvenido al grupo oficial de Insta360 España! 👋🇪🇸

🎉 ¡Al unirte al grupo, ya estás participando en el sorteo! El ganador se anunciará el 21 de abril.

👉 Si un amigo te invitó, responde a este mensaje con:
@TuUsuario #insta360recomendado

🎁 Además, por cada amigo que invites tú y que se una al grupo, consigues +1 oportunidad extra.

Solo tiene que unirse y mencionarte respondiendo a este bot con:
@TuUsuario #insta360recomendado

👀 Así, tu amigo también participa en el sorteo."""

AUTO_APPROVE_AFTER_DM = True
VALID_SUBMISSION_REPLY = "¡Gracias! Hemos recibido tu recomendación y la revisaremos manualmente. ✅"
INVALID_SUBMISSION_REPLY = "Por favor, responde con este formato: @usuario #insta360recomendado"
INTERNAL_ERROR_REPLY = "Lo sentimos, ha ocurrido un error. Inténtalo de nuevo más tarde."


@dataclass
class Settings:
    bot_token: str
    telegram_group_id: int
    admin_password: str
    base_url: str = ""
    webhook_secret: str = ""
    app_env: str = "development"
    database_url: str = "sqlite:///./telegram_welcome_bot.db"
    request_timeout_seconds: float = 15.0
    auto_set_webhook_on_startup: bool = False
    telegram_mode: str = "polling"
    polling_timeout_seconds: int = 30
    polling_retry_seconds: float = 3.0

    @property
    def telegram_api_base(self) -> str:
        return f"https://api.telegram.org/bot{self.bot_token}"

    @property
    def session_secret(self) -> str:
        source = f"{self.admin_password}:{self.bot_token}:{self.webhook_secret}:{self.app_env}"
        return hashlib.sha256(source.encode("utf-8")).hexdigest()

    @property
    def webhook_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/telegram/webhook"


def _require_env(name: str, default: Optional[str] = None) -> str:
    value = os.getenv(name, default)
    if value is None or value == "":
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        bot_token=_require_env("BOT_TOKEN"),
        telegram_group_id=int(_require_env("TELEGRAM_GROUP_ID")),
        admin_password=_require_env("ADMIN_PASSWORD"),
        base_url=os.getenv("BASE_URL", ""),
        webhook_secret=os.getenv("WEBHOOK_SECRET", ""),
        app_env=os.getenv("APP_ENV", "development"),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./telegram_welcome_bot.db"),
        request_timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "15")),
        auto_set_webhook_on_startup=os.getenv("AUTO_SET_WEBHOOK_ON_STARTUP", "false").lower() == "true",
        telegram_mode=os.getenv("TELEGRAM_MODE", "polling").lower(),
        polling_timeout_seconds=int(os.getenv("POLLING_TIMEOUT_SECONDS", "30")),
        polling_retry_seconds=float(os.getenv("POLLING_RETRY_SECONDS", "3")),
    )
