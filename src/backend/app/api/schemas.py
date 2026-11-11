"""Request shapes sent by assistant-ui's Assistant Transport (the chat on the Next.js /chat page)."""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MAX_MESSAGE_CHARS = 8000  # a single chat message can't be longer than this


class MessagePart(BaseModel):
    type: str
    text: str | None = None


class UserMessage(BaseModel):
    role: str = "user"
    id: str | None = None
    parts: list[MessagePart]


class AddMessageCommand(BaseModel):
    type: Literal["add-message"]
    message: UserMessage


class ChatRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    commands: list[AddMessageCommand] = Field(default_factory=list)
    # The conversation id from the sidebar. Not used until chat memory is added.
    thread_id: str | None = Field(None, alias="threadId")
    # What the browser currently shows. Sent back to the browser for display only;
    # NEVER passed to the agent, because anyone can edit it in their browser.
    state: dict[str, Any] | None = None