"""Reads and writes for the chat transcript (conversations + chat_messages)."""
import json
import uuid

from langchain_core.messages import BaseMessage
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert

from app.db.engine import SessionLocal
from app.db.models import ChatMessage, Conversation

TITLE_MAX_CHARS = 60
ROLES = {"human": "user", "ai": "assistant", "tool": "tool"}


def parse_thread_id(thread_id: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(thread_id)
    except (ValueError, TypeError):
        return None


async def conversation_exists(conversation_id: uuid.UUID) -> bool:
    # When login exists, this also checks Conversation.user_id == the signed-in user.
    async with SessionLocal() as session:
        found = await session.scalar(
            select(Conversation.id).where(
                Conversation.id == conversation_id,
                Conversation.archived_at.is_(None),
            )
        )
        return found is not None


def _to_json(message: BaseMessage) -> dict:
    # Round-trip through JSON so the JSONB column only ever gets plain JSON values.
    return json.loads(json.dumps(message.model_dump(), default=str))


async def save_messages(conversation_id: uuid.UUID, messages: list[BaseMessage]) -> int:
    """Add messages to the transcript. A message that's already saved is skipped, not duplicated.
    Returns how many were actually added."""
    rows = [
        {
            "conversation_id": conversation_id,
            "message_id": m.id or f"gen-{uuid.uuid4()}",
            "role": ROLES.get(m.type, m.type),
            "content": _to_json(m),
        }
        for m in messages
    ]
    if not rows:
        return 0
    async with SessionLocal() as session:
        result = await session.execute(
            insert(ChatMessage)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["conversation_id", "message_id"])
            .returning(ChatMessage.id)
        )
        added = len(result.all())
        await session.commit()
        return added


async def touch_conversation(conversation_id: uuid.UUID, first_user_text: str) -> None:
    """Move the chat to the top of the sidebar, and give it a title if it has none yet."""
    title = " ".join(first_user_text.split())[:TITLE_MAX_CHARS] or "New chat"
    async with SessionLocal() as session:
        await session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(updated_at=func.now(), title=func.coalesce(Conversation.title, title))
        )
        await session.commit()