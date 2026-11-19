"""Request shapes sent by assistant-ui's Assistant Transport (the chat on the Next.js /chat page)."""
from typing import Annotated, Any, Literal, Union

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

class JobDecisionsCommand(BaseModel):
    """Continue on a search_jobs card: every job starts approved; only the skipped ids are sent."""
    model_config = ConfigDict(populate_by_name=True)

    type: Literal["job-decisions"]
    tool_call_id: str = Field(alias="toolCallId", min_length=1, max_length=200)
    skipped: list[Annotated[str, Field(max_length=300)]] = Field(default_factory=list, max_length=20)


Command = Annotated[Union[AddMessageCommand, JobDecisionsCommand], Field(discriminator="type")]

class ChatRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    commands: list[Command] = Field(default_factory=list)
    # The conversation id from the sidebar. Not used until chat memory is added.
    thread_id: str | None = Field(None, alias="threadId")
    # What the browser currently shows. Sent back to the browser for display only;
    # NEVER passed to the agent, because anyone can edit it in their browser.
    state: dict[str, Any] | None = None

