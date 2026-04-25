"""
Transaction history chart specialist, exposed to the main banking agent via Agent.as_tool().

Inspired by the Charter pattern: deterministic aggregates first, then a focused model pass that
emits strict JSON (metrics + Recharts-friendly chart definitions).
"""

from __future__ import annotations

from typing import Any

from agents import Agent
from agents.agent_tool_input import StructuredToolInputBuilderOptions
from agents.result import RunResult
from pydantic import BaseModel, Field

from app.analytics.transaction_stats import compute_transaction_history_stats
from app.tools.banking import fetch_serialized_transactions_for_clerk
from app.tools.chart import (
    SMART_PAY_TRANSACTION_CHART_AGENT_INSTRUCTIONS,
    format_transaction_chart_analyst_task,
)

# Keep in sync with app.llm.agent (avoid import cycle).
_GPT_4_MINI = "gpt-4o-mini"


class TransactionAnalyticsToolParams(BaseModel):
    """Structured arguments for the nested analytics agent (main model fills these)."""

    user_question: str = Field(
        ...,
        description=(
            "What the user wants to see or understand (spending trends, running balance, weekly "
            "totals, who they paid most, pie breakdown with Others, etc.)."
        ),
    )
    transaction_limit: int | None = Field(
        None,
        description="Optional cap on how many recent transactions to load (10–200). Default 100.",
        ge=10,
        le=200,
    )


async def _nested_output_extractor(result: RunResult) -> str:
    out = result.final_output
    text = out if isinstance(out, str) else (str(out) if out is not None else "")
    return text.strip()


def build_transaction_history_analytics_tool(*, clerk_user_id: str) -> Any:
    """
    Specialist agent wrapped as a single tool for the capstone banking agent.

    Fetches transactions for `clerk_user_id` inside the tool input builder (not model-supplied),
    so the model cannot target another user's ledger.
    """
    chart_agent = Agent(
        name="transaction_chart_specialist",
        instructions=SMART_PAY_TRANSACTION_CHART_AGENT_INSTRUCTIONS,
        model=_GPT_4_MINI,
        tools=[],
    )

    async def input_builder(options: StructuredToolInputBuilderOptions) -> str:
        params = options["params"]
        if isinstance(params, BaseModel):
            params = params.model_dump()

        limit = int(params.get("transaction_limit") or 100)
        limit = max(10, min(200, limit))
        user_question = (params.get("user_question") or "").strip() or "Overall spending and cash flow"

        wallet, rows, err = await fetch_serialized_transactions_for_clerk(clerk_user_id, limit)
        if err == "no_wallet":
            metrics = {"error": "no_wallet", "detail": "No wallet found for this user."}
            return format_transaction_chart_analyst_task(
                user_question=user_question,
                computed_metrics=metrics,
                recent_transactions_sample=[],
            )
        if err == "no_database":
            metrics = {"error": "no_database", "detail": "Database misconfiguration."}
            return format_transaction_chart_analyst_task(
                user_question=user_question,
                computed_metrics=metrics,
                recent_transactions_sample=[],
            )

        assert wallet is not None
        metrics = compute_transaction_history_stats(
            viewer_clerk_user_id=clerk_user_id,
            transactions=rows,
            current_balance_usd_cents=wallet.balance,
        )
        recent_sample = rows[:30]
        return format_transaction_chart_analyst_task(
            user_question=user_question,
            computed_metrics=metrics,
            recent_transactions_sample=recent_sample,
        )

    return chart_agent.as_tool(
        tool_name="buildTransactionHistoryAnalytics",
        tool_description=(
            "Build structured transaction analytics for the signed-in user: KPIs, daily/weekly/"
            "monthly spend and income with running balance (line charts), top beneficiaries as a "
            "bar chart, and beneficiary share as a pie chart with an **Others** slice for smaller "
            "recipients. Uses real ledger data for their account only. Call when the user asks for "
            "trends, charts, spending summaries, or who they paid or received from most. Arguments: "
            "user_question (required), optional transaction_limit (10–200, default 100)."
        ),
        parameters=TransactionAnalyticsToolParams,
        input_builder=input_builder,
        include_input_schema=True,
        max_turns=4,
        custom_output_extractor=_nested_output_extractor,
    )
