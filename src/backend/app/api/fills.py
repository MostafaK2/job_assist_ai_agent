"""/api/fills: the fill card (chat page) gets the fill plan and the resume, then hands them to the
Job Assist extension. Private values in the plan go to the user's own browser only.

    POST /api/fills/{fill_id}/plan    {threadId, again}  -> the plan; starts the fill ONCE
                                       (again=true only from the card's "Fill again" button)
    GET  /api/fills/{fill_id}/resume?threadId=...       -> the resume PDF
"""
import logging
import time
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.tools import store
from app.tools.apply import BACKEND_DIR
from app.tools.fill import FINAL, build_plan, get_fill, update_fill
from app.tools.profile import load_full_profile

log = logging.getLogger("agent.api")
router = APIRouter(prefix="/fills")

FillId = Annotated[str, Path(pattern=r"^fill_[0-9a-f]{12}$")]
NO_STORE = {"Cache-Control": "no-store"}   # the plan and resume hold private data


class PlanRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    thread_id: str = Field(alias="threadId", min_length=1, max_length=100)
    again: bool = False


def _fill_and_draft(fill_id: str, thread_id: str) -> tuple[dict, dict]:
    """The fill session and its draft. The thread id must match: a fill belongs to one chat."""
    fill = get_fill(fill_id)
    if fill is None or fill["thread_id"] != thread_id:
        raise HTTPException(404, "This fill wasn't found in this chat")
    draft = store.get("drafts", fill["draft_id"])
    if draft is None:
        raise HTTPException(410, "This application has expired. Ask me to prepare it again.")
    return fill, draft


@router.post("/{fill_id}/plan")
def fill_plan(fill_id: FillId, body: PlanRequest):
    fill, draft = _fill_and_draft(fill_id, body.thread_id)
    if draft["status"] in FINAL:
        raise HTTPException(409, f"This application was already {draft['status']}")
    if fill["status"] != "created" and not body.again:
        raise HTTPException(409, "This form was already opened")   # a reload must not reopen it
    try:
        profile = load_full_profile()
    except (OSError, LookupError, ValueError) as err:
        log.warning("fill plan: profile failed: %r", err)
        raise HTTPException(503, "Your profile couldn't be loaded") from err
    update_fill(fill_id, status="started", started_at=time.time())
    return JSONResponse(build_plan(fill_id, draft, profile), headers=NO_STORE)


@router.get("/{fill_id}/resume")
def fill_resume(fill_id: FillId, thread_id: Annotated[str, Query(alias="threadId", max_length=100)]):
    _, draft = _fill_and_draft(fill_id, thread_id)
    raw = draft.get("resume_file")
    path = (BACKEND_DIR / raw).resolve() if raw else None
    try:
        ok = (path is not None and path.is_relative_to(BACKEND_DIR) and path.is_file()
              and path.read_bytes()[:5] == b"%PDF-")
    except OSError:
        ok = False
    if not ok:
        raise HTTPException(404, "No resume file on record")
    return FileResponse(path, media_type="application/pdf", filename=path.name, headers=NO_STORE)