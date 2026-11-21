"""Pre-fill a Greenhouse application from the user's profile, in code (no LLM).

    prefill_from_profile(fields, profile) -> {
        "prefilled":  {field_name: value},              # filled by code
        "sources":    {field_name: "profile.<key>"},    # where each value came from (approval card)
        "for_model":  [field + {"task": ...}, ...],     # REQUIRED questions code couldn't fill
        "left_blank": [field + {"reason": ...}, ...],   # everything else left empty
    }

Policy
    Required  -> code fills it if it can; otherwise the model gets it ("for_model").
    Optional  -> code fills it only from OPTIONAL_FILL sources (name, links, address, self-ID...);
                 otherwise left blank. Optional questions never go to the model.
    Self-ID   -> (gender, race, veteran, disability...) never go to the model. Required and no
                 matching saved answer -> the "I don't wish to answer" option.

"for_model" tasks:
    "pick_option"       dropdown/radio: the model picks the best option from the profile
    "draft"             free text the model writes (a required cover letter, "why us?")
    "map_saved_answer"  a saved answer ("saved_answer") that matches no option exactly:
                        the model picks the option that means the same thing

"one_of" groups (resume file OR resume text) need one answer: the first filled one is kept.
"""
import re
from datetime import date

RESUME_TOKEN = "PROFILE_RESUME"  # save_draft_answers swaps this for the real PDF

# Optional questions are filled only from these sources (name, links, address, self-ID, resume).
OPTIONAL_FILL = ("profile.identity", "profile.links", "profile.address",
                 "profile.voluntary_self_identification", "profile.resume")
PRIVATE = "profile.voluntary_self_identification"   # never sent to the model

# ---------------------------------------------------------------- contact details
# Profile keys to try, in order. Dotted keys reach into nested dicts.
PROFILE_KEYS = {
    "first_name": ["identity.preferred_first_name", "identity.first_name", "identity.legal_first_name"],
    "last_name": ["identity.preferred_last_name", "identity.last_name", "identity.legal_last_name"],
    "preferred_name": ["identity.preferred_first_name", "identity.first_name"],
    "full_name": ["identity.full_name"],                 # split into first/last if needed
    "email": ["identity.email"],
    "phone": ["identity.phone"],
    "linkedin": ["links.linkedin_url"],
    "github": ["links.github_url"],
    "website": ["links.website_portfolio_url"],
    "zip": ["address.zip_code"],
    "resume_path": ["resume_path", "resume.path"],
    "resume_text": ["resume_text", "resume.text"],
}  # "location" is computed from address.city/state

# Greenhouse's standard field names -> which info fills them.
STANDARD_FIELDS = {
    "first_name": "first_name", "last_name": "last_name", "preferred_name": "preferred_name",
    "email": "email", "phone": "phone", "resume": "resume_path", "resume_text": "resume_text",
}

# Custom text questions recognised by their label (Greenhouse names these question_123...).
LABEL_PATTERNS = [(re.compile(p, re.I), info) for p, info in [
    (r"\blinked\s?in\b", "linkedin"),
    (r"\bgit\s?hub\b", "github"),
    (r"^(personal\s+)?(website|portfolio)( url)?$", "website"),
    (r"^(current\s+)?(location|city)\b", "location"),
    (r"preferred (first )?name|name you'?d prefer|nickname", "preferred_name"),
    (r"\bzip\b|postal code", "zip"),
]]

# ---------------------------------------------------------------- saved answers
# (question pattern, profile key or =COMPUTED). Label first, then help text; first match wins,
# so specific rules go first. "a|b" after the dot means "Yes if ANY of these is true".
SAVED_ANSWER_RULES = [(re.compile(p, re.I), key) for p, key in [
    (r"employee (id|number|#)|badge number", "standard_answers.employee_id"),
    (r"\bu\.?s\.? (citizen|person)|citizenship|export control|source of your right to work", "citizenship.status"),
    (r"own expense|relocation assistance", "standard_answers.willing_to_relocate_at_own_expense"),
    (r"sponsor", "work_authorization.requires_sponsorship_now|requires_sponsorship_future"),
    (r"work authori[sz]ation|authori[sz]ed to work|(eligible|legally able|right) to work", "=WORK_AUTH"),
    (r"(ever|previously|formerly|in the past)\b.{0,60}\b(employed|worked)\b|\b(employed|worked)\b.{0,60}"
     r"\b(previously|formerly|in the past)|have you (ever )?(worked|been employed) (at|for|by)|"
     r"prior employment|former employee", "standard_answers.previously_employed_here"),
    (r"(at least|over|older than)\s+(the age of\s+)?18|18 (years|or older)", "=AGE_18"),
    (r"(hold|have)\b.*clearance", "security_clearance.has_clearance"),
    (r"^legal first name", "identity.legal_first_name"),
    (r"^legal last name", "identity.legal_last_name"),
    (r"legal (full )?name", "=LEGAL_NAME"),
    (r"e-?signature|type your full name|sign(ature)? (here|below)", "=SIGNATURE"),
    (r"how did you (initially )?(hear|learn|find)|where did you (hear|find|learn)|referral source",
     "standard_answers.how_did_you_hear"),
    (r"notice period|when can you start|earliest start|available to start", "standard_answers.notice_period"),
    (r"willing to travel|travel requirement", "standard_answers.willing_to_travel"),
    (r"relocat", "standard_answers.willing_to_relocate"),
    (r"essential functions", "standard_answers.can_you_perform_essential_functions"),
    (r"convicted|criminal", "standard_answers.have_you_been_convicted"),
    (r"contact your (current )?employer", "standard_answers.may_contact_current_employer"),
    (r"(current|previous|most recent) (or (previous|most recent) )?employer", "=CURRENT_EMPLOYER"),
    (r"(current|previous|most recent) (or (previous|most recent) )?(job )?title", "=CURRENT_TITLE"),
    (r"country.{0,40}(reside|live|located|residence)|where do you (currently )?live", "address.country"),
    (r"relative.{0,60}government official", "standard_answers.relative_of_government_official"),
    (r"government official", "standard_answers.government_official"),
    (r"conflict of interest", "standard_answers.conflict_of_interest"),
    (r"employment agreement|non-?compete|post-employment restriction", "standard_answers.has_employment_restrictions"),
    (r"\bsms\b|whatsapp|text messages", "standard_answers.sms_opt_in"),
    (r"pronoun", "identity.pronouns"),
    (r"transgender", "voluntary_self_identification.transgender"),
    (r"sexual orientation", "voluntary_self_identification.sexual_orientation"),
    (r"lgbtq", "voluntary_self_identification.lgbtq"),
    (r"\bgender\b", "voluntary_self_identification.gender"),
    (r"\brace\b|ethnic", "voluntary_self_identification.ethnicity"),
    (r"veteran|armed forces", "voluntary_self_identification.veteran_status"),
    (r"disability", "voluntary_self_identification.disability"),
]]
NOT_APPLICABLE_IF_MISSING = {"standard_answers.employee_id"}   # missing = doesn't apply (not an employee)

# Work-authorization country, picked from the question text; US if none is named.
WORK_AUTH_COUNTRIES = [(r"canada", "canada"), (r"united kingdom|\buk\b", "united_kingdom")]

# ---------------------------------------------------------------- option matching
SYNONYMS = [{"male", "man"}, {"female", "woman"},
            {"unitedstates", "us", "usa", "unitedstatesofamerica"}]       # compared after _norm()
NEGATIVE = re.compile(r"\b(no|not|never|none|don't|do not|haven't|have not)\b", re.I)
DECLINE = re.compile(r"decline|wish to (answer|disclose|self)|want to answer|prefer not|"
                     r"not to (say|disclose|answer)", re.I)
NOT_APPLICABLE = re.compile(r"does not apply|not applicable|^n/?a\b", re.I)

# Acknowledgements / consents: code picks the agreeing option. Statements about AI use are
# left to the model + approval card (an AI-filled application shouldn't auto-promise "no AI").
ACK = re.compile(r"^(i (understand|acknowledge|certify|confirm|agree|affirm)|by (clicking|checking|submitting)|"
                 r"please (confirm|review|acknowledge))|acknowledg|privacy (notice|policy|act)", re.I)
AGREE = re.compile(r"^(yes|i (acknowledge|agree|accept|confirm|understand|have read)|acknowledge|confirm|agree|accept)", re.I)
AI_STATEMENT = re.compile(r"\bAI\b|artificial intelligence")
# Follow-ups that start with "If" ("If yes, please explain", "If you chose Other, specify"): "N/A".
CONDITIONAL = re.compile(r"^\s*if\b", re.I)


# ---------------------------------------------------------------- helpers
def _get(profile: dict, dotted: str):
    for part in dotted.split("."):
        if not isinstance(profile, dict):
            return None
        profile = profile.get(part)
    return profile


def _norm(text) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(text).lower())


def _stems(text: str) -> set[str]:
    return {w[:5] for w in re.findall(r"[a-z]{4,}", text.lower())}


def _computed(name: str, field: dict, profile: dict):
    legal = " ".join(filter(None, [_get(profile, "identity.legal_first_name") or _get(profile, "identity.first_name"),
                                   _get(profile, "identity.legal_last_name") or _get(profile, "identity.last_name")]))
    jobs = sorted(profile.get("work_history") or [],      # current job first, then most recent start
                  key=lambda j: (j.get("end_date") is None, j.get("start_date") or ""), reverse=True)
    if name == "WORK_AUTH":
        question = f"{field.get('label') or ''} {field.get('help') or ''}"
        country = next((c for p, c in WORK_AUTH_COUNTRIES if re.search(p, question, re.I)), "us")
        return _get(profile, f"work_authorization.authorized_to_work_in_{country}")
    if name == "AGE_18":
        dob = _get(profile, "identity.dob")
        if not dob:
            return None
        born, today = date.fromisoformat(dob), date.today()
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day)) >= 18
    if name == "LEGAL_NAME":
        return legal or None
    if name == "SIGNATURE":
        return f"{legal} {date.today():%m/%d/%Y}" if legal else None
    if name in ("CURRENT_EMPLOYER", "CURRENT_TITLE"):
        return jobs[0].get("company" if name == "CURRENT_EMPLOYER" else "title") if jobs else None
    raise KeyError(name)


def profile_value(profile: dict, info: str) -> tuple[str | None, str | None]:
    """First non-empty profile value for a piece of info -> (value, "profile.<key>")."""
    if info == "location":
        city, state = _get(profile, "address.city"), _get(profile, "address.state")
        return (f"{city}, {state}" if state else city, "profile.address.city/state") if city else (None, None)
    for key in PROFILE_KEYS.get(info, []):
        value = _get(profile, key)
        if isinstance(value, str) and value.strip():
            return value.strip(), f"profile.{key}"
    if info in ("first_name", "last_name"):  # "Ada Lovelace" -> "Ada" / "Lovelace"
        full, src = profile_value(profile, "full_name")
        if full and " " in full:
            return (full.split()[0] if info == "first_name" else full.split()[-1]), f"{src} (split)"
    return None, None


def _info_for(field: dict) -> str | None:
    """Which contact info fills this field, or None."""
    if field.get("name") in STANDARD_FIELDS:
        return STANDARD_FIELDS[field["name"]]
    if field.get("type") not in ("input_text", "textarea", None):
        return None
    label = (field.get("label") or "").strip()
    return next((info for pattern, info in LABEL_PATTERNS if pattern.search(label)), None)


def _saved_answer(field: dict, profile: dict) -> tuple[object, str | None]:
    """(saved value, "profile.<key>") for the first rule matching the label, else the help text."""
    for text in (field.get("label") or "", field.get("help") or ""):
        for pattern, key in SAVED_ANSWER_RULES:
            if not pattern.search(text):
                continue
            if key.startswith("="):
                return _computed(key[1:], field, profile), f"profile.computed.{key[1:].lower()}"
            if "|" in key:
                base, rest = key.split(".", 1)
                values = [_get(profile, f"{base}.{k}") for k in rest.split("|")]
                return (None if all(v is None for v in values) else any(values)), f"profile.{key}"
            return _get(profile, key), f"profile.{key}"
    return None, None


def _to_option(value, options: list[str] | None) -> str | None:
    """Map a saved value onto the form. Text fields take it as is; dropdowns need ONE clear match."""
    if isinstance(value, bool):
        value = "Yes" if value else "No"
    value = str(value).strip() if value is not None else ""
    if not value or not options:
        return value or None
    real = [o for o in options if not DECLINE.search(o)]
    keys = next((g for g in SYNONYMS if _norm(value) in g), {_norm(value)})
    yes_no, negative = value.lower() in ("yes", "no"), value.lower() in ("no", "none")
    tests = [
        lambda o: _norm(o) in keys,                                            # "he/him" = "He / Him", Male = Man
        lambda o: yes_no and re.match(rf"{value}\b", o, re.I),                 # "No, I am not a ..."
        lambda o: negative and NEGATIVE.search(o),                             # "I am not a protected veteran"
        lambda o: len(value) > 3 and re.search(rf"\b{re.escape(value)}\b", o, re.I),  # "Asian (Not Hispanic)"
    ]
    for test in tests:
        hits = [o for o in real if test(o)]
        if len(hits) == 1:
            return hits[0]
    if len(value) > 3 and not yes_no:                                          # "Company careers page" -> "Career Page"
        scores = {o: len(_stems(value) & _stems(o)) for o in real}
        best = max(scores.values(), default=0)
        if best and list(scores.values()).count(best) == 1:
            return max(scores, key=scores.get)
    return None


def _pick(options: list[str], pattern: re.Pattern) -> str | None:
    hits = [o for o in options if pattern.search(o)
            and (pattern is DECLINE or not DECLINE.search(o))
            and (pattern is not AGREE or not NEGATIVE.search(o))]
    return hits[0] if len(hits) == 1 else None


# ---------------------------------------------------------------- one field
def _decide(field: dict, profile: dict) -> tuple:
    """("fill", value, source) | ("model", task, extra) | ("blank", reason)."""
    label, opts = field.get("label") or "", field.get("options") or []
    text = f"{label} {field.get('help') or ''}"
    voluntary = field.get("voluntary") or field.get("section") in ("eeoc", "demographic")

    if field.get("type") == "input_hidden":
        return "blank", "hidden field (set by the location picker)"

    # 1) contact details / resume
    if (info := _info_for(field)) is not None:
        value, src = profile_value(profile, info)
        if value is not None:
            return "fill", RESUME_TOKEN if info == "resume_path" else value, src
        return ("model", "draft", {}) if info == "resume_text" else ("blank", f"missing in profile: {info}")
    if field.get("type") == "input_file":
        return "blank", "file upload (its text twin is used instead)"

    # 2) one possible answer, or an acknowledgement
    if len(opts) == 1:
        return "fill", opts[0], "auto.only_option"
    if opts and ACK.search(label) and not AI_STATEMENT.search(text) and (agree := _pick(opts, AGREE)):
        return "fill", agree, "auto.acknowledgement"

    # 3) a saved answer (work authorization, sponsorship, legal name, self-ID, ...)
    saved, src = _saved_answer(field, profile)
    private = voluntary or (src or "").startswith(PRIVATE)
    if src:
        if saved is None and src.removeprefix("profile.") in NOT_APPLICABLE_IF_MISSING:
            return "blank", "not applicable"
        if (value := _to_option(saved, opts)) is not None:
            return "fill", value, src

    # 4) follow-up questions, self-ID fallbacks
    if CONDITIONAL.search(label):
        if na := (_pick(opts, NOT_APPLICABLE) if opts else "N/A"):
            return "fill", na, "auto.not_applicable"
    if private:
        if decline := _pick(opts, DECLINE):
            return "fill", decline, "auto.declined_to_answer"
        return "blank", "self-ID with no matching saved answer"

    # 5) the model
    if src and saved is not None:
        return "model", "map_saved_answer", {"saved_answer": saved, "saved_from": src}
    return "model", "pick_option" if opts else "draft", {}


# ---------------------------------------------------------------- main
def prefill_from_profile(fields: list[dict], profile: dict) -> dict:
    profile = profile or {}
    prefilled, sources, for_model, left_blank = {}, {}, [], []

    for field in fields:
        kind, *rest = _decide(field, profile)
        required = bool(field.get("required"))
        if kind == "fill" and (required or rest[1].startswith(OPTIONAL_FILL)):
            prefilled[field["name"]], sources[field["name"]] = rest
        elif kind == "model" and required:
            for_model.append({**field, "task": rest[0], **rest[1]})
        else:
            reason = rest[0] if kind == "blank" else "optional"
            left_blank.append({**field, "reason": reason})

    # one_of groups: keep only the first filled member; send an unfilled group to the model once.
    for field in fields:
        for extra in [n for n in field.get("one_of") or [] if n in prefilled][1:]:
            prefilled.pop(extra)
            sources.pop(extra)
    seen, kept = set(), []
    for f in for_model:
        group = frozenset(f.get("one_of") or ())
        if group and (group & prefilled.keys() or group in seen):
            continue
        seen.add(group)
        kept.append(f)

    return {"prefilled": prefilled, "sources": sources, "for_model": kept, "left_blank": left_blank}


# # ---------------------------------------------------------------- manual test
# # Run from src/backend:   python -m app.tools.<this_module> [board_token job_id]
# if __name__ == "__main__":
#     import json
#     import sys
#     from pathlib import Path

#     from .job_details import load_form

    
#     profile_path = Path(__file__).resolve().parents[2] / "data" / "profile.json"
#     profile = json.loads(profile_path.read_text(encoding="utf-8"))["profiles"][0]


#     jobs = [
#         ("nuro", 7902399),
#         # ("recursionpharmaceuticals", 8334716),
#         # ("lyft", 8834157002),
#         # ("stripe", 8168813),
#         # ("oscar", 8301400),
#         # ("flexport", 8136589),
#         # ("coinbase", 8357772),
#         # ("gitlab", 8871406002),
#         # ("instacart", 7793391),
#         # ("hellofresh", 8345649),
#         # ("twilio", 8249285),
#         # ("doordashusa", 8279250),
#         # ("peloton", 7290826),
#         # ("cloudflare", 8328562),
#     ]   

#     for board_token, job_id in jobs:
#         print("="*20 + f" {board_token}/{job_id} ============\n")
#         try:
#             form = load_form(board_token, job_id)
#         except Exception as err:
#             print(f"Couldn't load form: {err!r}")
#             continue
    
#         pre = prefill_from_profile(form["fields"], profile)
#         print(json.dumps(pre, indent=2))
#         print("PREFILLED")
#         for n, v in pre["prefilled"].items():
#             print(f"  {n:<16} = {str(v)[:45]!r:<48} <- {pre['sources'][n]}")
#         print("\nFOR THE MODEL")
#         for f in pre["for_model"]:
#             hint = f" (saved: {f['saved_answer']!r})" if f["task"] == "map_saved_answer" else ""
#             print(f"  [{f['task']:<16}] {f['label'][:60]}{hint}")
#         print("\nLEFT BLANK (voluntary):", [f["label"] for f in pre["left_blank"]])

#         print("="*60 + "\n")