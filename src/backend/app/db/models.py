"""Our tables. LangGraph's checkpoint tables are separate and managed by LangGraph itself."""
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(TimestampMixin, Base):
    """Accounts. Created now, stays empty until login is built."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True)       # always stored lowercase
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)                    # Argon2 hash, never the password
    display_name: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    conversations: Mapped[list["Conversation"]] = relationship(back_populates="user")


class Conversation(TimestampMixin, Base):
    """One chat in the sidebar. Its id is also the agent's LangGraph thread_id."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Optional until login exists; a later migration makes it required.
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str | None] = mapped_column(String(200))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User | None] = relationship(back_populates="conversations")
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ChatMessage.id",
    )

    __table_args__ = (
        # The sidebar: "this user's chats, newest first"
        Index("ix_conversations_user_id_updated_at", "user_id", text("updated_at DESC")),
    )


class ChatMessage(Base):
    """The transcript: every message exactly as shown, only ever added to (never summarized)."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)  # also the order
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    message_id: Mapped[str] = mapped_column(String(200))   # LangChain's message id
    role: Mapped[str] = mapped_column(String(20))           # "user" | "assistant" | "tool"
    content: Mapped[dict] = mapped_column(JSONB)            # the full LangChain message, as displayed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped[Conversation] = relationship(back_populates="messages")

    __table_args__ = (
        # The same message can't be saved twice in one conversation
        UniqueConstraint("conversation_id", "message_id"),
        # Opening a chat: "this conversation's messages, in order"
        Index("ix_chat_messages_conversation_id_id", "conversation_id", "id"),
    )