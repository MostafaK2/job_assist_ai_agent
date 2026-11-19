"""Job tables: companies, jobs (from the Greenhouse sync) and job_applications (the user's history).

companies + jobs are fully replaced on every sync run (see app/ingest/sync_greenhouse.py).
job_applications is NEVER touched by the sync, so it links to a job by Greenhouse's own
stable ids (board_token, job_id) instead of a foreign key to jobs.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # serial; reset on each sync
    board_token: Mapped[str] = mapped_column(String(200), unique=True)
    name: Mapped[str] = mapped_column(String(300))
    job_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text)  # null = board fetched fine
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Job(Base):
    """One Greenhouse job. Unique ID = (company_id, job_id)."""

    __tablename__ = "jobs"

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True
    )
    job_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Greenhouse "id"

    # Identification
    company_name: Mapped[str] = mapped_column(String(300))
    board_token: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    absolute_url: Mapped[str | None] = mapped_column(Text)  # the apply link
    departments: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")

    # Timing
    date_posted: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # first_published
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))   # Greenhouse updated_at
    application_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # Administrative
    requisition_id: Mapped[str | None] = mapped_column(Text)
    internal_job_id: Mapped[int | None] = mapped_column(BigInteger)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    # Content
    description_html: Mapped[str | None] = mapped_column(Text)
    description_markdown: Mapped[str | None] = mapped_column(Text)
    description_text: Mapped[str | None] = mapped_column(Text)  # plain text for search / the LLM
    raw: Mapped[dict] = mapped_column(JSONB)  # the whole Greenhouse object, so no field is ever lost

    __table_args__ = (
        Index("ix_jobs_board_token_job_id", "board_token", "job_id"),
        Index("ix_jobs_is_active_company_id", "is_active", "company_id"),
    )


class ApplicationStatus(str, enum.Enum):
    draft = "draft"          # answers being prepared
    approved = "approved"    # user approved the answers (Gate 2)
    filled = "filled"        # Playwright filled the form (we never submit)
    submitted = "submitted"  # the user confirmed they clicked Submit themselves
    withdrawn = "withdrawn"
    failed = "failed"


class JobApplication(Base):
    """Has this user applied to this job? One row per (user, job)."""

    __tablename__ = "job_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Null for now (single user). Later: the logged-in user's id.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    # Greenhouse's stable ids. Deliberately NOT a foreign key to jobs: the sync
    # replaces the jobs table, and that must never delete application history.
    board_token: Mapped[str] = mapped_column(String(200))
    job_id: Mapped[int] = mapped_column(BigInteger)
    job_title: Mapped[str | None] = mapped_column(Text)      # copied in, so history reads well
    company_name: Mapped[str | None] = mapped_column(String(300))  # even after the job closes

    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus, name="application_status"),
        default=ApplicationStatus.draft,
        server_default=ApplicationStatus.draft.value,
    )
    answers: Mapped[dict | None] = mapped_column(JSONB)  # the approved draft
    screenshot_path: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        # NULLS NOT DISTINCT (Postgres 15+): two rows with user_id NULL for the same job
        # still count as duplicates. Without it, NULL != NULL and duplicates slip through.
        UniqueConstraint(
            "user_id", "board_token", "job_id",
            name="uq_job_applications_user_job",
            postgresql_nulls_not_distinct=True,
        ),
    )
