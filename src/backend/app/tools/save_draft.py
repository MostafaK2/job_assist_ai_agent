"""Pre-fill every application field the user's profile can answer, in code (no LLM).

    prefill_from_profile(fields, profile) -> {
        "prefilled":  {field_name: value},              # filled from the profile
        "sources":    {field_name: "profile.<key>"},    # where each value came from (approval card)
        "for_model":  [field + {"task": ...}, ...],     # everything code couldn't fill
        "left_blank": [field, ...],                     # voluntary questions with no saved answer
    }

Each "for_model" field has a task:
    "draft"             custom question the model writes from the profile (cover letter, "why us?")
    "map_saved_answer"  the profile has an answer ("saved_answer") that doesn't exactly match the
                        form's options; the model picks the matching option (e.g. saved "No" ->
                        "I am not a protected veteran"), or asks the user if none fits
    "ask_user"          a fact only the user knows and the profile doesn't have (export controls,
                        phone, resume...). The model must ask the user, never guess.

`fields` is the "fields" list from load_form() / get_application_form.
`profile` is what get_user_profile returns. Adjust PROFILE_KEYS / SAVED_ANSWER_RULES to match it.
Not a tool yet: test it on its own first (see the bottom of this file).
"""
import re

RESUME_TOKEN = "PROFILE_RESUME"  # save_draft_answers swaps this for the real PDF

# ---------------------------------------------------------------- contact details
# For each piece of info, the profile keys to try, in order. Dotted keys reach into nested dicts.
PROFILE_KEYS = {
    "first_name": ["identity.preferred_name", "identity.first_name", "first_name"],
    "last_name": ["identity.last_name", "last_name"],
    "full_name": ["identity.full_name", "full_name", "name"],  # split into first/last if needed
    "email": ["identity.email", "email"],
    "phone": ["identity.phone", "phone"],
    "linkedin": ["links.linkedin_url", "linkedin_url"],
    "github": ["links.github_url", "github_url"],
    "website": ["links.website_portfolio_url", "website"],
    "location": [],                                  # computed: "Philadelphia, PA"
    # The profile doesn't store the resume yet. Point this at wherever onboarding saves it.
    "resume_path": ["resume_path", "resume.path"],
    "resume_text": ["resume_text", "resume.text"],
}

# Greenhouse's standard field names -> which info fills them.
STANDARD_FIELDS = {
    "first_name": "first_name", "last_name": "last_name", "email": "email", "phone": "phone",
    "resume": "resume_path", "resume_text": "resume_text",
}

# Custom text questions recognised by their label (Greenhouse names these question_123...).
LABEL_PATTERNS = [
    (re.compile(r"\blinked\s?in\b", re.I), "linkedin"),
    (re.compile(r"\bgit\s?hub\b", re.I), "github"),
    (re.compile(r"^(personal\s+)?(website|portfolio)( url)?$", re.I), "website"),
    (re.compile(r"^(current\s+)?(location|city)\b", re.I), "location"),
]

# ---------------------------------------------------------------- saved answers
# Questions answered from the user's saved onboarding answers: (label pattern, profile key).
# Keys with "|" mean "Yes if ANY of these is true" (sponsorship now OR in the future).
SAVED_ANSWER_RULES = [
    # "U.S. WORK AUTHORIZATION", "Are you legally authorized to work in...": the country is
    # picked from the question text (see _work_auth_key), US if none is named.
    (r"work authori[sz]ation|authori[sz]ed to work|(eligible|legally able|right) to work", "WORK_AUTH"),
    (r"sponsor", "work_authorization.requires_sponsorship_now|requires_sponsorship_future"),
    # "Have you ever been employed by X or any company X acquired?", "previously worked for..."
    (r"(ever|previously|formerly)\b.{0,20}\b(employed|worked) (by|for|at)|prior employment|former employee",
     "standard_answers.previously_employed_here"),
    (r"(hold|have)\b.*clearance", "security_clearance.has_clearance"),
    (r"^legal first name", "identity.first_name"),
    (r"^legal last name", "identity.last_name"),
    (r"how did you hear", "standard_answers.how_did_you_hear"),
    (r"notice period|when can you start|earliest start", "standard_answers.notice_period"),
    (r"willing to travel", "standard_answers.willing_to_travel"),
    (r"willing to relocate|open to relocat", "preferences.willing_to_relocate"),
    (r"\bgender\b", "voluntary_self_identification.gender"),
    (r"\brace\b|ethnicity", "voluntary_self_identification.ethnicity"),
    (r"veteran", "voluntary_self_identification.veteran_status"),
    (r"disability", "voluntary_self_identification.disability"),
]
SAVED_ANSWER_RULES = [(re.compile(p, re.I), key) for p, key in SAVED_ANSWER_RULES]


# ---------------------------------------------------------------- helpers
def _get(profile: dict, dotted: str):
    value = profile
    for part in dotted.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def profile_value(profile: dict, info: str) -> tuple[str | None, str | None]:
    """First non-empty profile value for a piece of info -> (value, "profile.<key>")."""
    profile = profile or {}
    if info == "location":
        city, state = _get(profile, "address.city"), _get(profile, "address.state")
        if city:
            return (f"{city}, {state}" if state else city), "profile.address.city/state"
    for key in PROFILE_KEYS.get(info, []):
        value = _get(profile, key)
        if isinstance(value, str) and value.strip():
            return value.strip(), f"profile.{key}"
    if info in ("first_name", "last_name"):  # "Ada Lovelace" -> "Ada" / "Lovelace"
        full, src = profile_value(profile, "full_name")
        if full and " " in full:
            part = full.split(" ", 1)[0] if info == "first_name" else full.rsplit(" ", 1)[1]
            return part.strip(), f"{src} (split)"
    return None, None


def _info_for(field: dict) -> str | None:
    """Which contact info fills this field, or None."""
    if field.get("name") in STANDARD_FIELDS:
        return STANDARD_FIELDS[field["name"]]
    if field.get("type") not in ("input_text", "textarea", None):
        return None
    label = (field.get("label") or "").strip()
    return next((info for pattern, info in LABEL_PATTERNS if pattern.search(label)), None)


def _question_text(field: dict) -> str:
    """Label + help text: real forms often put the actual question in the help text."""
    return f"{field.get('label') or ''} {field.get('help') or ''}".strip()


def _work_auth_key(text: str) -> str:
    t = text.lower()
    if "canada" in t:
        return "work_authorization.authorized_to_work_in_canada"
    if "united kingdom" in t or re.search(r"\buk\b", t):
        return "work_authorization.authorized_to_work_in_united_kingdom"
    return "work_authorization.authorized_to_work_in_us"


def _saved_answer(field: dict, profile: dict) -> tuple[object, str | None]:
    """(saved value, "profile.<key>") if a saved-answer rule matches this field's question.
    The label is checked first; the help text only if the label matches no rule (labels are
    specific, help text may mention several topics)."""
    for text in (field.get("label") or "", field.get("help") or ""):
        for pattern, key in SAVED_ANSWER_RULES:
            if not pattern.search(text):
                continue
            if key == "WORK_AUTH":
                key = _work_auth_key(_question_text(field))
            if "|" in key:
                base, rest = key.split(".", 1)
                values = [_get(profile or {}, f"{base}.{k}") for k in rest.split("|")]
                value = None if all(v is None for v in values) else any(bool(v) for v in values)
            else:
                value = _get(profile or {}, key)
            return value, f"profile.{key}"
    return None, None


def _to_option(value, options: list[str] | None) -> str | None:
    """Map a saved value onto the form. Text fields take it as is; dropdowns need one clear match."""
    if value is None:
        return None
    if isinstance(value, bool):
        value = "Yes" if value else "No"
    value = str(value).strip()
    if not value:
        return None
    if not options:
        return value
    exact = [o for o in options if o.lower() == value.lower()]
    if exact:
        return exact[0]
    if value.lower() in ("yes", "no"):  # "Yes, I am authorized..." style options
        starts = [o for o in options if o.lower().startswith(value.lower())]
        if len(starts) == 1:
            return starts[0]
    return None


def _for_model(field: dict, task: str, **extra) -> dict:
    return {**field, "task": task, **extra}


# ---------------------------------------------------------------- main
def prefill_from_profile(fields: list[dict], profile: dict) -> dict:
    prefilled, sources, for_model, left_blank = {}, {}, [], []
    voluntary = lambda f: f.get("voluntary") or f.get("section") in ("eeoc", "demographic")

    for field in fields:
        name = field["name"]

        # 1) a saved answer (work authorization, sponsorship, legal name, self-ID, ...)
        saved, src = _saved_answer(field, profile)
        if src is not None:
            value = _to_option(saved, field.get("options"))
            if value is not None:
                prefilled[name], sources[name] = value, src
            elif saved is not None and voluntary(field):                      # NEW (step 1)
                # Self-ID answers are private (profile_for_agent hides them), so they're never
                # sent to the model. No exact option match -> leave this voluntary question blank.
                left_blank.append(field)
            elif saved is not None:          # saved, but not one of the options: model maps it
                for_model.append(_for_model(field, "map_saved_answer",
                                            saved_answer=saved, saved_from=src))
            elif voluntary(field):
                left_blank.append(field)     # voluntary + nothing saved: leave it blank
            elif field.get("answer_source") == "user_only":
                for_model.append(_for_model(field, "ask_user"))
            else:
                for_model.append(_for_model(field, "draft"))
            continue

        # 2) contact details / resume
        info = _info_for(field)
        if info is not None:
            value, src = profile_value(profile, info)
            if value is not None:
                prefilled[name] = RESUME_TOKEN if info == "resume_path" else value
                sources[name] = src
            else:
                for_model.append(_for_model(field, "ask_user"))  # personal fact: never guessed
            continue

        # 3) nothing in the profile for this field
        if voluntary(field):
            left_blank.append(field)
        elif field.get("type") == "input_file":
            continue                         # only the resume is uploaded; others use the text twin
        elif field.get("answer_source") == "user_only":
            for_model.append(_for_model(field, "ask_user"))      # e.g. export controls
        else:
            for_model.append(_for_model(field, "draft"))         # e.g. cover letter, "why us?"

    # one_of pairs (resume file OR resume text): keep only the first filled one, and don't send
    # the other side to the model. If neither is filled, send the pair once.
    for field in fields:
        for extra in [n for n in field.get("one_of") or [] if n in prefilled][1:]:
            prefilled.pop(extra)
            sources.pop(extra)
    seen = set()
    kept = []
    for f in for_model:
        group = f.get("one_of") or []
        if any(n in prefilled for n in group if n != f["name"]):
            continue
        if group and f["label"] in seen:
            continue
        seen.add(f["label"])
        kept.append(f)

    return {"prefilled": prefilled, "sources": sources, "for_model": kept, "left_blank": left_blank}


# # ---------------------------------------------------------------- manual test
# # Run from src/backend:   python -m app.tools.save_draft [board_token job_id]
# # Without arguments it uses the first fake job in your jobs list (-> the real stand-in job).
# if __name__ == "__main__":
#     import json
#     import sys
#     from pathlib import Path

#     from .job_details import load_form
#     from .search_jobs import load_jobs

#     if len(sys.argv) >= 3:
#         board_token, job_id = sys.argv[1], int(sys.argv[2])
#     else:
#         job = next(j for j in load_jobs() if "example.com" in (j.get("url") or ""))
#         board_token, job_id = job["board_token"], job["id"]

#     profiles_path = Path(__file__).resolve().parents[2] / "data" / "profile.json"
#     profile = json.loads(profiles_path.read_text(encoding="utf-8"))["profiles"][0]

#     form = load_form(board_token, job_id)    # applies the stand-in itself
#     print(f"Form: {form['title']} ({form['board_token']}/{form['job_id']}), {len(form['fields'])} fields\n")

#     fields = form["fields"]

#     pre = prefill_from_profile(fields, profile)

#     print("PREFILLED")
#     for n, v in pre["prefilled"].items():
#         print(f"  {n:<16} = {str(v)[:45]!r:<48} <- {pre['sources'][n]}")
#     print("\nFOR THE MODEL")
#     for f in pre["for_model"]:
#         hint = f" (saved: {f['saved_answer']!r})" if f["task"] == "map_saved_answer" else ""
#         print(f"  [{f['task']:<16}] {f['label'][:60]}{hint}")
#     print("\nLEFT BLANK (voluntary):", [f["label"] for f in pre["left_blank"]])

