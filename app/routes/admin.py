from __future__ import annotations

import csv
import io
import secrets
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import case, distinct, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db_session
from app.models import JoinRequest, Submission
from app.services.submission_service import SubmissionService
from app.services.telegram_client import TelegramClient

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def _is_authenticated(request: Request) -> bool:
    return bool(request.session.get("admin_authenticated"))


def _redirect(path: str) -> RedirectResponse:
    return RedirectResponse(url=path, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, db: Session = Depends(get_db_session)) -> HTMLResponse:
    if not _is_authenticated(request):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": request.query_params.get("error")},
        )

    summary = {
        "total_join_requests": db.scalar(select(func.count(JoinRequest.id))) or 0,
        "dms_sent": db.scalar(select(func.count(JoinRequest.id)).where(JoinRequest.dm_sent.is_(True))) or 0,
        "approvals": db.scalar(select(func.count(JoinRequest.id)).where(JoinRequest.approved.is_(True))) or 0,
        "total_submissions": db.scalar(select(func.count(Submission.id))) or 0,
        "pending_submissions": db.scalar(
            select(func.count(Submission.id)).where(Submission.review_status == "pending")
        )
        or 0,
        "approved_submissions": db.scalar(
            select(func.count(Submission.id)).where(Submission.review_status == "approved")
        )
        or 0,
        "rejected_submissions": db.scalar(
            select(func.count(Submission.id)).where(Submission.review_status == "rejected")
        )
        or 0,
    }
    return templates.TemplateResponse(request=request, name="dashboard.html", context={"summary": summary})


@router.post("/admin/login")
def admin_login(request: Request, password: str = Form(...)) -> RedirectResponse:
    settings = get_settings()
    if not secrets.compare_digest(password, settings.admin_password):
        return _redirect("/admin?error=Credenciales%20inválidas")

    request.session["admin_authenticated"] = True
    return _redirect("/admin")


@router.post("/admin/logout")
def admin_logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return _redirect("/admin")


@router.get("/admin/submissions", response_class=HTMLResponse)
def submissions_page(
    request: Request,
    status_filter: str = Query("all", alias="status"),
    valid_only: bool = Query(False),
    duplicates_only: bool = Query(False),
    db: Session = Depends(get_db_session),
) -> HTMLResponse:
    if not _is_authenticated(request):
        return _redirect("/admin")

    query = select(Submission).order_by(Submission.received_at.desc(), Submission.id.desc())
    if status_filter != "all":
        query = query.where(Submission.review_status == status_filter)
    if valid_only:
        query = query.where(Submission.parse_valid.is_(True))
    if duplicates_only:
        query = query.where(Submission.duplicate_candidate.is_(True))

    submissions = db.scalars(query).all()
    context = {
        "submissions": submissions,
        "filters": {
            "status": status_filter,
            "valid_only": valid_only,
            "duplicates_only": duplicates_only,
        },
    }
    return templates.TemplateResponse(request=request, name="submissions.html", context=context)


@router.post("/admin/submissions/{submission_id}/review")
def review_submission(
    request: Request,
    submission_id: int,
    action: str = Form(...),
    note: Optional[str] = Form(default=None),
    db: Session = Depends(get_db_session),
) -> RedirectResponse:
    if not _is_authenticated(request):
        return _redirect("/admin")
    if action not in {"approved", "rejected", "pending"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported action")

    settings = get_settings()
    service = SubmissionService(db, TelegramClient(settings), settings.telegram_group_id)
    submission = service.update_review_status(submission_id, action, note)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    return _redirect("/admin/submissions")


@router.get("/admin/stats", response_class=HTMLResponse)
def admin_stats(request: Request, db: Session = Depends(get_db_session)) -> HTMLResponse:
    if not _is_authenticated(request):
        return _redirect("/admin")

    leaderboard_query = (
        select(
            Submission.inviter_username,
            func.count(Submission.id).label("total_submissions"),
            func.sum(case((Submission.review_status == "approved", 1), else_=0)).label("approved_submissions"),
            func.count(distinct(Submission.sender_user_id)).label("unique_senders"),
        )
        .where(Submission.inviter_username.is_not(None))
        .group_by(Submission.inviter_username)
        .order_by(func.count(Submission.id).desc(), Submission.inviter_username.asc())
    )
    leaderboard = db.execute(leaderboard_query).all()
    return templates.TemplateResponse(request=request, name="stats.html", context={"leaderboard": leaderboard})


@router.get("/admin/export.csv")
def export_csv(request: Request, db: Session = Depends(get_db_session)) -> StreamingResponse:
    if not _is_authenticated(request):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    submissions = db.scalars(select(Submission).order_by(Submission.id.asc())).all()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "received_at",
            "sender_username",
            "sender_user_id",
            "sender_full_name",
            "inviter_username",
            "hashtag_present",
            "parse_valid",
            "duplicate_candidate",
            "member_status",
            "is_current_member",
            "review_status",
            "review_note",
            "raw_text",
        ]
    )
    for submission in submissions:
        writer.writerow(
            [
                submission.id,
                submission.received_at.isoformat() if submission.received_at else "",
                submission.sender_username or "",
                submission.sender_user_id,
                submission.sender_full_name,
                submission.inviter_username or "",
                submission.hashtag_present,
                submission.parse_valid,
                submission.duplicate_candidate,
                submission.member_status or "",
                submission.is_current_member,
                submission.review_status,
                submission.review_note or "",
                submission.raw_text,
            ]
        )

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=submissions.csv"},
    )
