"""Session-bound tools (no model-supplied user id for authentication)."""

import json

from agents import function_tool


def build_get_authenticated_clerk_user_id_tool(*, auth_clerk_user_id: str):
    """Returns the Clerk `sub` for the current session — use when validating transfers."""
    auth = auth_clerk_user_id.strip()

    @function_tool(name_override="getAuthenticatedClerkUserId")
    async def get_authenticated_clerk_user_id() -> str:
        """Return the Clerk user id for the signed-in user. Call before evaluateSendMoneyInstruction when validating a transfer."""
        if not auth:
            return json.dumps(
                {
                    "ok": False,
                    "clerk_user_id": None,
                    "detail": "No authenticated Clerk user id in this session.",
                    "tool": "getAuthenticatedClerkUserId",
                }
            )
        return json.dumps(
            {
                "ok": True,
                "clerk_user_id": auth,
                "detail": "Use this exact clerk_user_id as session_clerk_user_id when calling evaluateSendMoneyInstruction.",
                "tool": "getAuthenticatedClerkUserId",
            }
        )

    return get_authenticated_clerk_user_id
