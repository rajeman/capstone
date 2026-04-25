"""Pull chart payloads from agent run items (transaction analytics tool output)."""

from __future__ import annotations

import json
import re
from typing import Any

from agents.items import RunItem, ToolCallItem, ToolCallOutputItem
from agents.tool import ToolOutputText

_ANALYTICS_TOOL = "buildTransactionHistoryAnalytics"


def _tool_name_from_raw(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        n = raw.get("name")
        return n if isinstance(n, str) else None
    n = getattr(raw, "name", None)
    return n if isinstance(n, str) else None


def _call_id_from_raw(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        cid = raw.get("call_id") or raw.get("id")
        return cid if isinstance(cid, str) else None
    cid = getattr(raw, "call_id", None) or getattr(raw, "id", None)
    return cid if isinstance(cid, str) else None


def _call_id_to_tool_name(new_items: list[RunItem]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in new_items:
        if not isinstance(item, ToolCallItem):
            continue
        name = _tool_name_from_raw(item.raw_item)
        cid = _call_id_from_raw(item.raw_item)
        if name and cid:
            out[cid] = name
    return out


def _coerce_tool_output_to_str(output: Any) -> str | None:
    if output is None:
        return None
    if isinstance(output, str):
        return output
    if isinstance(output, ToolOutputText):
        return output.text
    text = getattr(output, "text", None)
    if isinstance(text, str):
        return text
    if isinstance(output, dict) and isinstance(output.get("text"), str):
        return output["text"]
    try:
        return json.dumps(output, default=str)
    except TypeError:
        return str(output)


def _parse_charts_json_blob(blob: str) -> list[dict[str, Any]]:
    s = blob.strip()
    if not s:
        return []
    m = re.match(r"^```(?:json)?\s*\n?(.*)\n?```\s*$", s, flags=re.DOTALL | re.IGNORECASE)
    if m:
        s = m.group(1).strip()
    try:
        data = json.loads(s)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    charts = data.get("charts")
    if not isinstance(charts, list):
        return []
    return [c for c in charts if isinstance(c, dict)]


def extract_transaction_charts_from_run_items(new_items: list[RunItem]) -> list[dict[str, Any]]:
    """
    Return chart objects from the latest successful `buildTransactionHistoryAnalytics` tool output.
    """
    call_names = _call_id_to_tool_name(new_items)
    found: list[dict[str, Any]] = []
    for item in new_items:
        if not isinstance(item, ToolCallOutputItem):
            continue

        name = _tool_name_from_raw(item.raw_item)
        if not name:
            cid = _call_id_from_raw(item.raw_item)
            if cid:
                name = call_names.get(cid)
        if name != _ANALYTICS_TOOL:
            continue

        raw_str = _coerce_tool_output_to_str(getattr(item, "output", None))
        if not raw_str:
            continue
        charts = _parse_charts_json_blob(raw_str)
        if charts:
            found = charts
    return found
