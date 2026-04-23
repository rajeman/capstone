from openai import AsyncOpenAI

from agents import set_default_openai_client

from app.config import settings


def init_openai() -> None:
    """Register the default AsyncOpenAI client used by the OpenAI Agents SDK."""
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    set_default_openai_client(client, use_for_tracing=False)
