from agents import Agent

from app.llm.agent import create_capstone_agent


def create_banking_agent(*, clerk_user_id: str, system_prompt: str | None) -> Agent:
    """Same capabilities as the capstone agent; name kept for chat / logging compatibility."""
    return create_capstone_agent(
        clerk_user_id=clerk_user_id,
        system_prompt=system_prompt,
        name="banking_agent",
    )
