from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, update

from ..deps import get_db
from .. import models, schemas
from ..templates import templates

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/", response_class=HTMLResponse)
def queue_page(request: Request, db: Session = Depends(get_db)):
    queued = db.execute(
        select(models.Job).order_by(models.Job.status, models.Job.priority, models.Job.queued_at)
    ).scalars().all()
    programs = db.execute(select(models.Program)).scalars().all()
    return templates.TemplateResponse(
        "dashboard.html", {"request": request, "jobs": queued, "programs": programs}
    )


@router.post("/enqueue", response_class=RedirectResponse, status_code=status.HTTP_302_FOUND)
def enqueue_job_from_form(program_id: int, priority: int = 100, db: Session = Depends(get_db)):
    program = db.get(models.Program, program_id)
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")
    job = models.Job(program_id=program_id, priority=priority)
    db.add(job)
    db.commit()
    return RedirectResponse(url="/jobs/", status_code=status.HTTP_302_FOUND)


@router.get("/api", response_model=list[schemas.JobRead])
def list_jobs_api(db: Session = Depends(get_db)):
    jobs = db.execute(
        select(models.Job).order_by(models.Job.status, models.Job.priority, models.Job.queued_at)
    ).scalars().all()
    return jobs


@router.post("/api", response_model=schemas.JobRead)
def enqueue_job_api(payload: schemas.JobCreate, db: Session = Depends(get_db)):
    program = db.get(models.Program, payload.program_id)
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")
    job = models.Job(program_id=payload.program_id, priority=payload.priority)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.post("/{job_id}/pause", response_model=schemas.JobRead)
def pause_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(models.Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in (models.JobStatus.running, models.JobStatus.queued):
        raise HTTPException(status_code=400, detail="Can only pause queued or running jobs")
    job.status = models.JobStatus.paused
    db.commit()
    db.refresh(job)
    return job


@router.post("/{job_id}/resume", response_model=schemas.JobRead)
def resume_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(models.Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != models.JobStatus.paused:
        raise HTTPException(status_code=400, detail="Can only resume paused jobs")
    job.status = models.JobStatus.queued
    db.commit()
    db.refresh(job)
    return job


@router.post("/{job_id}/cancel", response_model=schemas.JobRead)
def cancel_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(models.Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status in (models.JobStatus.completed, models.JobStatus.failed, models.JobStatus.canceled):
        raise HTTPException(status_code=400, detail="Job already finished")
    job.status = models.JobStatus.canceled
    db.commit()
    db.refresh(job)
    return job


@router.post("/reorder", response_model=list[schemas.JobRead])
def reorder_queue(req: schemas.QueueReorderRequest, db: Session = Depends(get_db)):
    # Assign sequential priorities starting at 1 in the order provided
    priority = 1
    for job_id in req.job_ids_in_order:
        job = db.get(models.Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        job.priority = priority
        if job.status == models.JobStatus.paused:
            # keep paused jobs paused but reordered
            pass
        elif job.status == models.JobStatus.queued:
            pass
        priority += 1
    db.commit()
    jobs = db.execute(select(models.Job).order_by(models.Job.status, models.Job.priority, models.Job.queued_at)).scalars().all()
    return jobs