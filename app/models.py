from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )


class JoinRequest(TimestampMixin, Base):
    __tablename__ = "join_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    telegram_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    user_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    group_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    invite_link: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requested_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    dm_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dm_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    dm_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class Submission(TimestampMixin, Base):
    __tablename__ = "submissions"
    __table_args__ = (
        Index("ix_submissions_review_status", "review_status"),
        Index("ix_submissions_duplicate_candidate", "duplicate_candidate"),
        Index("ix_submissions_parse_valid", "parse_valid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sender_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    sender_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sender_full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    inviter_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    hashtag_present: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    parse_valid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    duplicate_candidate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    member_status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_current_member: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    source_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    review_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    review_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class AdminEvent(Base):
    __tablename__ = "admin_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class BotState(Base):
    __tablename__ = "bot_state"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
