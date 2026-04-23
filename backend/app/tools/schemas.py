from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.repositories.repository import User

CLERK_USER_ID_FIELD_DESCRIPTION = (
    "Clerk `sub` for tools only: use the id injected in system instructions for the signed-in user, "
    "or the match record from searchUsersByName for a payee. Never ask the user for this value."
)


class GetUserInfoByClerkIdParams(BaseModel):
    """Validated input for looking up a user by Clerk id."""

    clerk_user_id: str = Field(description=CLERK_USER_ID_FIELD_DESCRIPTION)


class UserInfoByClerkIdFound(BaseModel):
    """User profile returned when a record exists for the given Clerk id."""

    found: Literal[True] = True
    id: str
    email: str
    name: str
    clerk_user_id: str | None
    first_name: str | None
    last_name: str | None
    username: str | None
    phone_number: str | None
    image_url: str | None
    created_at: str | None
    updated_at: str | None


class UserInfoByClerkIdNotFound(BaseModel):
    """Response when no user exists for the Clerk id."""

    found: Literal[False] = False
    clerk_user_id: str


class UserNameSearchMatch(BaseModel):
    """One row returned from name search (enough to disambiguate payees)."""

    id: str
    clerk_user_id: str | None
    name: str
    email: str
    first_name: str | None
    last_name: str | None
    username: str | None


def user_to_found_response(user: User) -> UserInfoByClerkIdFound:
    return UserInfoByClerkIdFound(
        id=str(user.id),
        email=user.email,
        name=user.name,
        clerk_user_id=user.clerk_user_id,
        first_name=user.first_name,
        last_name=user.last_name,
        username=user.username,
        phone_number=user.phone_number,
        image_url=user.image_url,
        created_at=user.created_at.isoformat() if user.created_at else None,
        updated_at=user.updated_at.isoformat() if user.updated_at else None,
    )


def user_to_name_search_match(user: User) -> UserNameSearchMatch:
    return UserNameSearchMatch(
        id=str(user.id),
        clerk_user_id=user.clerk_user_id,
        name=user.name,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        username=user.username,
    )
