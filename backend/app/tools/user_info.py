import json
from typing import Annotated

from agents import function_tool
from pydantic import Field

from app.db import get_mongo_client
from app.repositories.repository import UserRepository
from app.tools.schemas import (
    CLERK_USER_ID_FIELD_DESCRIPTION,
    GetUserInfoByClerkIdParams,
    UserInfoByClerkIdNotFound,
    user_to_found_response,
    user_to_name_search_match,
)


@function_tool
async def get_user_info_by_clerk_id(
    clerk_user_id: Annotated[str, Field(description=CLERK_USER_ID_FIELD_DESCRIPTION)],
) -> str:
    """Look up a user in the database; pass the signed-in user's id from instructions — never ask the user for it."""
    params = GetUserInfoByClerkIdParams(clerk_user_id=clerk_user_id)

    repo = UserRepository(get_mongo_client())
    user = await repo.get_user_by_clerk_id(params.clerk_user_id)
    if user is None:
        return UserInfoByClerkIdNotFound(clerk_user_id=params.clerk_user_id).model_dump_json()
    return user_to_found_response(user).model_dump_json()


@function_tool(name_override="searchUsersByName")
async def search_users_by_name(
    query: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "Optional substring matched against first name, last name, or display name "
                "(case-insensitive). Use alone for a broad search, or combine with first_name / last_name."
            ),
        ),
    ] = None,
    first_name: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "Optional substring that must appear in the user's stored first name "
                "(case-insensitive). Combined with last_name or query using AND."
            ),
        ),
    ] = None,
    last_name: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "Optional substring that must appear in the user's stored last name "
                "(case-insensitive). Combined with first_name or query using AND."
            ),
        ),
    ] = None,
) -> str:
    """Search directory users by name. One match: use it directly without confirmation questions. Several matches: ask who they meant using names or emails only — never ask for Clerk ids."""
    q = (query or "").strip() if query is not None else ""
    fn = (first_name or "").strip() if first_name is not None else ""
    ln = (last_name or "").strip() if last_name is not None else ""
    if not q and not fn and not ln:
        return json.dumps(
            {
                "ok": False,
                "detail": "Provide at least one of: query, first_name, or last_name (non-empty).",
                "tool": "searchUsersByName",
            }
        )

    repo = UserRepository(get_mongo_client())
    users = await repo.search_users_by_name(
        query=query,
        first_name=first_name,
        last_name=last_name,
        limit=25,
    )
    matches = [user_to_name_search_match(u).model_dump() for u in users]
    n = len(matches)

    payload: dict = {
        "ok": True,
        "match_count": n,
        "matches": matches,
        "tool": "searchUsersByName",
    }
    if n == 0:
        payload["detail"] = "No users matched those name criteria."
    elif n == 1:
        payload["requires_user_to_choose"] = False
        payload["hint"] = (
            "Exactly one clear match — proceed: use matches[0].clerk_user_id in follow-up tool calls "
            "(e.g. sendMoney to_clerk_user_id) without asking the user to confirm or pick someone. "
            "You may briefly state who was found; do not ask a clarifying question for this case."
        )
    else:
        payload["requires_user_to_choose"] = True
        payload["agent_instruction"] = (
            "Multiple people matched. List each option by full name, email, or username only. "
            "When the user clearly picks one, use that row's clerk_user_id only inside tool calls. "
            "Never ask for or display Clerk ids to the user."
        )
    return json.dumps(payload)
