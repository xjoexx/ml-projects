from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..deps import get_db
from .. import models, schemas
from ..templates import templates

router = APIRouter(prefix="/programs", tags=["programs"])


@router.get("/", response_class=HTMLResponse)
def list_programs_page(request: Request, db: Session = Depends(get_db)):
    programs = db.execute(select(models.Program).order_by(models.Program.created_at.desc())).scalars().all()
    return templates.TemplateResponse("programs.html", {"request": request, "programs": programs})


@router.post("/create", response_class=RedirectResponse, status_code=status.HTTP_302_FOUND)
def create_program_form(
    name: str,
    code_text: str,
    estimated_duration_seconds: int | None = None,
    db: Session = Depends(get_db),
):
    existing = db.execute(select(models.Program).where(models.Program.name == name)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Program with this name already exists")
    program = models.Program(
        name=name,
        code_text=code_text,
        estimated_duration_seconds=estimated_duration_seconds,
    )
    db.add(program)
    db.commit()
    return RedirectResponse(url="/programs/", status_code=status.HTTP_302_FOUND)


@router.get("/api", response_model=list[schemas.ProgramRead])
def list_programs_api(db: Session = Depends(get_db)):
    programs = db.execute(select(models.Program).order_by(models.Program.created_at.desc())).scalars().all()
    return programs


@router.post("/api", response_model=schemas.ProgramRead)
def create_program_api(payload: schemas.ProgramCreate, db: Session = Depends(get_db)):
    existing = db.execute(select(models.Program).where(models.Program.name == payload.name)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Program with this name already exists")
    program = models.Program(**payload.model_dump())
    db.add(program)
    db.commit()
    db.refresh(program)
    return program