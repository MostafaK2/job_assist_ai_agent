"""Stage 1 of search_jobs: ONE SQL query that applies the hard filters and returns ranked candidates.

Everything here uses an index: GIN on locations / work_types / search_tsv, trigram on title.
Scoring against the profile happens afterwards in Python (app/tools/job_scoring.py), on these
candidates only.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache

from sqlalchemy import Engine, Float, and_, create_engine, exists, func, literal, or_, select
from sqlalchemy.orm import Session

from app.config import APP_DATABASE_URL
from app.db.job_models import Job, JobApplication

CANDIDATES = 200  # rows handed to the Python scorer

@dataclass
class Filters:
    places: list[dict] = field(default_factory=list)       # any of: {"state": "NY", "country": "US"}
    remote_countries: list[str | None] = field(default_factory=list)  # remote OK here; None = anywhere
    work_types: list[str] = field(default_factory=list)    # any of; unknown work type always passes
    companies: list[str] = field(default_factory=list)
    exclude_companies: list[str] = field(default_factory=list)
    department: str = ""
    posted_since: datetime | None = None
    rank_text: str = ""        # title + query words, ORed: ranks candidates, doesn't filter
    must_match: str = ""       # the user's own query words: must appear somewhere in the job
    titles: list[str] = field(default_factory=list)        # fuzzy title similarity (pg_trgm)
    user_id: uuid.UUID | None = None                       # whose applications to hide


@lru_cache(maxsize=1)
def _engine() -> Engine:
    return create_engine(APP_DATABASE_URL, pool_pre_ping=True)


def _ors(words: str) -> str:
    """'backend engineer robotics' -> 'backend or engineer or robotics' (websearch_to_tsquery syntax)."""
    return " or ".join(w for w in words.replace('"', " ").split() if w.lower() not in {"or", "and", "-"})


def find_candidates(f: Filters) -> tuple[list[dict], int, int]:
    """-> (candidate rows, total matches, already-applied matches hidden)."""
    applied = exists().where(
        JobApplication.board_token == Job.board_token,
        JobApplication.job_id == Job.job_id,
        JobApplication.user_id.is_not_distinct_from(f.user_id),
    )
    where = [Job.is_active]

    # Location: any wanted place, or remote work in a wanted country.
    loc = [Job.locations.contains([p]) for p in f.places]
    for country in f.remote_countries:
        remote = Job.work_types.contains(["remote"])
        loc.append(and_(remote, or_(Job.locations.contains([{"country": country}]),
                                    func.jsonb_array_length(Job.locations) == 0))
                   if country else remote)
    if loc:
        where.append(or_(*loc))
    if f.work_types:
        where.append(or_(Job.work_types.overlap(f.work_types), func.cardinality(Job.work_types) == 0))
    if f.companies:
        where.append(or_(*[Job.company_name.ilike(f"%{c}%") for c in f.companies]))
    for c in f.exclude_companies:
        where.append(~Job.company_name.ilike(f"%{c}%"))
    if f.department:
        where.append(Job.department.ilike(f"%{f.department}%"))
    if f.posted_since:
        where.append(Job.date_posted >= f.posted_since)
    if f.must_match:
        where.append(Job.search_tsv.op("@@")(func.websearch_to_tsquery("english", f.must_match)))

    # Ranking: full-text rank (title words weigh most) + fuzzy title similarity.
    words = _ors(f.rank_text)
    zero = literal(0.0, Float)
    rank = func.ts_rank_cd(Job.search_tsv, func.websearch_to_tsquery("english", words), 32) if words else zero
    sim = func.greatest(*[func.similarity(Job.title, t) for t in f.titles]) if f.titles else zero
    if words:  # keep only jobs that relate to the words at all
        where.append(or_(Job.search_tsv.op("@@")(func.websearch_to_tsquery("english", words)), sim > 0.3))

    q = (
        select(
            Job.board_token, Job.job_id, Job.title, Job.company_name, Job.department,
            Job.absolute_url, Job.date_posted, Job.locations, Job.work_types, Job.description_text,
            rank.label("text_rank"), sim.label("title_sim"), applied.label("applied"),
            func.count().over().label("total"),
            func.count().filter(applied).over().label("total_applied"),
        )
        .where(*where)
        .order_by((rank + sim).desc(), Job.date_posted.desc().nulls_last())
        .limit(CANDIDATES)
    )
    with Session(_engine()) as session:
        rows = [dict(r) for r in session.execute(q).mappings()]
    if not rows:
        return [], 0, 0
    total, hidden = rows[0]["total"], rows[0]["total_applied"]
    return [r for r in rows if not r["applied"]], total - hidden, hidden