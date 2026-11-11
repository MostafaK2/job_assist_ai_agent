from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langgraph.checkpoint.base import BaseCheckpointSaver

from langchain_core.messages import AnyMessage, get_buffer_string
from langchain_core.runnables import RunnableLambda
from langgraph.config import get_stream_writer

from app.agent.llm import get_llm
from app.agent.prompts import SUMMARY_PROMPT, SYSTEM_PROMPT
from app.config import (
    SUMMARY_KEEP_MESSAGES,
    SUMMARY_TRIGGER_MESSAGES,
    SUMMARY_TRIGGER_TOKENS,
    SUMMARY_TRIM_TOKENS,
)
from app.tools import ALL_TOOLS


def build_summarizer() -> SummarizationMiddleware:
    """Condenses the agent's memory of a long chat. The user's transcript is never changed."""
    llm = get_llm()

    def summary_prompt(messages: list[AnyMessage]) -> str:
        # Same formatting the middleware uses by default: each message tagged with its author.
        return SUMMARY_PROMPT.format(messages=get_buffer_string(messages, format="xml"))

    # This only runs when a summary is actually needed. It first tells the chat
    # (stream_mode="custom") so the UI can show a notice while the summary is written.
    def summarize(messages: list[AnyMessage]) -> str:
        get_stream_writer()({"summarizing": True})
        return llm.invoke(summary_prompt(messages)).text

    async def asummarize(messages: list[AnyMessage]) -> str:
        get_stream_writer()({"summarizing": True})
        return (await llm.ainvoke(summary_prompt(messages))).text

    return SummarizationMiddleware(
        model=llm,  # used to count tokens
        summarizer=RunnableLambda(summarize, afunc=asummarize),
        # A list means "whichever comes first".
        trigger=[("tokens", SUMMARY_TRIGGER_TOKENS), ("messages", SUMMARY_TRIGGER_MESSAGES)],
        keep=("messages", SUMMARY_KEEP_MESSAGES),
        trim_tokens_to_summarize=SUMMARY_TRIM_TOKENS,
    )


def build_agent(checkpointer: BaseCheckpointSaver | None = None):
    """checkpointer=None: no memory (used by the CLI). With one: remembers each thread_id."""
    return create_agent(
        model=get_llm(),
        tools=ALL_TOOLS,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
        middleware=[build_summarizer()],
    )


def run(query: str) -> str:
    agent = build_agent()
    result = agent.invoke({"messages": [{"role": "user", "content": query}]})
    return result["messages"][-1].text