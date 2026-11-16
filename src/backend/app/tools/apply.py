"""Tools for applying to one job, in this order:

    prepare_application(board_token, job_id)   code pre-fills the form from the profile;
                                               returns only the questions the model must handle
    save_draft_answers(application_id, answers) merges the model's answers with the prefilled
                                               ones, checks everything, saves a draft
    fill_application(draft_id)                 (step 3) fills the real form, never submits;
                                               runs only after the user approves (Gate 2)

Everything that matters lives on the server (APPLICATIONS, DRAFTS): the model only carries ids.
Private details (email, phone, self-ID answers) are filled by code and never shown to the model,
matching profile_for_agent in profile.py. In-memory storage is fine for the demo; a server
restart clears it.
"""
import re
import time
import uuid
from pathlib import Path
from typing import Annotated

import httpx
from langchain.tools import tool
from pydantic import BaseModel, Field

from app.config import PROFILE_PATH
from app.tools.job_details import BoardToken, JobId, _error, load_form
from app.tools.profile import load_full_profile
from app.tools.save_draft import RESUME_TOKEN, prefill_from_profile

BACKEND_DIR = Path(PROFILE_PATH).resolve().parents[1]  # resume paths are relative to src/backend
EXPIRES_SECONDS = 2 * 60 * 60
MAX_TEXT = {"input_text": 500, "textarea": 10_000}
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)
# Values from these profile parts are filled by code but never shown to the model.
PRIVATE_SOURCES = ("profile.identity.email", "profile.identity.phone",
                   "profile.address", "profile.voluntary_self_identification")

APPLICATIONS: dict[str, dict] = {}  # application_id -> prepared form + prefilled answers
DRAFTS: dict[str, dict] = {}        # draft_id -> checked answers, ready for approval


class Answer(BaseModel):
    name: Annotated[str, Field(max_length=100, description='The question\'s "name"')]
    value: Annotated[str, Field(max_length=10_000, description="The answer (dropdowns: one of the options)")]


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _get_live(store: dict, key: str) -> dict | None:
    item = store.get(key)
    if item and time.time() - item["created"] < EXPIRES_SECONDS:
        return item
    return None


def _is_private(source: str | None) -> bool:
    return bool(source) and source.startswith(PRIVATE_SOURCES)


def resume_file(profile: dict) -> Path | None:
    """The user's resume PDF on the server, or None if it's missing or not a real PDF."""
    raw = profile.get("resume_path") or (profile.get("resume") or {}).get("path")
    if not raw:
        return None
    path = (BACKEND_DIR / raw).resolve()
    try:
        ok = path.is_file() and path.stat().st_size < 10_000_000 and path.read_bytes()[:5] == b"%PDF-"
    except OSError:
        ok = False
    return path if ok else None


def check_answer(field: dict, value: str) -> tuple[str | None, str | None]:
    """(clean value, problem): exactly one is set."""
    value = (value or "").strip()
    if not value:
        return None, "empty answer"
    if field.get("type") == "input_file":
        return None, "files can't be uploaded here; answer the text version of this question"
    options = field.get("options")
    if options:
        match = next((o for o in options if o.lower() == value.lower()), None)
        return (match, None) if match else (None, f"must be exactly one of: {options}")
    limit = MAX_TEXT.get(field.get("type") or "", 500)
    if len(value) > limit:
        return None, f"too long ({len(value)} characters, max {limit})"
    label = (field.get("label") or "").lower()
    if "email" in label and not EMAIL.match(value):
        return None, "not a valid email address"
    if re.search(r"linkedin|website|portfolio|github|url", label) and not value.lower().startswith("https://"):
        return None, "links must start with https://"
    return value, None


# ---------------------------------------------------------------- tools
@tool
def prepare_application(board_token: BoardToken, job_id: JobId) -> dict:
    """Start an application for ONE job the user chose. Fills everything the profile can
    answer (in code) and returns only the questions left for you, each with a task:

    - "draft": write the answer from the profile and the job (e.g. a short cover letter).
      Don't invent facts the profile doesn't support.
    - "map_saved_answer": the user saved "saved_answer"; pick the option that means the same.
      If none fits, ask the user.
    - "ask_user": only the user knows this. Ask them in ONE chat message together with any
      other ask_user questions. Never guess, and don't save an answer until they reply.

    Dropdown answers must be copied exactly from "options". Then call save_draft_answers.
    """
    try:
        form = load_form(board_token, job_id)
    except (httpx.HTTPError, ValueError) as err:
        return _error(board_token, job_id, err)
    try:
        profile = load_full_profile()
    except (OSError, LookupError, ValueError) as err:
        print(f"prepare_application: profile failed: {err!r}")
        return {"error": "The user's profile couldn't be loaded. Tell the user and don't guess."}

    pre = prefill_from_profile(form["fields"], profile)
    resume = resume_file(profile)
    if RESUME_TOKEN in pre["prefilled"].values() and resume is None:  # path saved but file bad
        name = next(n for n, v in pre["prefilled"].items() if v == RESUME_TOKEN)
        pre["prefilled"].pop(name), pre["sources"].pop(name)
        field = next(f for f in form["fields"] if f["name"] == name)
        pre["for_model"].insert(0, {**field, "task": "ask_user"})

    application_id = _new_id("app")
    APPLICATIONS[application_id] = {
        "created": time.time(),
        "form": form,
        "prefilled": pre["prefilled"],
        "sources": pre["sources"],
        "for_model": {f["name"]: f for f in pre["for_model"]},
        "resume_file": str(resume) if resume else None,
    }
    labels = {f["name"]: f["label"] for f in form["fields"]}
    keep = ("name", "label", "task", "type", "required", "options", "help", "saved_answer")
    return {
        "application_id": application_id,
        "job": {"title": form["title"], "url": form["url"]},
        "filled_from_profile": sorted({labels[n] for n in pre["prefilled"]}),  # labels only
        "questions": [{k: f[k] for k in keep if f.get(k) not in (None, "", [])}
                      for f in pre["for_model"]],
        "left_blank": [f["label"] for f in pre["left_blank"]],
    }


@tool
def save_draft_answers(
    application_id: Annotated[str, Field(pattern=r"^app_[0-9a-f]{12}$")],
    answers: Annotated[list[Answer], Field(max_length=60)],
) -> dict:
    """Save your answers to the questions from prepare_application and check them.
    Answers for fields that were already filled from the profile are refused.
    Returns a draft_id. If there are problems, fix them and call again (at most twice).
    When status is "ready", call fill_application(draft_id); the user approves first.
    Nothing is sent to the employer by this tool.
    """
    app = _get_live(APPLICATIONS, application_id)
    if app is None:
        return {"error": "Unknown or expired application_id. Call prepare_application again."}

    form, mine = app["form"], app["for_model"]
    values = dict(app["prefilled"])
    sources = dict(app["sources"])
    problems = []
    for a in answers:
        if a.name in app["prefilled"]:
            problems.append({"name": a.name, "issue": "already filled from the profile; not changed"})
            continue
        field = mine.get(a.name)
        if field is None:
            problems.append({"name": a.name, "issue": "not one of your questions for this application"})
            continue
        value, problem = check_answer(field, a.value)
        if problem:
            problems.append({"name": a.name, "label": field["label"], "issue": problem})
            continue
        values[a.name] = value
        sources[a.name] = "user (chat)" if field["task"] == "ask_user" else "model"

    def filled(f):
        return any(n in values for n in (f.get("one_of") or [f["name"]]))

    missing = []
    for f in form["fields"]:
        if f["required"] and not f.get("voluntary") and not filled(f) and f["label"] not in missing:
            missing.append(f["label"])

    draft_id = _new_id("draft")
    status = "ready" if not missing else "incomplete"
    DRAFTS[draft_id] = {
        "created": time.time(),
        "application_id": application_id,
        "board_token": form["board_token"],
        "job_id": form["job_id"],
        "title": form["title"],
        "url": form["url"],
        "fields": form["fields"],
        "answers": values,
        "sources": sources,
        "resume_file": app["resume_file"],
        "status": status,            # "approved" is set only by the approval step
    }
    return {
        "draft_id": draft_id,
        "status": status,
        "answered": len(values),
        "problems": problems,
        "missing_required": missing,
    }


def draft_summary(draft_id: str, include_private: bool = False) -> list[dict]:
    """The draft as label/value/source rows, for the approval message shown to the USER.
    Private values are masked unless include_private (never pass that to the model)."""
    draft = _get_live(DRAFTS, draft_id)
    if draft is None:
        return []
    rows, seen = [], set()
    for f in draft["fields"]:
        name = f["name"]
        if name not in draft["answers"] or name in seen:
            continue
        seen.add(name)
        value, source = draft["answers"][name], draft["sources"].get(name, "")
        if value == RESUME_TOKEN:
            value = Path(draft["resume_file"] or "").name or "(resume on file)"
        elif _is_private(source) and not include_private:
            value = "(on file)"
        rows.append({"label": f["label"], "value": value, "source": source})
    return rows


APPLY_TOOLS = [prepare_application, save_draft_answers]