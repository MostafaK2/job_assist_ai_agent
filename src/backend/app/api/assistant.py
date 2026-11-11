import logging

"""POST /api/assistant: streams the agent's reply to the chat UI."""
from assistant_stream import RunController, create_run
from assistant_stream.modules.langgraph import append_langgraph_event
from assistant_stream.serialization import AssistantTransportResponse
from fastapi import APIRouter, HTTPException, Request
from langchain_core.messages import HumanMessage

from app.api.schemas import MAX_MESSAGE_CHARS, ChatRequest


router = APIRouter()
log = logging.getLogger("uvicorn.error")

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

SUMMARIZATION_NODE_PREFIX = "SummarizationMiddleware"

def _is_from_summarizer(event_type: str, chunk) -> bool:
    if event_type == "messages":
        _message, metadata = chunk
        return str(metadata.get("langgraph_node", "")).startswith(SUMMARIZATION_NODE_PREFIX)
    if event_type == "updates" and isinstance(chunk, dict):
        return any(str(node).startswith(SUMMARIZATION_NODE_PREFIX) for node in chunk)
    return False

@router.post("/assistant")
async def assistant(request: ChatRequest, http_request: Request):
    agent = http_request.app.state.agent  # built once at startup, with the Postgres checkpointer
    if not request.thread_id:
        raise HTTPException(status_code=400, detail="threadId is required")
    # TEMPORARY (Step 5 replaces this): the thread id comes straight from the browser.
    # Step 5 checks it against the conversations table first.
    config = {"configurable": {"thread_id": request.thread_id}}

    async def run(controller: RunController):
        # controller.state is what the chat shows. Every change to it streams to the browser.
        # (It's a special proxy object, so check for None rather than isinstance(..., dict).)
        if controller.state is None:
            controller.state = {}
        if "messages" not in controller.state:
            controller.state["messages"] = []
        controller.state["summarizing"] = False  # the chat shows a notice while this is True

        new_messages = _user_messages(request)
        if not new_messages:
            return
        for message in new_messages:
            controller.state["messages"].append(message.model_dump())

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
                        log.info("Summarizing earlier messages in thread %s", request.thread_id)
                    continue
                if _is_from_summarizer(event_type, chunk):
                    # The summary is memory-only: never shown to the user.
                    if event_type == "updates":
                        controller.state["summarizing"] = False  # summary done
                    continue
                append_langgraph_event(controller.state, namespace, event_type, chunk)
        finally:
            controller.state["summarizing"] = False  # never leave the notice stuck on


    response = AssistantTransportResponse(create_run(run, state=request.state))
    # Tell proxies (Next.js, Caddy) not to compress or buffer the stream; otherwise
    # the reply only shows up once it's completely finished.
    response.headers["Cache-Control"] = "no-cache, no-transform"
    response.headers["X-Accel-Buffering"] = "no"
    return response