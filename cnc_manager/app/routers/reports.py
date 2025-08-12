from __future__ import annotations

from datetime import timedelta
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from ..deps import get_db
from .. import models
from ..templates import templates

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/", response_class=HTMLResponse)
def reports_page(request: Request, db: Session = Depends(get_db)):
    summary = _get_summary(db)
    recent = db.execute(
        select(models.Job).order_by(models.Job.queued_at.desc()).limit(50)
    ).scalars().all()
    return templates.TemplateResponse(
        "reports.html", {"request": request, "summary": summary, "recent": recent}
    )


def _get_summary(db: Session) -> dict:
    counts = (
        db.execute(
            select(models.Job.status, func.count(models.Job.id)).group_by(models.Job.status)
        )
        .all()
    )
    avg_duration_seconds = db.execute(
        select(func.avg(func.strftime('%s', models.Job.finished_at) - func.strftime('%s', models.Job.started_at)))
        .where(models.Job.finished_at.is_not(None), models.Job.started_at.is_not(None))
    ).scalar()
    return {
        "by_status": {status.value: count for status, count in counts},
        "avg_duration_seconds": float(avg_duration_seconds) if avg_duration_seconds is not None else None,
    }