"""The approved jobs for one chat, worked through one at a time (Gate 1 -> review -> next).

Kept on the server (store.py), keyed by the chat's thread id, so the model can't skip, reorder
or repeat jobs: every "next job" message is written by code from this queue.

    start(thread_id, jobs)        jobs = [{"id": "board_token/job_id", "label": "..."}], in order
    current(thread_id)            the job being worked on now, or None
    peek_next(thread_id)          the job after it, or None (doesn't change anything)
    finish(thread_id, outcome)    record "approved" / "skipped" for the current job, move on
    summary(thread_id)            {"approved": [...labels], "skipped": [...labels]}
"""
from app.tools import store

KIND = "queues"


def _get(thread_id: str) -> dict | None:
    return store.get(KIND, thread_id)


def start(thread_id: str, jobs: list[dict]) -> None:
    store.put(KIND, thread_id, {"jobs": jobs, "current": 0, "results": {}}, renew=True)


def current(thread_id: str) -> dict | None:
    q = _get(thread_id)
    return q["jobs"][q["current"]] if q and q["current"] < len(q["jobs"]) else None


def peek_next(thread_id: str) -> dict | None:
    q = _get(thread_id)
    return q["jobs"][q["current"] + 1] if q and q["current"] + 1 < len(q["jobs"]) else None


def finish(thread_id: str, outcome: str) -> None:
    q = _get(thread_id)
    if not q or q["current"] >= len(q["jobs"]):
        return
    q["results"][q["jobs"][q["current"]]["id"]] = outcome
    q["current"] += 1
    store.put(KIND, thread_id, q)


def summary(thread_id: str) -> dict[str, list[str]]:
    q = _get(thread_id) or {"jobs": [], "results": {}}
    return {outcome: [j["label"] for j in q["jobs"] if q["results"].get(j["id"]) == outcome]
            for outcome in ("approved", "skipped")}