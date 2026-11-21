"""Gate 1: the user's Approve/Skip choices on a search_jobs result card -> one message for the agent.

The browser only sends {toolCallId, skipped}. Everything else comes from the search result
saved on the server, so the user can only approve jobs that search_jobs actually returned.
The approved jobs become this chat's queue (job_queue.py): the agent is told one job at a time.
"""
import re
import uuid

from fastapi import HTTPException
from langchain_core.messages import HumanMessage

from app.api.decision import Decision
from app.api.schemas import JobDecisionsCommand
from app.db.chat_store import find_tool_message
from app.tools import job_queue

TITLE_CHARS = 120  # job titles come from Greenhouse: shorten and flatten before they reach the model


def _label(row: dict) -> str:
    title = re.sub(r"\s+", " ", f"{row.get('title', '')} ({row.get('company', '')})")[:TITLE_CHARS]
    return f'{row["id"]}: "{title}"'


async def decision_message(conversation_id: uuid.UUID, command: JobDecisionsCommand) -> Decision:
    saved = await find_tool_message(conversation_id, command.tool_call_id, "search_jobs")
    rows = ((saved or {}).get("artifact") or {}).get("rows")
    if not rows:
        raise HTTPException(status_code=404, detail="Those search results weren't found in this chat")
    ids = [r["id"] for r in rows]
    unknown = set(command.skipped) - set(ids)
    if unknown:
        raise HTTPException(status_code=400, detail="You can only skip jobs from these search results")

    approved = [r for r in rows if r["id"] not in command.skipped]
    skipped = [r for r in rows if r["id"] in command.skipped]
    if approved:
        text = (f"I approved {len(approved)} job{'s' if len(approved) > 1 else ''} from the search results. "
                f"Prepare this one now: {_label(approved[0])}.")
        if len(approved) > 1:
            more = len(approved) - 1
            text += (f" {more} more {'is' if more == 1 else 'are'} queued; "
                     "I'll tell you the next one when this one is done.")
        if skipped:
            text += "\nSkipped: " + "; ".join(map(_label, skipped))
    else:
        text = "I skipped all of these jobs. Ask me what to change, then search again."

    queue = [{"id": r["id"], "label": _label(r)} for r in approved]
    return Decision(
        message=HumanMessage(
            # One decision per search: the same id again is refused as "already sent" (409).
            id=f"job-decisions-{command.tool_call_id}",
            content=text,
            # Not seen by the model. The chat shows a short summary and locks the card with it.
            additional_kwargs={"metadata": {"jobDecisions": {
                "toolCallId": command.tool_call_id,
                "approved": [r["id"] for r in approved],
                "skipped": [r["id"] for r in skipped],
            }}},
        ),
        after_save=lambda: job_queue.start(str(conversation_id), queue) if queue else None,
    )