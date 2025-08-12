from __future__ import annotations

import enum
from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Enum,
    ForeignKey,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from .database import Base


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    paused = "paused"
    completed = "completed"
    failed = "failed"
    canceled = "canceled"


class Program(Base):
    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    code_text: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    jobs: Mapped[list[Job]] = relationship("Job", back_populates="program", cascade="all, delete-orphan")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    program_id: Mapped[int] = mapped_column(Integer, ForeignKey("programs.id"), nullable=False, index=True)
    program: Mapped[Program] = relationship("Program", back_populates="jobs")

    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.queued, index=True, nullable=False)

    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False, index=True)

    queued_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    machine_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)