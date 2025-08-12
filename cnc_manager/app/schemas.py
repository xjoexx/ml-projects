from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


JobStatusLiteral = Literal["queued", "running", "paused", "completed", "failed", "canceled"]


class ProgramBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code_text: str
    estimated_duration_seconds: Optional[int] = Field(default=None, ge=1)


class ProgramCreate(ProgramBase):
    pass


class ProgramRead(BaseModel):
    id: int
    name: str
    code_text: str
    estimated_duration_seconds: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class JobBase(BaseModel):
    program_id: int
    priority: int = 100


class JobCreate(JobBase):
    pass


class JobRead(BaseModel):
    id: int
    program_id: int
    status: JobStatusLiteral
    priority: int
    queued_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    machine_name: Optional[str]
    error_message: Optional[str]

    class Config:
        from_attributes = True


class QueueReorderRequest(BaseModel):
    job_ids_in_order: list[int]