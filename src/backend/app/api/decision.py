"""What a card button (job picker, review card, fill card) turns into on the server."""
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from langchain_core.messages import HumanMessage

from app.tools import job_queue


@dataclass
class Decision:
    message: HumanMessage                     # the one message the agent gets
    # Changes to server state (queue, draft status, job_applications). Run only AFTER the message
    # is saved, so a repeated click (refused as "already sent", 409) can't change anything twice.
    # May be async (database writes).
    after_save: Callable[[], None | Awaitable[None]] = field(default=lambda: None)


def next_job_text(thread_id: str, outcome: str, label: str) -> str:
    """What to do after this job ("submitted" / "skipped"), from the queue: written by code, so the
    model can't skip, reorder or repeat jobs."""
    if (nxt := job_queue.peek_next(thread_id)) is not None:
        return f" Next, prepare this one: {nxt['label']}."
    done = job_queue.summary(thread_id)
    done[outcome].append(label)
    parts = [f"{k.capitalize()}: {'; '.join(v)}." for k, v in done.items() if v]
    return " That was the last approved job. " + " ".join(parts) + " Summarize this in one or two lines."