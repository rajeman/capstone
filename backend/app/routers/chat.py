import json
import re
from typing import Any, Literal

from agents import Runner
from agents.items import ItemHelpers
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.clerk_auth import get_clerk_session_payload
from app.llm.agent import create_capstone_agent
from app.llm.run_trace import user_facing_trace_steps
from app.routers.chart_extract import extract_transaction_charts_from_run_items

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    """Conversation turn: system prompt plus prior user/assistant messages (last message must be user)."""

    system_prompt: str | None = Field(
        default=None,
        description="Optional override; defaults to the server banking system prompt.",
    )
    messages: list[ChatMessageIn]


class ReasoningStepOut(BaseModel):
    id: str
    label: str
    detail: str | None = None


class ChatResponse(BaseModel):
    message: str
    reasoning_steps: list[ReasoningStepOut] = Field(default_factory=list)
    charts: list[Any] = Field(
        default_factory=list,
        description="Transaction analytics charts when the agent generates them.",
    )


def _strip_json_fence(text: str) -> str:
    """Unwrap ```json ... ``` whether it is the whole message or embedded in prose."""
    s = text.strip()
    m = re.match(r"^```(?:json)?\s*\n?(.*)\n?```\s*$", s, flags=re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m2 = re.search(r"```(?:json)?\s*\n(.*?)```", s, flags=re.DOTALL | re.IGNORECASE)
    if m2:
        return m2.group(1).strip()
    return s


def _extract_json_object(text: str) -> str | None:
    """Best-effort: pull the first top-level `{ ... }` when the model adds prose around JSON."""
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    quote: str | None = None
    for i, ch in enumerate(text[start:], start):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif quote and ch == quote:
                in_str = False
            continue
        if ch in ('"', "'"):
            in_str = True
            quote = ch
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _looks_like_agent_json(data: dict[str, Any]) -> bool:
    return "final_answer" in data or "steps" in data or "action" in data


def _loads_structured_json(text: str) -> dict[str, Any] | None:
    s = text.strip()
    fenced = _strip_json_fence(s)
    blobs: list[str] = []
    for part in (s, fenced):
        if part:
            blobs.append(part)
            extracted = _extract_json_object(part)
            if extracted:
                blobs.append(extracted)
    seen: set[str] = set()
    for blob in blobs:
        if not blob or blob in seen:
            continue
        seen.add(blob)
        try:
            data = json.loads(blob)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and _looks_like_agent_json(data):
            return data
    return None


def parse_structured_agent_output(
    text: str,
) -> tuple[str, list[ReasoningStepOut], list[dict[str, Any]]]:
    """Parse final JSON (steps/action/final_answer/optional charts) for chat + side panel."""
    data = _loads_structured_json(text)
    if data is None:
        return text, [], []

    steps_out: list[ReasoningStepOut] = []
    raw_steps = data.get("steps")
    if isinstance(raw_steps, list):
        for i, item in enumerate(raw_steps):
            if isinstance(item, str) and item.strip():
                steps_out.append(
                    ReasoningStepOut(id=f"step-{i}", label=item.strip(), detail=None)
                )

    # "action" is still required in JSON for the model’s bookkeeping; do not surface it in the UI.
    charts_out: list[dict[str, Any]] = []
    raw_charts = data.get("charts")
    if isinstance(raw_charts, list):
        for chart in raw_charts:
            if isinstance(chart, dict):
                charts_out.append(chart)

    final = data.get("final_answer")
    if isinstance(final, str) and final.strip():
        message = final.strip()
    else:
        message = text

    if not steps_out and isinstance(final, str) and final.strip():
        steps_out.append(
            ReasoningStepOut(
                id="implicit",
                label="Wrapped up your answer",
                detail=None,
            )
        )

    return message, steps_out, charts_out


@router.post("", response_model=ChatResponse)
async def chat_turn(request: Request, body: ChatRequest) -> ChatResponse:
    payload = await get_clerk_session_payload(request)
    clerk_user_id = payload.get("sub")
    if not clerk_user_id or not isinstance(clerk_user_id, str):
        raise HTTPException(status_code=401, detail="Missing subject in session")

    if not body.messages:
        raise HTTPException(status_code=400, detail="messages must not be empty")
    if body.messages[-1].role != "user":
        raise HTTPException(status_code=400, detail="Last message must be from the user")

    agent = create_capstone_agent(clerk_user_id=clerk_user_id, system_prompt=body.system_prompt)
    input_items = ItemHelpers.input_to_new_input_list(
        [{"role": m.role, "content": m.content} for m in body.messages],
    )
    result = await Runner.run(agent, input_items)
    out = result.final_output
    text = out if isinstance(out, str) else (str(out) if out is not None else "")
    message, reasoning_steps, charts_from_message = parse_structured_agent_output(text)
    if not reasoning_steps:
        trace_rows = user_facing_trace_steps(result.new_items)
        reasoning_steps = [
            ReasoningStepOut(id=row["id"], label=row["label"], detail=row.get("detail"))
            for row in trace_rows
        ]
    charts = extract_transaction_charts_from_run_items(result.new_items)
    if not charts and charts_from_message:
        charts = charts_from_message
    return ChatResponse(message=message, reasoning_steps=reasoning_steps, charts=charts)
