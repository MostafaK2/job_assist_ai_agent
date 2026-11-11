"""/api/threads: the chat list in the sidebar. Each conversation id is also the agent's thread_id."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_session
from app.db.models import ChatMessage, Conversation

router = APIRouter(prefix="/threads", tags=["threads"])

MAX_THREADS_LISTED = 100


class ThreadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None
    archived: bool
    created_at: datetime
    updated_at: datetime


class ThreadUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")  # unknown fields are an error, not silently ignored

    title: str | None = Field(None, min_length=1, max_length=200)
    archived: bool | None = None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    message_id: str
    role: str
    content: dict
    created_at: datetime


def _out(conversation: Conversation) -> ThreadOut:
    return ThreadOut(
        id=conversation.id,
        title=conversation.title,
        archived=conversation.archived_at is not None,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


async def _get_or_404(session: AsyncSession, thread_id: uuid.UUID) -> Conversation:
    # When login exists, this also checks that the conversation belongs to the signed-in user.
    conversation = await session.get(Conversation, thread_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.post("", status_code=201, response_model=ThreadOut)
async def create_thread(session: AsyncSession = Depends(get_session)):
    """A new, empty chat. The server picks the id; the browser never does."""
    conversation = Conversation()
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return _out(conversation)


@router.get("", response_model=list[ThreadOut])
async def list_threads(archived: bool = False, session: AsyncSession = Depends(get_session)):
    """The sidebar: newest first. ?archived=true lists archived chats instead."""
    archived_filter = Conversation.archived_at.is_not(None) if archived else Conversation.archived_at.is_(None)
    rows = await session.scalars(
        select(Conversation)
        .where(archived_filter)
        .order_by(Conversation.updated_at.desc())
        .limit(MAX_THREADS_LISTED)
    )
    return [_out(c) for c in rows]


@router.get("/{thread_id}", response_model=ThreadOut)
async def get_thread(thread_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    return _out(await _get_or_404(session, thread_id))


@router.patch("/{thread_id}", response_model=ThreadOut)
async def update_thread(
    thread_id: uuid.UUID, changes: ThreadUpdate, session: AsyncSession = Depends(get_session)
):
    """Rename and/or archive (archived=true) or unarchive (archived=false) a chat."""
    conversation = await _get_or_404(session, thread_id)
    if changes.title is not None:
        title = " ".join(changes.title.split())  # no line breaks or runs of spaces
        if not title:
            raise HTTPException(status_code=422, detail="Title can't be blank")
        conversation.title = title
    if changes.archived is not None:
        conversation.archived_at = func.now() if changes.archived else None
    await session.commit()
    await session.refresh(conversation)
    return _out(conversation)


@router.delete("/{thread_id}", status_code=204)
async def delete_thread(
    thread_id: uuid.UUID, request: Request, session: AsyncSession = Depends(get_session)
):
    """Deletes the chat, its saved messages (CASCADE) and the agent's memory of it."""
    conversation = await _get_or_404(session, thread_id)
    await session.delete(conversation)
    await session.commit()
    await request.app.state.checkpointer.adelete_thread(str(thread_id))
    return Response(status_code=204)


@router.get("/{thread_id}/messages", response_model=list[MessageOut])
async def list_messages(thread_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    """The saved transcript, oldest first. Used to show an old chat again."""
    await _get_or_404(session, thread_id)
    rows = await session.scalars(
        select(ChatMessage).where(ChatMessage.conversation_id == thread_id).order_by(ChatMessage.id)
    )
    return list(rows)