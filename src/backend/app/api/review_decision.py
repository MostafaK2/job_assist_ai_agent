"""Gate 2: the user's decision on a review card (a save_models_answers result) -> one message.

The browser sends {toolCallId, decision, edits, note}. The draft is found on the server (from the
saved tool message, never the browser), the user's edits are checked like the model's answers,
and the draft's status is set here, in code. The user's own answers (phone, self-ID...) are saved
to the draft only: they never appear in the message the model gets.

    approve   edits applied, nothing required left -> draft "approved" -> next job in the queue
    skip      draft "skipped" -> next job in the queue
    changes   the note goes to the model, which saves a new draft (a new card)
"""
import re
import uuid

from fastapi import HTTPException
from langchain_core.messages import HumanMessage

from app.api.decision import Decision
from app.api.schemas import ReviewDecisionCommand
from app.db.chat_store import find_tool_message
from app.tools import job_queue, store
from app.tools.apply import _required, check_answer

TITLE_CHARS = 120


def _flat(text: str, limit: int) -> str:
    return re.sub(r"\s+", " ", text or "").strip()[:limit]


def _next_step(thread_id: str, outcome: str, label: str) -> str:
    """What to do after this job, from the queue (written by code, so the order can't drift)."""
    if (nxt := job_queue.peek_next(thread_id)) is not None:
        return f" Next, prepare this one: {nxt['label']}."
    done = job_queue.summary(thread_id)
    done[outcome].append(label)
    parts = [f"{k.capitalize()}: {'; '.join(v)}." for k, v in done.items() if v]
    return " That was the last approved job. " + " ".join(parts) + " Summarize this in one or two lines."


async def review_message(conversation_id: uuid.UUID, command: ReviewDecisionCommand) -> Decision:
    saved = await find_tool_message(conversation_id, command.tool_call_id, "save_models_answers")
    draft_id = ((saved or {}).get("artifact") or {}).get("draft_id")
    draft = store.get("drafts", draft_id) if draft_id else None
    if draft is None:
        raise HTTPException(404, "This draft has expired. Ask me to prepare the application again.")
    app = store.get("applications", draft["application_id"]) or {}
    if app.get("latest_draft") != draft_id:
        raise HTTPException(409, "There's a newer version of this application below")
    if draft["status"] in ("approved", "skipped"):
        raise HTTPException(409, "You already decided on this application")

    thread_id = str(conversation_id)
    job_id = f'{draft["board_token"]}/{draft["job_id"]}'
    current = job_queue.current(thread_id)
    in_queue = current is not None and current["id"] == job_id
    label = current["label"] if in_queue else f'{job_id}: "{_flat(draft["title"], TITLE_CHARS)}"'

    updates: dict = {}
    if command.decision == "approve":
        fields = {f["name"]: f for f in draft["fields"]}
        answers, sources, problems = dict(draft["answers"]), dict(draft["sources"]), []
        for name, raw in command.edits.items():
            if name not in draft["editable"] or name not in fields:
                problems.append({"name": name, "issue": "this answer can't be changed here"})
                continue
            value, problem = check_answer(fields[name], raw)
            if problem:
                problems.append({"name": name, "label": fields[name]["label"], "issue": problem})
            elif value != answers.get(name):
                answers[name], sources[name] = value, "user"
        if problems:
            raise HTTPException(400, {"problems": problems})
        missing = [f["label"] for f in draft["fields"]
                   if _required(f) and f.get("type") != "input_file"
                   and not any(n in answers for n in (f.get("one_of") or [f["name"]]))]
        if missing:
            raise HTTPException(400, {"missing_required": list(dict.fromkeys(missing))})
        updates = {"answers": answers, "sources": sources, "status": "approved"}
        text = f"I approved the application for {label}."
    elif command.decision == "skip":
        updates = {"status": "skipped"}
        text = f"Skip the application for {label}."
    else:
        note = _flat(command.note, 2000)
        if not note:
            raise HTTPException(400, "Say what to change")
        text = (f"Change the application for {label} (application_id {draft['application_id']}): {note}\n"
                "Then call save_models_answers again.")

    if in_queue and command.decision != "changes":
        text += _next_step(thread_id, updates["status"], label)

    def after_save():
        if updates:
            store.put("drafts", draft_id, {**draft, **updates})
        if in_queue and command.decision != "changes":
            job_queue.finish(thread_id, updates["status"])

    return Decision(
        message=HumanMessage(
            id=f"review-{command.tool_call_id}",   # one decision per card (a repeat is a 409)
            content=text,
            additional_kwargs={"metadata": {"reviewDecision": {
                "toolCallId": command.tool_call_id,
                "decision": command.decision,
                "job": _flat(draft["title"], TITLE_CHARS),
                "edited": sum(1 for v in updates.get("sources", {}).values() if v == "user"),
                "note": _flat(command.note, 2000) if command.decision == "changes" else "",
            }}},
        ),
        after_save=after_save,
    )