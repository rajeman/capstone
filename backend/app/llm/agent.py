from agents import Agent

from app.llm.financial_prompt import FINANCIAL_SYSTEM_PROMPT
from app.tools.banking import get_balance, get_transactions, send_money
from app.tools.datetime_info import get_current_datetime
from app.tools.user_info import get_user_info_by_clerk_id, search_users_by_name

# OpenAI API model id for the GPT-4 class "mini" model.
GPT_4_MINI_MODEL = "gpt-4o-mini"

_CAPSTONE_TOOLS = [
    send_money,
    get_balance,
    get_transactions,
    get_user_info_by_clerk_id,
    search_users_by_name,
    get_current_datetime,
]


def build_capstone_instructions(*, clerk_user_id: str, system_prompt: str | None) -> str:
    base = (system_prompt or "").strip() or FINANCIAL_SYSTEM_PROMPT
    return (
        f"{base}\n\n"
        f"Authenticated clerk_user_id (Clerk `sub` — use as clerk_user_id / from_clerk_user_id where required): {clerk_user_id}\n"
        "Never ask the user for Clerk user id, `sub`, or other technical ids — only use the id above for themselves and search tool rows for others."
    )


def create_capstone_agent(
    *,
    clerk_user_id: str,
    system_prompt: str | None,
    name: str = "capstone_agent",
) -> Agent:
    """Main app agent: profile, directory search, transfers, balance, and time tools."""
    return Agent(
        name=name,
        instructions=build_capstone_instructions(
            clerk_user_id=clerk_user_id, system_prompt=system_prompt
        ),
        model=GPT_4_MINI_MODEL,
        tools=list(_CAPSTONE_TOOLS),
    )
