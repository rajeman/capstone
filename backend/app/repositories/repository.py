from pymongo import AsyncMongoClient
from pymongo.errors import DuplicateKeyError

from beanie import Indexed

from app.models.timestamped import TimestampedDocument


class DuplicateEmailError(Exception):
    pass


class User(TimestampedDocument):
    email: Indexed(str, unique=True)
    name: str
    clerk_user_id: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    image_url: str | None = None
    username: str | None = None
    phone_number: str | None = None

    class Settings:
        name = "users"


class UserRepository:
    def __init__(self, client: AsyncMongoClient) -> None:
        self._client = client

    @staticmethod
    def _display_name(first, last, username, email) -> str:
        if first or last:
            return " ".join(filter(None, [first, last]))
        return username or email.split("@")[0] or "User"

    @staticmethod
    def _claims_to_profile(payload: dict) -> dict:
        email = payload["email"].strip().lower()

        first = payload.get("first_name") or payload.get("given_name")
        last = payload.get("last_name") or payload.get("family_name")

        return {
            "email": email,
            "first_name": first.strip() if first else None,
            "last_name": last.strip() if last else None,
            "username": (payload.get("username") or "").strip() or None,
            "image_url": (payload.get("image_url") or payload.get("picture") or "").strip() or None,
            "phone_number": (payload.get("phone_number") or "").strip() or None,
        }

    async def create_user(self, email: str, name: str) -> str:
        try:
            user = await User(email=email, name=name).insert()
            return str(user.id)
        except DuplicateKeyError:
            raise DuplicateEmailError from None

    async def sync_user_from_clerk(self, payload: dict) -> tuple[str, bool]:
        sub = payload["sub"]
        profile = self._claims_to_profile(payload)

        user = await User.find_one(
            (User.clerk_user_id == sub) | (User.email == profile["email"])
        )

        if user:
            is_new = False
        else:
            user = User(**profile)
            is_new = True

        user.clerk_user_id = sub
        user.name = self._display_name(
            profile["first_name"],
            profile["last_name"],
            profile["username"],
            profile["email"],
        )
        user.first_name = profile["first_name"]
        user.last_name = profile["last_name"]
        user.username = profile["username"]
        user.image_url = profile["image_url"]
        user.phone_number = profile["phone_number"]
        user.email = profile["email"]

        try:
            if is_new:
                await user.insert()
            else:
                await user.save()
        except DuplicateKeyError:
            raise DuplicateEmailError from None

        return str(user.id), is_new
