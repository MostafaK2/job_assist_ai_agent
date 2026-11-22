"""The fill card's buttons and the extension's reports -> one message for the agent.

Phase 1: the user's outcome for a filled form.
    submitted   the user pressed Submit on the real page -> job_applications row, queue moves on
    skipped     the user won't submit this one -> queue moves on

The fill and its draft are found on the server (from the saved fill_application tool message),
never from the browser. One outcome per application: a second one is refused (409).
"""
import re
import uuid

from fastapi import HTTPException
from langchain_core.messages import HumanMessage

from app.api.decision import Decision, next_job_text
from app.api.schemas import FillEventCommand
from app.db.applications import record_application
from app.db.chat_store import find_tool_message
from app.db.job_models import ApplicationStatus
from app.tools import job_queue, store
from app.tools.fill import FINAL, get_fill, update_fill

TITLE_CHARS = 120


async def fill_event_message(conversation_id: uuid.UUID, command: FillEventCommand) -> Decision:
    thread_id = str(conversation_id)
    saved = await find_tool_message(conversation_id, command.tool_call_id, "fill_application")
    fill_id = ((saved or {}).get("artifact") or {}).get("fill_id")
    fill = get_fill(fill_id) if fill_id else None
    if fill is None or fill["thread_id"] != thread_id:
        raise HTTPException(404, "This fill wasn't found in this chat")
    draft = store.get("drafts", fill["draft_id"])
    if draft is None:
        raise HTTPException(410, "This application has expired")
    if draft["status"] in FINAL:
        raise HTTPException(409, f"This application was already {draft['status']}")

    job_id = f'{draft["board_token"]}/{draft["job_id"]}'
    title = re.sub(r"\s+", " ", draft["title"] or "").strip()[:TITLE_CHARS]
    current = job_queue.current(thread_id)
    in_queue = current is not None and current["id"] == job_id
    label = current["label"] if in_queue else f'{job_id}: "{title}"'

    outcome = command.event   # "submitted" | "skipped"
    text = (f"I submitted the application for {label}." if outcome == "submitted"
            else f"Skip the application for {label}; I won't submit it.")
    if in_queue:
        text += next_job_text(thread_id, outcome, label)

    async def after_save():
        store.put("drafts", fill["draft_id"], {**draft, "status": outcome})
        update_fill(fill_id, status=outcome)
        if in_queue:
            job_queue.finish(thread_id, outcome)
        if outcome == "submitted":   # search hides jobs the user applied to
            await record_application(draft["board_token"], int(draft["job_id"]), draft["title"], None,
                                     ApplicationStatus.submitted)

    return Decision(
        message=HumanMessage(
            id=f"fill-done-{fill['draft_id']}",   # one outcome per application (a repeat is a 409)
            content=text,
            additional_kwargs={"metadata": {"fillEvent": {
                "toolCallId": command.tool_call_id, "event": outcome, "job": title,
            }}},
        ),
        after_save=after_save,
    )