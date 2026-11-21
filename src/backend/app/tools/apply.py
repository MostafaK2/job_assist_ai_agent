"""Tools for applying to one job, in this order:

    code_prepare_application(board_token, job_id)  code pre-fills the form from the profile;
                                                   returns only the REQUIRED questions left for the model
    save_models_answers(application_id, answers)    merges the model's answers with the prefilled
                                                   ones, checks everything, saves a draft
    fill_application(draft_id)                     (step 3) fills the real form, never submits;
                                                   runs only after the user approves (Gate 2)

Everything that matters lives on the server (store.py: SQLite in data/applications.db); the
model only carries ids. Private details (email, phone, address, self-ID answers) are filled by
code and never shown to the model.
"""
import logging
import re
import uuid
from pathlib import Path
from typing import Annotated

import httpx
from langchain.tools import tool
from pydantic import BaseModel, Field

from app.config import PROFILE_PATH
from app.tools.job_details import BoardToken, JobId, _error, load_form
from app.tools import store
from app.tools.profile import load_full_profile
from app.tools.save_draft import PRIVATE, RESUME_TOKEN, prefill_from_profile

log = logging.getLogger("agent.tools")

BACKEND_DIR = Path(PROFILE_PATH).resolve().parents[1]  # resume paths are relative to src/backend
MAX_TEXT = {"input_text": 500, "textarea": 10_000}
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)
# Filled by code, never shown to the model (approval-card rows are masked too).
PRIVATE_SOURCES = (PRIVATE, "profile.identity.email", "profile.identity.phone", "profile.address")


class Answer(BaseModel):
    name: Annotated[str, Field(max_length=100, description='The question\'s "name"')]
    value: Annotated[str, Field(max_length=10_000, description="The answer (dropdowns: one of the options)")]


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _is_private(field: dict, source: str | None) -> bool:
    voluntary = field.get("voluntary") or field.get("section") in ("eeoc", "demographic")
    return bool(voluntary or (source and source.startswith(PRIVATE_SOURCES)))


def _required(field: dict) -> bool:
    """Required and something a person fills in (hidden lat/long are set by the location picker)."""
    return bool(field.get("required")) and field.get("type") != "input_hidden"


def resume_file(profile: dict) -> Path | None:
    """The user's resume PDF on the server, or None if it's missing, outside src/backend, or not a PDF."""
    raw = profile.get("resume_path") or (profile.get("resume") or {}).get("path")
    if not raw:
        return None
    path = (BACKEND_DIR / raw).resolve()
    try:
        ok = (path.is_relative_to(BACKEND_DIR) and path.is_file()
              and path.stat().st_size < 10_000_000 and path.read_bytes()[:5] == b"%PDF-")
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
    if options := field.get("options"):
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
def code_prepare_application(board_token: BoardToken, job_id: JobId) -> dict:
    """Start an application for ONE job the user chose. Code fills everything the profile can
    answer and returns only the REQUIRED questions left for you, each with a task:

    - "pick_option": pick the best option for the user from their profile and the job.
    - "map_saved_answer": the user saved "saved_answer"; pick the option that means the same.
    - "draft": write the answer from the profile and the job (e.g. a required cover letter, or a
      plain-text resume if the resume file is missing). Don't invent facts the profile lacks.

    Dropdown answers must be copied exactly from "options". Self-ID questions (gender, race,
    veteran, disability) are handled by code and never shown to you.
    Answer every question yourself; never stop to ask the user. They review everything at the
    end. Then call save_models_answers.
    """
    try:
        form = load_form(board_token, job_id)
    except (httpx.HTTPError, ValueError) as err:
        return _error(board_token, job_id, err)
    try:
        profile = load_full_profile()
    except (OSError, LookupError, ValueError) as err:
        log.warning("prepare_application: profile failed: %r", err)
        return {"error": "The user's profile couldn't be loaded. Tell the user and don't guess."}

    resume = resume_file(profile)
    if resume is None:  # no usable PDF: prefill without it, so the model drafts the text version
        profile = {**profile, "resume_path": None, "resume": None}
    pre = prefill_from_profile(form["fields"], profile)

    store.purge()
    application_id = _new_id("app")
    store.put("applications", application_id, {
        "form": form,
        "prefilled": pre["prefilled"],
        "sources": pre["sources"],
        "for_model": {f["name"]: f for f in pre["for_model"]},
        "resume_file": str(resume) if resume else None,
    })
    labels = {f["name"]: f["label"] for f in form["fields"]}
    keep = ("name", "label", "task", "type", "required", "options", "help", "saved_answer")
    return {
        "application_id": application_id,
        "job": {"title": form["title"], "url": form["url"]},
        "filled_from_profile": sorted({labels[n] for n in pre["prefilled"]}),  # labels only, no values
        "questions": [{k: f[k] for k in keep if f.get(k) not in (None, "", [])} for f in pre["for_model"]],
        "resume_on_file": resume is not None,
    }


@tool
def save_models_answers(
    application_id: Annotated[str, Field(pattern=r"^app_[0-9a-f]{12}$")],
    answers: Annotated[list[Answer], Field(max_length=60)],
) -> dict:
    """Save your answers to the questions from code_prepare_application and check them.
    Answers for fields that were already filled from the profile are refused.

    - "problems": your mistakes (e.g. not an exact option). Fix them and call again (at most twice).
    - "left_for_user": required questions only the user can answer (missing contact details,
      file uploads, self-ID). Don't ask about them: they're shown on the approval card.
    Status is "ready" or "needs_review"; either way, move on to the user's approval, then
    fill_application(draft_id). Nothing is sent to the employer by this tool.
    """
    app = store.get("applications", application_id)
    if app is None:
        return {"error": "Unknown or expired application_id. Call code_prepare_application again."}

    values, sources, problems = dict(app["prefilled"]), dict(app["sources"]), []
    for a in answers:
        field = app["for_model"].get(a.name)
        if a.name in app["prefilled"]:
            problems.append({"name": a.name, "issue": "already filled from the profile; not changed"})
        elif field is None:
            problems.append({"name": a.name, "issue": "not one of your questions for this application"})
        else:
            value, problem = check_answer(field, a.value)
            if problem:
                problems.append({"name": a.name, "label": field["label"], "issue": problem})
            else:
                values[a.name], sources[a.name] = value, "model"

    form = app["form"]
    unanswered = [f for f in form["fields"]
                  if _required(f) and not any(n in values for n in (f.get("one_of") or [f["name"]]))]
    problems += [{"name": f["name"], "label": f["label"], "issue": "not answered yet"}
                 for f in unanswered if f["name"] in app["for_model"]
                 and not any(p["name"] == f["name"] for p in problems)]
    missing = list(dict.fromkeys(f["label"] for f in unanswered if f["name"] not in app["for_model"]))
    status = "ready" if not unanswered else "needs_review"   # user fills the rest on the approval card

    draft_id = _new_id("draft")
    store.put("drafts", draft_id, {
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
    })
    return {"draft_id": draft_id, "status": status, "answered": len(values),
            "problems": problems, "left_for_user": missing}


def draft_summary(draft_id: str, include_private: bool = False) -> list[dict]:
    """The draft as label/value/source rows, for the approval message shown to the USER.
    Private values are masked unless include_private (never pass that to the model)."""
    draft = store.get("drafts", draft_id)
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
        elif _is_private(f, source) and not include_private:
            value = "(on file)"
        rows.append({"label": f["label"], "value": value, "source": source})
    return rows


APPLY_TOOLS = [code_prepare_application, save_models_answers]