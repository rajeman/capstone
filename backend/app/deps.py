from fastapi import Depends
from pymongo import AsyncMongoClient

from app.db import get_mongo_client
from app.repositories.repository import UserRepository


def get_user_repository(
    client: AsyncMongoClient = Depends(get_mongo_client),
) -> UserRepository:
    return UserRepository(client)
