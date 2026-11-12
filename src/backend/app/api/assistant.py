"""POST /api/assistant: streams the agent's reply to the chat UI."""
import logging
import uuid

from assistant_stream import RunController, create_run
from assistant_stream.modules.langgraph import append_langgraph_event
from assistant_stream.serialization import AssistantTransportResponse
from fastapi import APIRouter, HTTPException, Request
from langchain_core.exceptions import ModelError, ModelRateLimitError
from langchain_core.messages import AIMessage, HumanMessage

from app.api.schemas import MAX_MESSAGE_CHARS, ChatRequest
from app.db.chat_store import conversation_exists, parse_thread_id, save_messages, touch_conversation

router = APIRouter()
log = logging.getLogger("uvicorn.error")

# The summarization step runs as its own graph node. Its output (a "Here is a summary..."
# message) is for the agent's memory only and must not appear in the chat.
SUMMARIZATION_NODE_PREFIX = "SummarizationMiddleware"


def _is_from_summarizer(event_type: str, chunk) -> bool:
    if event_type == "messages":
        _message, metadata = chunk
        return str(metadata.get("langgraph_node", "")).startswith(SUMMARIZATION_NODE_PREFIX)
    if event_type == "updates" and isinstance(chunk, dict):
        return any(str(node).startswith(SUMMARIZATION_NODE_PREFIX) for node in chunk)
    return False


def _finished_messages(event_type: str, chunk) -> list:
    """Complete messages from an 'updates' event (the model's reply, tool results)."""
    if event_type != "updates" or not isinstance(chunk, dict):
        return []
    found = []
    for update in chunk.values():
        if isinstance(update, dict):
            found.extend(update.get("messages") or [])
    return found


def _notice(text: str) -> dict:
    """A short assistant message for the chat (shown, but not part of the agent's memory)."""
    return AIMessage(content=text, id=f"notice-{uuid.uuid4()}").model_dump()


def _user_messages(request: ChatRequest) -> list[HumanMessage]:
    """Turn the 'add-message' commands into LangChain messages (text only, length-limited)."""
    messages = []
    for command in request.commands:
        if command.message.role != "user":
            continue  # only the user's own messages are accepted from the browser
        text = "\n".join(p.text for p in command.message.parts if p.type == "text" and p.text).strip()
        if text:
            messages.append(HumanMessage(content=text[:MAX_MESSAGE_CHARS], id=command.message.id))
    return messages


@router.post("/assistant")
async def assistant(request: ChatRequest, http_request: Request):
    agent = http_request.app.state.agent  # built once at startup, with the Postgres checkpointer
    conversation_id = parse_thread_id(request.thread_id)
    if conversation_id is None:
        raise HTTPException(status_code=400, detail="threadId must be a conversation id")
    # Only chats created through our API can be used. The browser can't invent a thread.
    if not await conversation_exists(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    config = {"configurable": {"thread_id": str(conversation_id)}}

    new_messages = _user_messages(request)
    if not new_messages:
        raise HTTPException(status_code=400, detail="No message to send")
    # Save the user's message before the agent runs, so it's kept even if the agent fails.
    # If it was already saved (double click, network retry, replayed request), don't run again.
    if await save_messages(conversation_id, new_messages) == 0:
        raise HTTPException(status_code=409, detail="This message was already sent")
    await touch_conversation(conversation_id, new_messages[0].content)

    async def run(controller: RunController):
        # controller.state is what the chat shows. Every change to it streams to the browser.
        # (It's a special proxy object, so check for None rather than isinstance(..., dict).)
        if controller.state is None:
            controller.state = {}
        if "messages" not in controller.state:
            controller.state["messages"] = []
        controller.state["summarizing"] = False  # the chat shows a notice while this is True

        for message in new_messages:
            controller.state["messages"].append(message.model_dump())

        # Only the NEW message goes in. The checkpointer adds this thread's earlier messages
        # from Postgres, so the agent remembers the conversation without trusting the browser.
        replies = []
        try:
            async for namespace, event_type, chunk in agent.astream(
                {"messages": new_messages},
                config,
                stream_mode=["messages", "updates", "custom"],
                subgraphs=True,
            ):
                if event_type == "custom":
                    # Sent by the summarizer just before it starts writing (see build_summarizer).
                    if isinstance(chunk, dict) and chunk.get("summarizing"):
                        controller.state["summarizing"] = True
                        log.info("Summarizing earlier messages in conversation %s", conversation_id)
                    continue
                if _is_from_summarizer(event_type, chunk):
                    # The summary is memory-only: never shown, never saved to the transcript.
                    if event_type == "updates":
                        controller.state["summarizing"] = False  # summary done
                    continue
                replies.extend(_finished_messages(event_type, chunk))
                append_langgraph_event(controller.state, namespace, event_type, chunk)
        except ModelRateLimitError:
            log.warning("Gemini rate limit or quota reached (thread %s)", conversation_id)
            controller.state["messages"].append(_notice(
                "The AI service has hit its usage limit, so I can't reply right now. "
                "Please try again later."
            ))
        except ModelError:
            log.exception("Gemini call failed (thread %s)", conversation_id)
            controller.state["messages"].append(_notice(
                "Something went wrong talking to the AI service. Please try again."
            ))
        finally:
            controller.state["summarizing"] = False
            # Runs even if the agent errors or the user presses Stop: keep what was produced.
            await save_messages(conversation_id, replies)

    response = AssistantTransportResponse(create_run(run, state=request.state))
    # Tell proxies (Next.js, Caddy) not to compress or buffer the stream; otherwise
    # the reply only shows up once it's completely finished.
    response.headers["Cache-Control"] = "no-cache, no-transform"
    response.headers["X-Accel-Buffering"] = "no"
    return response

