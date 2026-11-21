"""What a card button (Gate 1 job picker, Gate 2 review card) turns into on the server."""
from collections.abc import Callable
from dataclasses import dataclass, field

from langchain_core.messages import HumanMessage


@dataclass
class Decision:
    message: HumanMessage                     # the one message the agent gets
    # Changes to server state (queue, draft status). Run only AFTER the message is saved, so a
    # repeated click (refused as "already sent", 409) can't change anything twice.
    after_save: Callable[[], None] = field(default=lambda: None)