from pymongo import AsyncMongoClient
from pymongo.errors import DuplicateKeyError

from beanie import Document, Indexed


class DuplicateEmailError(Exception):
    pass


class User(Document):
    email: Indexed(str, unique=True)
    name: str

    class Settings:
        name = "users"


class UserRepository:
    def __init__(self, client: AsyncMongoClient) -> None:
        self._client = client

    async def create_user(self, email: str, name: str) -> str:
        user = User(email=email, name=name)
        try:
            await user.insert()
        except DuplicateKeyError:
            raise DuplicateEmailError from None
        return str(user.id)
