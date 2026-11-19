"""Load all Greenhouse jobs into Postgres. Every run REPLACES companies + jobs.

Run from src/backend:
    python -m app.ingest.sync_greenhouse                 # all companies
    python -m app.ingest.sync_greenhouse --limit 3       # first 3, for testing

How it works:
  1. Fetch every board with ONE request each (?content=true), in parallel. Nothing is
     written while fetching.
  2. In ONE transaction: empty companies + jobs, reset ids, bulk insert everything.
     If anything fails, the transaction rolls back and the old data is kept.
  job_applications is never touched.
"""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, insert, text
from sqlalchemy.orm import Session

from app.config import APP_DATABASE_URL
from app.db.job_models import Company, Job
from app.ingest.greenhouse_client import BoardFetchError, fetch_board_jobs
from app.ingest.html_text import html_to_text, unescape_html

# Parsers
from app.ingest.location_parser import parse_job_location

COMPANIES_FILE = Path(__file__).resolve().parents[2] / "data" / "greenhouse_companies.json"
MAX_WORKERS = 8      # boards fetched at the same time
INSERT_CHUNK = 1000  # job rows per INSERT


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def to_job_row(job: dict, company_id: int, company_name: str, board_token: str, fetched_at: datetime) -> dict | None:
    """Greenhouse job -> jobs row. None if the job is missing required fields."""
    job_id, title = job.get("id"), job.get("title")
    if not job_id or not title:
        return None
    content = unescape_html(job.get("content") or "")
    description_text = html_to_text(content, formatted=False) or None  
    return {
        "company_id": company_id,
        "job_id": int(job_id),
        "company_name": company_name,
        "board_token": board_token,
        "title": title,
        "absolute_url": job.get("absolute_url"),
        "department": next((d.get("name") for d in job.get("departments") or [] if d.get("name")), None),
        "date_posted": parse_ts(job.get("first_published")),
        "updated_at": parse_ts(job.get("updated_at")),
        "application_deadline": parse_ts(job.get("application_deadline")),
        "last_fetched_at": fetched_at,
        "requisition_id": job.get("requisition_id"),
        "internal_job_id": job.get("internal_job_id"),
        "is_active": True,
        "description_html": content or None,
        "description_markdown": html_to_text(content, markdown=True) or None,
        "description_text": description_text,
        "raw": job,
        **parse_job_location(job, description_text=description_text),
    }


def load_companies(path: Path, limit: int | None) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    seen, companies = set(), []
    for c in data:
        token = (c.get("board_token") or "").strip()
        if token and token not in seen:  # skip blanks and duplicate tokens in the file
            seen.add(token)
            companies.append({"board_token": token, "name": c.get("company") or token})
    return companies[:limit] if limit else companies


def fetch_all(companies: list[dict]) -> dict[str, list[dict] | BoardFetchError]:
    def one(c):
        try:
            return c["board_token"], fetch_board_jobs(c["board_token"])
        except BoardFetchError as e:
            return c["board_token"], e

    results = {}
    with ThreadPoolExecutor(MAX_WORKERS) as pool:
        for i, (token, result) in enumerate(pool.map(one, companies), 1):
            results[token] = result
            msg = f"error: {result}" if isinstance(result, Exception) else f"{len(result)} jobs"
            print(f"[{i}/{len(companies)}] {token}: {msg}", flush=True)
    return results


def replace_tables(session: Session, companies: list[dict], results: dict, fetched_at: datetime) -> dict:
    """Empty companies + jobs and insert fresh rows. Caller commits."""
    # No CASCADE on purpose: if a table ever gets a foreign key to these, this fails
    # loudly instead of silently wiping it.
    session.execute(text("TRUNCATE TABLE jobs, companies RESTART IDENTITY"))

    company_rows = []
    for c in companies:
        r = results[c["board_token"]]
        failed = isinstance(r, Exception)
        company_rows.append({
            "board_token": c["board_token"],
            "name": c["name"],
            "job_count": 0 if failed else len(r),
            "last_error": str(r) if failed else None,
            "last_synced_at": fetched_at,
        })
    ids = dict(
        (token, cid) for cid, token in session.execute(
            insert(Company).returning(Company.id, Company.board_token), company_rows
        )
    )

    stats = {"jobs": 0, "skipped_invalid": 0, "skipped_duplicate": 0}
    batch: list[dict] = []
    for c in companies:
        r = results[c["board_token"]]
        if isinstance(r, Exception):
            continue
        seen_ids = set()
        for job in r:
            row = to_job_row(job, ids[c["board_token"]], c["name"], c["board_token"], fetched_at)
            if row is None:
                stats["skipped_invalid"] += 1
                continue
            if row["job_id"] in seen_ids:  # same job listed twice on one board
                stats["skipped_duplicate"] += 1
                continue
            seen_ids.add(row["job_id"])
            batch.append(row)
            if len(batch) >= INSERT_CHUNK:
                session.execute(insert(Job), batch)
                stats["jobs"] += len(batch)
                batch = []
    if batch:
        session.execute(insert(Job), batch)
        stats["jobs"] += len(batch)

    # Keep the real job count (after skipping invalid / duplicate rows)
    session.execute(text(
        "UPDATE companies c SET job_count = sub.n "
        "FROM (SELECT company_id, count(*) AS n FROM jobs GROUP BY company_id) sub "
        "WHERE c.id = sub.company_id"
    ))
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replace companies + jobs with fresh Greenhouse data.")
    parser.add_argument("--companies-file", type=Path, default=COMPANIES_FILE)
    parser.add_argument("--limit", type=int, help="only the first N companies (testing)")
    args = parser.parse_args(argv)

    companies = load_companies(args.companies_file, args.limit)
    print(f"Fetching {len(companies)} boards from {args.companies_file.name} ...")
    fetched_at = datetime.now(timezone.utc)
    results = fetch_all(companies)

    failed = [t for t, r in results.items() if isinstance(r, Exception)]
    if len(failed) == len(companies):
        print("\nEvery board failed (network problem?). Database NOT changed.")
        return 1

    engine = create_engine(APP_DATABASE_URL, pool_pre_ping=True)
    with Session(engine) as session, session.begin():  # one transaction: all or nothing
        stats = replace_tables(session, companies, results, fetched_at)
    engine.dispose()

    print("\n========== SYNC SUMMARY ==========")
    print(f"Companies:        {len(companies)} ({len(companies) - len(failed)} ok, {len(failed)} failed)")
    print(f"Jobs inserted:    {stats['jobs']}")
    print(f"Skipped invalid:  {stats['skipped_invalid']}")
    print(f"Skipped dupes:    {stats['skipped_duplicate']}")
    if failed:
        print("Failed boards (see companies.last_error):", ", ".join(failed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
