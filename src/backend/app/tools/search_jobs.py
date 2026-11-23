"""search_jobs: find jobs in our Postgres `jobs` table, ranked against the user's profile.

  1. app/db/job_search.py     one indexed SQL query: hard filters -> up to 200 candidates
  2. app/tools/job_scoring.py score each candidate 0-100 in Python, with reasons + warnings
  3. here                     a few short lines for the MODEL, and {columns, rows} for the
                              chat's Data Table (the tool message's artifact; the model never sees it)

Filters are exactly the tool arguments the model chose (it calls get_preferences first when the
user gave no details). The profile is used only to RANK: skills, level, experience, work
authorization. The model never reads job descriptions or the skill list.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from langchain.tools import tool
from pydantic import Field
from sqlalchemy.exc import SQLAlchemyError

from app.db.job_search import Filters, find_candidates
from app.ingest.location_parser import parse_location
from app.tools.job_scoring import PREF_LEVELS, Seeker, score_job, years_of_experience
from app.tools.profile import load_full_profile

log = logging.getLogger("agent.tools")

MAX_RESULTS = 20

# assistant-ui Data Table columns (https://www.assistant-ui.com/elements/data-table).
COLUMNS = [
    {"key": "title", "label": "Job", "priority": "primary", "format": {"kind": "link", "hrefKey": "url"}},
    {"key": "company", "label": "Company", "priority": "secondary"},
    {"key": "location", "label": "Location"},
    {"key": "work_types", "label": "Work type", "format": {"kind": "badge", "tones": {"remote": "success"}}},
    {"key": "posted", "label": "Posted", "format": {"kind": "date", "style": "relative"}},
    {"key": "score", "label": "Match", "format": {"kind": "number", "decimals": 0}},
    {"key": "reasons", "label": "Why", "format": {"kind": "list", "max": 3}, "sortable": False},
    {"key": "warnings", "label": "Warnings", "format": {"kind": "list", "max": 3}, "sortable": False},
]

Words = Annotated[list[Annotated[str, Field(max_length=80)]], Field(max_length=10)]


# ---------------------------------------------------------------- inputs -> filters
def _parse_places(texts: list[str]) -> tuple[list[dict], list[str | None]]:
    """['New York, NY', 'Remote (US)'] -> places [{city, state, country}], remote countries ['US']."""
    places, remote = [], []
    for text in texts:
        r = parse_location(text.replace("(", ", ").replace(")", " "))   # "Remote (US)" -> "Remote, US"
        locs = [{k: l[k] for k in ("city", "state", "country", "region") if l.get(k)} for l in r["locations"]]
        if "remote" in r["work_types"]:
            remote += [l.get("country") for l in locs] or [None]
        else:
            places += locs
    return places, list(dict.fromkeys(remote))


def _coarse(place: dict) -> dict:
    """Filter by US state or by country (city-level matching is left to scoring: Brooklyn ≈ NYC)."""
    if place.get("country") == "US" and place.get("state"):
        return {"state": place["state"], "country": "US"}
    return {k: place[k] for k in ("country",) if place.get(k)} or {k: place[k] for k in ("region",) if place.get(k)}


def _build(profile: dict, a: dict) -> tuple[Filters, Seeker, dict]:
    """Filters come ONLY from the tool arguments (what the model chose).
    The profile is used for ranking only: skills, level, experience, authorization, and the
    preferred titles/places when the model didn't give any (they reorder, never hide, jobs)."""
    prefs = profile.get("preferences") or {}
    places, remote = _parse_places(a["locations"])
    filters = Filters(
        places=list({str(sorted(p.items())): p for p in map(_coarse, places) if p}.values()),
        remote_countries=remote, work_types=a["work_types"],
        companies=a["companies"], exclude_companies=a["exclude_companies"], department=a["department"],
        posted_since=datetime.now(timezone.utc) - timedelta(days=a["posted_within_days"]) if a["posted_within_days"] else None,
        rank_text=" ".join([*a["titles"], a["query"]]), must_match=a["query"], titles=a["titles"],
        user_id=None,  # single-user for now: applications are saved with user_id NULL
    )
    rank_places, rank_remote = (places, remote) if a["locations"] else _parse_places(prefs.get("locations") or [])
    seeker = Seeker(
        titles=a["titles"] or prefs.get("target_titles") or [], query=a["query"],
        skills=list(dict.fromkeys([*profile.get("skills", []),
                                   *[t for w in profile.get("work_history") or [] for t in w.get("technologies") or []]])),
        levels={PREF_LEVELS[s.lower()] for s in prefs.get("seniority") or [] if s.lower() in PREF_LEVELS},
        years=years_of_experience(profile.get("work_history")),
        places=rank_places, remote_countries=rank_remote,
        work_types=a["work_types"],
        authorization=profile.get("work_authorization") or {},
        has_clearance=bool((profile.get("security_clearance") or {}).get("has_clearance")),
    )
    used = {k: a[k] for k in ("query", "titles", "locations", "work_types", "companies",
                              "exclude_companies", "department", "posted_within_days") if a[k]}
    return filters, seeker, used


# ---------------------------------------------------------------- output
def _where(locations: list[dict], work_types: list[str]) -> str:
    def one(l):
        name = ", ".join(x for x in (l.get("city"), l.get("state") or l.get("country")) if x) \
            or l.get("country") or l.get("region") or ""
        return f"Remote ({name})" if "remote" in work_types and not l.get("city") and name else name
    names = [n for n in dict.fromkeys(one(l) for l in locations) if n] or (["Remote"] if "remote" in work_types else [])
    return ", ".join(names[:1]) + (f" +{len(names) - 1}" if len(names) > 1 else "") if names else "?"


def _ago(posted: datetime | None) -> str:
    if not posted:
        return "?"
    days = (datetime.now(timezone.utc) - posted).days
    return "today" if days < 1 else f"{days}d ago" if days < 14 else f"{days // 7}w ago"


def _line(r: dict) -> str:
    """~40 tokens per job for the model."""
    parts = [r["id"], r["title"], r["company"], r["location"], "/".join(r["work_types"]) or "?",
             r["_ago"], str(r["score"]), "; ".join(r["reasons"]) or "-"]
    return " | ".join(parts) + (f" | ⚠ {'; '.join(r['warnings'])}" if r["warnings"] else "")


# ---------------------------------------------------------------- tool
@tool(response_format="content_and_artifact")
def search_jobs(
    query: Annotated[str, Field(max_length=200, description="Extra words the job must mention, e.g. 'robotics'")] = "",
    titles: Words = [],
    locations: Words = [],
    work_types: list[Literal["remote", "hybrid", "onsite"]] = [],
    companies: Words = [],
    exclude_companies: Words = [],
    department: Annotated[str, Field(max_length=80)] = "",
    posted_within_days: Annotated[int | None, Field(ge=1, le=365)] = None,
    limit: Annotated[int, Field(ge=1, le=MAX_RESULTS)] = 10,
):
    """Search open jobs. Only the filters you pass are applied (empty = no filter); use
    get_preferences first if the user didn't say what they want. Locations like "New York, NY"
    or "Remote (US)". Results are ranked against the user's résumé (0-100 match): show them in
    order with their reasons and warnings. Each result's id is "board_token/job_id"."""
    args = locals().copy()

    if limit <= 0:
        return ("Invalid limit; tell the user to pick a positive number and don't make up jobs.",
                {"columns": COLUMNS, "rows": []})
    try:
        profile = load_full_profile()  # for ranking only
    except (LookupError, OSError, ValueError) as error:
        log.info("search_jobs: no profile (%r); searching without it", error)
        profile = {}
    filters, seeker, used = _build(profile, args)

    try:
        candidates, total, hidden = find_candidates(filters)
    except SQLAlchemyError as error:
        log.exception("search_jobs failed: %r", error)
        return ("The job database couldn't be searched. Tell the user and don't make up jobs.",
                {"columns": COLUMNS, "rows": []})

    max_rank = max((c["text_rank"] for c in candidates), default=0) or 1.0
    scored = sorted(((score_job(seeker, c, max_rank), c) for c in candidates),
                    key=lambda sc: (sc[0]["score"], sc[1]["date_posted"] or datetime.min.replace(tzinfo=timezone.utc)),
                    reverse=True)[:limit]
    rows = [{
        "id": f"{c['board_token']}/{c['job_id']}",
        "title": c["title"], "url": c["absolute_url"], "company": c["company_name"],
        "location": _where(c["locations"], c["work_types"]), "work_types": c["work_types"],
        "posted": c["date_posted"].date().isoformat() if c["date_posted"] else None,
        "score": s["score"], "reasons": s["reasons"], "warnings": s["warnings"],
        "department": c["department"], "board_token": c["board_token"], "job_id": c["job_id"],
        "_ago": _ago(c["date_posted"]),
    } for s, c in scored]

    filters_used = "; ".join(f"{k}={', '.join(map(str, v)) if isinstance(v, list) else v}" for k, v in used.items()) or "none"
    if not rows:
        content = f"No open jobs match (filters: {filters_used}). Search again with fewer or broader filters."
    else:
        content = "\n".join([
            f"{len(rows)} of {total} matches, best first"
            + (f" ({hidden} already applied, hidden)" if hidden else "") + f". Filters: {filters_used}.",
            "id | title | company | location | work | posted | match | why | warnings",
            *map(_line, rows),
        ])
    for r in rows:
        r.pop("_ago")
    return content, {"columns": COLUMNS, "rows": rows, "total": total, "hidden_applied": hidden, "filters": used}