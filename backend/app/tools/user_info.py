from typing import Annotated

from agents import function_tool
from pydantic import Field

from app.tools.schemas import (
    CLERK_USER_ID_FIELD_DESCRIPTION,
    GetUserInfoByClerkIdParams,
    UserInfoByClerkIdNotFound,
    user_to_found_response,
)


@function_tool
async def get_user_info_by_clerk_id(
    clerk_user_id: Annotated[str, Field(description=CLERK_USER_ID_FIELD_DESCRIPTION)],
) -> str:
    """Look up a user in the database by Clerk user id and return their profile as JSON."""
    params = GetUserInfoByClerkIdParams(clerk_user_id=clerk_user_id)

    from app.db import get_mongo_client
    from app.repositories.repository import UserRepository

    repo = UserRepository(get_mongo_client())
    user = await repo.get_user_by_clerk_id(params.clerk_user_id)
    if user is None:
        return UserInfoByClerkIdNotFound(clerk_user_id=params.clerk_user_id).model_dump_json()
    return user_to_found_response(user).model_dump_json()
