"""Filling an APPROVED application in the user's own Chrome (the Job Assist extension).

    fill_application(draft_id)   tool: starts a fill session and shows a fill card in the chat
    The card (components/chat/FillCard.jsx) asks POST /api/fills/{fill_id}/plan for the fill plan
    (once: a reload never reopens the form), then hands it to the extension, which opens the
    Greenhouse page in a new tab and types the answers in. The user checks the tab and presses
    Submit themselves; nothing here ever submits.

Fill sessions live in the store (kind "fills"), keyed by fill_id, tied to the chat's thread:
    {"thread_id", "draft_id", "status": created | started | submitted | skipped, ...}
The plan holds private values (email, phone, self-ID): it goes from this server to the user's own
browser only, never to the model. Each private field is flagged so the extension never sends it
to the agent when it asks for help.
"""
import json
import time
import uuid
from pathlib import Path
from typing import Annotated

from langchain.tools import ToolRuntime, tool
from pydantic import Field

from app.tools import store
from app.tools.apply import _is_private, _required
from app.tools.save_draft import RESUME_TOKEN

KIND = "fills"
FINAL = ("submitted", "skipped")
GREENHOUSE_FORM = "https://job-boards.greenhouse.io/{board_token}/jobs/{job_id}"


# ---------------------------------------------------------------- fill sessions
def get_fill(fill_id: str) -> dict | None:
    return store.get(KIND, fill_id)


def update_fill(fill_id: str, **changes) -> dict | None:
    fill = get_fill(fill_id)
    if fill is not None:
        fill = {**fill, **changes}
        store.put(KIND, fill_id, fill)
    return fill


def form_url(draft: dict) -> str:
    """Always the canonical Greenhouse page: a job's own link is often a company page with the
    form embedded in a frame."""
    return GREENHOUSE_FORM.format(board_token=draft["board_token"], job_id=draft["job_id"])


# ---------------------------------------------------------------- the fill plan
def _year_month(value: str | None) -> dict | None:
    """'2023-09-01' -> {"year": "2023", "month": "09"}"""
    if not value or len(value) < 7:
        return None
    return {"year": value[:4], "month": value[5:7]}


def profile_facts(profile: dict) -> dict:
    """Profile facts for fields that exist only on the live page (Greenhouse's Education and
    Employment sections, location autocomplete...), which the form API doesn't describe."""
    identity, address = profile.get("identity") or {}, profile.get("address") or {}
    links = profile.get("links") or {}
    jobs = sorted(profile.get("work_history") or [],      # current job first, then most recent start
                  key=lambda j: (j.get("end_date") is None, j.get("start_date") or ""), reverse=True)
    return {
        "name": {"first": identity.get("preferred_first_name") or identity.get("first_name"),
                 "last": identity.get("preferred_last_name") or identity.get("last_name"),
                 "legal_first": identity.get("legal_first_name"), "legal_last": identity.get("legal_last_name")},
        "location": {"city": address.get("city"), "state": address.get("state"),
                     "country": address.get("country"), "zip": address.get("zip_code")},
        "links": {"linkedin": links.get("linkedin_url"), "github": links.get("github_url"),
                  "website": links.get("website_portfolio_url")},
        "education": [{"school": e.get("school"), "degree": e.get("degree"),
                       "discipline": e.get("field_of_study"), "gpa": e.get("gpa"),
                       "start": _year_month(e.get("start_date")), "end": _year_month(e.get("end_date"))}
                      for e in profile.get("education") or []],
        "employment": [{"company": j.get("company"), "title": j.get("title"), "current": j.get("end_date") is None,
                        "start": _year_month(j.get("start_date")), "end": _year_month(j.get("end_date"))}
                       for j in jobs],
    }


def build_plan(fill_id: str, draft: dict, profile: dict) -> dict:
    """Everything the extension needs to fill the form: the approved answers (by Greenhouse field
    name), the resume, and profile facts for page-only fields."""
    fields, unanswered, resume = [], [], None
    for f in draft["fields"]:
        if f.get("type") == "input_hidden":
            continue
        name, value = f["name"], draft["answers"].get(f["name"])
        source = draft["sources"].get(name, "")
        if value == RESUME_TOKEN:
            if draft.get("resume_file"):
                resume = {"name": name, "label": f["label"], "filename": Path(draft["resume_file"]).name}
            continue
        if value is None:
            group = f.get("one_of") or [name]
            if _required(f) and not any(n in draft["answers"] for n in group):
                unanswered.append({"name": name, "label": f["label"], "type": f.get("type")})
            continue
        fields.append({
            "name": name, "label": f["label"], "type": f.get("type"), "required": _required(f),
            "options": f.get("options") or [], "value": value,
            "source": "model" if source == "model" else "user" if source == "user" else "profile",
            "private": _is_private(f, source),   # never sent to the agent
        })
    return {
        "fill_id": fill_id,
        "url": form_url(draft),
        "job": {"title": draft["title"], "id": f'{draft["board_token"]}/{draft["job_id"]}'},
        "fields": fields,
        "resume": resume,
        "unanswered": list({u["label"]: u for u in unanswered}.values()),
        "profile_facts": profile_facts(profile),
    }


# ---------------------------------------------------------------- tool
@tool(response_format="content_and_artifact")
def fill_application(
    draft_id: Annotated[str, Field(pattern=r"^draft_[0-9a-f]{12}$", description="The approved draft's id")],
    runtime: ToolRuntime,
) -> tuple[str, dict | None]:
    """Fill an APPROVED application on the real job page, in the user's own Chrome (the Job
    Assist extension opens a new tab and types the answers in). Call it right after the user
    approves the review card, or when they ask you to fill an approved application.
    It never submits: the user checks the tab and presses Submit themselves.
    After calling it, STOP with one short line. You'll get a message if the form needs
    answers, and when the user submits or skips it.
    """
    draft = store.get("drafts", draft_id)
    if draft is None:
        return "Unknown or expired draft_id. Prepare the application again.", None
    if draft["status"] in FINAL:
        return f"This application was already {draft['status']}. Don't fill it again.", None
    if draft["status"] != "approved":
        return ("The user hasn't approved this draft. They approve it on the review card; "
                "don't fill it before that."), None

    fill_id = f"fill_{uuid.uuid4().hex[:12]}"
    store.put(KIND, fill_id, {"thread_id": runtime.config["configurable"]["thread_id"],
                              "draft_id": draft_id, "status": "created", "created_at": time.time()})
    store.put("drafts", draft_id, {**draft, "fill_id": fill_id})
    content = {"fill_id": fill_id, "status": "opening",
               "note": "The form opens in a new Chrome tab and fills itself. Stop now with one short line."}
    artifact = {"fill_id": fill_id, "url": form_url(draft),
                "job": {"title": draft["title"], "id": f'{draft["board_token"]}/{draft["job_id"]}'}}
    return json.dumps(content), artifact


FILL_TOOLS = [fill_application]