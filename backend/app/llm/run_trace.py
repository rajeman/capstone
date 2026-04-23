"""Turn agent run items into short, non-technical steps for the chat UI."""

from __future__ import annotations

from typing import Any

from agents.items import MessageOutputItem, RunItem, ToolCallItem

# SDK tool names → one line a customer might understand (no jargon, no payloads).
_FRIENDLY_TOOL_LABEL: dict[str, str] = {
    "sendMoney": "Handled your transfer",
    "getBalance": "Checked your balance",
    "getTransactions": "Looked up your recent activity",
    "get_user_info_by_clerk_id": "Looked up your profile on file",
    "searchUsersByName": "Searched for the person you mentioned",
    "getCurrentDateTime": "Confirmed today's date and time",
}


def _tool_name_from_raw(raw: Any) -> str | None:
    if isinstance(raw, dict):
        n = raw.get("name")
        return n if isinstance(n, str) else None
    n = getattr(raw, "name", None)
    return n if isinstance(n, str) else None


def user_facing_trace_steps(new_items: list[RunItem]) -> list[dict[str, str | None]]:
    """
    Ordered milestones for the side panel: only plain-language labels, no arguments or raw results.
    """
    steps: list[dict[str, str | None]] = []

    for item in new_items:
        if isinstance(item, ToolCallItem):
            name = _tool_name_from_raw(item.raw_item)
            label = _FRIENDLY_TOOL_LABEL.get(name or "", "Took care of something for your request")
            steps.append({"id": f"m-{len(steps)}", "label": label, "detail": None})
        elif isinstance(item, MessageOutputItem):
            continue

    if not steps:
        steps.append(
            {
                "id": "conversation",
                "label": "Put together a reply from our chat",
                "detail": None,
            },
        )
    return steps


def reasoning_steps_from_new_items(new_items: list[RunItem]) -> list[dict[str, str | None]]:
    """Alias for :func:`user_facing_trace_steps` (same user-facing output)."""
    return user_facing_trace_steps(new_items)
