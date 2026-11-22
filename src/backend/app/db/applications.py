"""job_applications rows: "has this user applied to this job?" (search hides these jobs)."""
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert

from app.db.engine import SessionLocal
from app.db.job_models import ApplicationStatus, JobApplication


async def record_application(board_token: str, job_id: int, title: str | None,
                             company: str | None, status: ApplicationStatus) -> None:
    """Insert or update the row for this job. Answers aren't copied here: they hold private values."""
    now = datetime.now(timezone.utc)
    stamps = {ApplicationStatus.submitted: {"submitted_at": now}, ApplicationStatus.filled: {"filled_at": now},
              ApplicationStatus.approved: {"approved_at": now}}.get(status, {})
    values = {"board_token": board_token, "job_id": job_id, "job_title": title,
              "company_name": company, "status": status, **stamps}
    stmt = insert(JobApplication).values(user_id=None, **values)
    stmt = stmt.on_conflict_do_update(constraint="uq_job_applications_user_job",
                                      set_={"status": status, "updated_at": now, **stamps})
    async with SessionLocal() as session:
        await session.execute(stmt)
        await session.commit()