from typing import Annotated

from beanie import Indexed
from pymongo import AsyncMongoClient
from pymongo.errors import DuplicateKeyError

from app.models.timestamped import TimestampedDocument


class DuplicateEmailError(Exception):
    pass


# 1000 USD in cents (integer).
INITIAL_WALLET_BALANCE_USD_CENTS = 1000 * 100


class User(TimestampedDocument):
    email: Indexed(str, unique=True)
    name: str
    # Clerk `sub`; unique when set (sparse so non-Clerk users can have null).
    clerk_user_id: Annotated[str | None, Indexed(unique=True, sparse=True)] = None
    first_name: str | None = None
    last_name: str | None = None
    image_url: str | None = None
    username: str | None = None
    phone_number: str | None = None

    class Settings:
        name = "users"


class Wallet(TimestampedDocument):
    clerk_user_id: Annotated[str, Indexed(unique=True)]
    balance: int

    class Settings:
        name = "wallets"


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

    async def get_user_by_clerk_id(self, clerk_user_id: str) -> User | None:
        return await User.find_one(User.clerk_user_id == clerk_user_id)

    def _update_from_clerk_profile(self, user: User, profile: dict) -> None:
        """Apply only fields Clerk provided (non-None). Never change email or Mongo id."""
        p = profile
        touched = False
        if p["first_name"] is not None:
            user.first_name = p["first_name"]
            touched = True
        if p["last_name"] is not None:
            user.last_name = p["last_name"]
            touched = True
        if p["username"] is not None:
            user.username = p["username"]
            touched = True
        if p["image_url"] is not None:
            user.image_url = p["image_url"]
            touched = True
        if p["phone_number"] is not None:
            user.phone_number = p["phone_number"]
            touched = True
        if touched:
            user.name = self._display_name(
                user.first_name,
                user.last_name,
                user.username,
                user.email,
            )

    async def sync_user_from_clerk(self, payload: dict) -> tuple[str, bool]:
        """Lookup by Clerk id only. Insert all profile fields if new; otherwise merge provided fields."""
        sub = payload["sub"]
        profile = self._claims_to_profile(payload)

        user = await User.find_one(User.clerk_user_id == sub)
        if user:
            self._update_from_clerk_profile(user, profile)
            try:
                await user.save()
            except DuplicateKeyError:
                raise DuplicateEmailError from None
            return str(user.id), False

        user = User(
            clerk_user_id=sub,
            email=profile["email"],
            name=self._display_name(
                profile["first_name"],
                profile["last_name"],
                profile["username"],
                profile["email"],
            ),
            first_name=profile["first_name"],
            last_name=profile["last_name"],
            username=profile["username"],
            image_url=profile["image_url"],
            phone_number=profile["phone_number"],
        )
        try:
            await user.insert()
        except DuplicateKeyError:
            raise DuplicateEmailError from None
        await Wallet(
            clerk_user_id=sub,
            balance=INITIAL_WALLET_BALANCE_USD_CENTS,
        ).insert()
        return str(user.id), True
