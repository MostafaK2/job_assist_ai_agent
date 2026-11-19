"""Stage 2 of search_jobs: score each candidate 0-100 against the seeker, with reasons and warnings.

Pure functions, no database or model calls, so the same search always ranks the same way.
Tune the ranking by changing WEIGHTS.
"""
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from rapidfuzz import fuzz

WEIGHTS = {"title": 40, "skills": 35, "location": 8, "work_type": 6, "text": 6, "recency": 5}  # sums to 100
SENIORITY_FLOOR = 0.5

SKILLS_FOR_FULL_MARKS = 5     # this many of the seeker's skills in a description = full skill score
RECENCY_HALF_LIFE_DAYS = 30

# Job level from the title. Order matters: the first match wins.
LEVELS = [
    (0, r"intern(ship)?|co-?op|apprentice"),
    (1, r"new grad|graduate|entry|junior|jr|associate|early career|\bi\b|\b1\b"),
    (4, r"staff|principal|distinguished|architect|lead|manager|head|director|vp"),
    (3, r"senior|sr|\biii\b|\b3\b"),
    (2, r"\bii\b|\b2\b|mid"),
]
PREF_LEVELS = {"intern": 0, "internship": 0, "entry-level": 1, "entry": 1, "junior": 1, "new grad": 1,
               "mid": 2, "mid-level": 2, "senior": 3, "staff": 4, "principal": 4, "lead": 4}
LEVEL_WORDS = re.compile(r"\b(?:senior|sr|junior|jr|staff|principal|lead|intern|new grad|entry level|"
                         r"i{1,3}|iv|[1-4])\b|\([^)]*\)|,.*$|\s[/|–-]\s.*$", re.I)  # drops ", Payments", " - Remote"
YEARS = re.compile(r"(\d{1,2})\s*\+?\s*(?:-\s*\d{1,2}\s*)?(?:years?|yrs?)", re.I)

WARN = {  # description patterns -> warning (only shown when it conflicts with the profile)
    "clearance": re.compile(r"\b(?:security clearance|ts/sci|top secret|secret clearance|clearance required|"
                            r"active clearance)\b", re.I),
    "no_sponsorship": re.compile(r"\b(?:unable to|not able to|cannot|can ?not|do(?:es)? not|will not|won't)\s+"
                                 r"(?:provide\s+|offer\s+)?(?:visa\s+|immigration\s+)?sponsor", re.I),
    "citizenship": re.compile(r"\bu\.?s\.? citizens?(?:hip)?\s+(?:is\s+|are\s+)?(?:required|only)|"
                              r"must be a u\.?s\.? citizen|\bitar\b", re.I),
}
AUTH_FLAGS = {"US": "authorized_to_work_in_us", "CA": "authorized_to_work_in_canada",
              "GB": "authorized_to_work_in_united_kingdom"}


@dataclass
class Seeker:
    """What scoring needs from the profile + this search. Built once per search."""
    titles: list[str] = field(default_factory=list)
    query: str = ""
    skills: list[str] = field(default_factory=list)
    levels: set[int] = field(default_factory=set)          # wanted job levels (0-4); empty = any
    years: float = 0.0                                      # full-time experience
    places: list[dict] = field(default_factory=list)       # wanted {city, state, country}
    remote_countries: list[str | None] = field(default_factory=list)
    work_types: list[str] = field(default_factory=list)    # requested in this search
    authorization: dict = field(default_factory=dict)      # profile["work_authorization"]
    has_clearance: bool = False

    def __post_init__(self):
        self._skill_res = [(s, re.compile(rf"(?<![\w+#.]){re.escape(s)}(?![\w+#])", re.I)) for s in self.skills]
        self._titles = [_clean_title(t) for t in self.titles]


def _clean_title(title: str) -> str:
    return re.sub(r"\s+", " ", LEVEL_WORDS.sub(" ", title)).strip().lower()


def job_level(title: str) -> int | None:
    t = title.lower()
    return next((lvl for lvl, rx in LEVELS if re.search(rf"\b(?:{rx})\b", t)), None)


def years_required(text: str) -> int | None:
    """Smallest 'N+ years' that sits near the word experience (ignores '3 years of funding')."""
    found = [int(m.group(1)) for m in YEARS.finditer(text or "")
             if re.search(r"experience|professional|industry|working|building|engineering",
                          re.split(r"[.;\n]", text[m.end():m.end() + 60])[0], re.I) and int(m.group(1)) <= 20]
    return min(found) if found else None


def _title_score(s: Seeker, title: str) -> float:
    targets = s._titles + ([s.query.lower()] if s.query else [])
    if not targets:
        return 0.5
    clean = _clean_title(title)
    return max(fuzz.token_set_ratio(clean, t) for t in targets) / 100


def _seniority(s: Seeker, title: str, text: str) -> tuple[float, int | None, int | None]:
    level, need = job_level(title), years_required(text)
    if not s.levels:
        lvl_fit = 1.0
    elif level is None:
        lvl_fit = 0.8                                   # unlabelled titles are often open to juniors
    else:
        lvl_fit = {0: 1.0, 1: 0.6, 2: 0.2}.get(min(abs(level - w) for w in s.levels), 0.0)
    gap = (need or 0) - s.years
    yrs_fit = 1.0 if gap <= 0 else 0.7 if gap <= 2 else 0.3 if gap <= 4 else 0.0
    return min(lvl_fit, yrs_fit), level, need


def _location_score(s: Seeker, locations: list[dict], work_types: list[str]) -> float:
    if not s.places and not s.remote_countries:
        return 0.5
    best = 0.0
    for loc in locations or [{}]:
        if "remote" in work_types and any(c in (None, loc.get("country")) for c in s.remote_countries):
            best = max(best, 1.0)
        for p in s.places:
            if p.get("country") != loc.get("country"):
                continue
            if p.get("city") and p.get("city") == loc.get("city"):
                best = max(best, 1.0)
            elif p.get("state") and p.get("state") == loc.get("state"):
                best = max(best, 0.8)
            else:
                best = max(best, 0.5)                   # same country: relocation
    return best if locations else max(best, 0.4)


def _work_type_score(s: Seeker, work_types: list[str]) -> float:
    """Confirmed match beats unknown (unknown still passes the filter)."""
    if not s.work_types:
        return 0.5
    return 1.0 if set(work_types) & set(s.work_types) else 0.4 if not work_types else 0.0


def _recency(posted: datetime | None) -> float:
    if not posted:
        return 0.3
    days = max((datetime.now(timezone.utc) - posted).days, 0)
    return 0.5 ** (days / RECENCY_HALF_LIFE_DAYS)


def _warnings(s: Seeker, text: str, locations: list[dict], work_types: list[str], need: int | None) -> list[str]:
    out = []
    if WARN["clearance"].search(text) and not s.has_clearance:
        out.append("Needs security clearance")
    if WARN["no_sponsorship"].search(text) and (s.authorization.get("requires_sponsorship_now")
                                                or s.authorization.get("requires_sponsorship_future")):
        out.append("No visa sponsorship")
    if WARN["citizenship"].search(text):
        out.append("US citizens only")
    countries = {l.get("country") for l in locations if l.get("country")}
    blocked = [c for c in countries if c in AUTH_FLAGS and s.authorization.get(AUTH_FLAGS[c]) is False]
    if countries and len(blocked) == len(countries):
        out.append(f"Needs work authorization in {', '.join(sorted(blocked))}")
    if need is not None and need - s.years >= 3:
        out.append(f"Asks for {need}+ years")
    return out


def score_job(s: Seeker, job: dict, max_rank: float) -> dict:
    """-> {"score": 0-100, "reasons": [...], "warnings": [...], "parts": {...}} for one candidate."""
    text = f"{job['title']}\n{job.get('description_text') or ''}"
    matched = [name for name, rx in s._skill_res if rx.search(text)]
    seniority, level, need = _seniority(s, job["title"], text)
    parts = {
        "title": _title_score(s, job["title"]),
        "skills": min(len(matched) / SKILLS_FOR_FULL_MARKS, 1.0) if s.skills else 0.5,
        "seniority": seniority,
        "location": _location_score(s, job.get("locations") or [], job.get("work_types") or []),
        "work_type": _work_type_score(s, job.get("work_types") or []),
        "text": (job.get("text_rank") or 0) / max_rank if max_rank else 0.0,
        "recency": _recency(job.get("date_posted")),
    }
    reasons = []
    if parts["title"] >= 0.85:
        reasons.append("title match")
    if matched:
        reasons.append(", ".join(matched[:4]) + (f" +{len(matched) - 4}" if len(matched) > 4 else ""))
    if s.levels and level in s.levels:
        reasons.append("level fits")
    if parts["location"] >= 0.8:
        reasons.append("location fits")
    if s.work_types and parts["work_type"] == 1.0:
        reasons.append("/".join(sorted(set(s.work_types) & set(job.get("work_types") or []))))
    return {
        "score": round(sum(WEIGHTS[k] * parts[k] for k in WEIGHTS) * (SENIORITY_FLOOR + (1 - SENIORITY_FLOOR) * seniority)),
        "reasons": reasons,
        "warnings": _warnings(s, text, job.get("locations") or [], job.get("work_types") or [], need),
        "parts": {k: round(v, 2) for k, v in parts.items()},  # for debugging / tuning, not shown to the model
    }


def years_of_experience(work_history: list[dict]) -> float:
    """Full-time years only: internships and part-time jobs don't count toward 'N+ years'."""
    total = 0
    for w in work_history or []:
        if (w.get("employment_type") or "").lower() in {"internship", "part_time", "part-time", "contract_part_time"}:
            continue
        start = _date(w.get("start_date"))
        end = _date(w.get("end_date")) or date.today()
        if start and end > start:
            total += (end - start).days
    return round(total / 365, 1)


def _date(value) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None