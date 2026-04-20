from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field, field_validator
from pymongo import AsyncMongoClient

from app.db import get_mongo_client
from app.repositories.repository import DuplicateEmailError, UserRepository

router = APIRouter(prefix="/users", tags=["users"])


class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1)

    @field_validator("email", mode="before")
    @classmethod
    def strip_and_lower_email(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v


def get_user_repository(
    client: AsyncMongoClient = Depends(get_mongo_client),
) -> UserRepository:
    return UserRepository(client)


@router.post("", status_code=201)
async def create_user(
    body: UserCreate,
    repo: UserRepository = Depends(get_user_repository),
):
    try:
        user_id = await repo.create_user(body.email, body.name)
    except DuplicateEmailError:
        raise HTTPException(
            status_code=409,
            detail="A user with this email already exists.",
        ) from None
    return {"id": user_id}
