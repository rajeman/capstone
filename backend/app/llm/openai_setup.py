import logging
import os

from openai import AsyncOpenAI

from agents import set_default_openai_client, set_trace_processors

from app.config import settings

logger = logging.getLogger(__name__)


def _langsmith_tracing_requested() -> bool:
    """True when common LangSmith / LangChain tracing env toggles are on."""
    for var in ("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2"):
        raw = os.environ.get(var, "").strip().lower()
        if raw in ("true", "1", "yes", "on"):
            return True
    return False


def _init_langsmith_tracing_if_enabled() -> None:
    """Send OpenAI Agents SDK spans to LangSmith when tracing env vars are on."""
    if not _langsmith_tracing_requested():
        return
    if not os.environ.get("LANGSMITH_API_KEY", "").strip():
        logger.warning(
            "LangSmith tracing is enabled (LANGSMITH_TRACING or LANGCHAIN_TRACING_V2) "
            "but LANGSMITH_API_KEY is empty; skipping LangSmith registration."
        )
        return
    try:
        from langsmith.integrations.openai_agents_sdk import OpenAIAgentsTracingProcessor
    except ImportError:
        logger.warning(
            "LangSmith tracing requested but langsmith[openai-agents] is not installed; skipping."
        )
        return
    set_trace_processors([OpenAIAgentsTracingProcessor()])
    logger.info("LangSmith tracing enabled for OpenAI Agents SDK (OpenAIAgentsTracingProcessor).")


def init_openai() -> None:
    """Register the default AsyncOpenAI client used by the OpenAI Agents SDK."""
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    set_default_openai_client(client, use_for_tracing=False)
    _init_langsmith_tracing_if_enabled()
