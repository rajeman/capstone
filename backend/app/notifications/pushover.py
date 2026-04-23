"""Pushover (https://pushover.net/) notifications for wallet events."""

import asyncio
import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import httpx

from app.config import settings
from app.db import get_mongo_client

logger = logging.getLogger(__name__)

# Same collection as Beanie `User.Settings.name` in `app.repositories.repository`.
_USERS_COLLECTION = "users"

PUSHOVER_MESSAGES_URL = "https://api.pushover.net/1/messages.json"


def _format_usd(amount_usd_cents: int) -> str:
    d = (Decimal(amount_usd_cents) / Decimal(100)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return format(d, "f")


def _str_field(obj: Any, key: str) -> str:
    if isinstance(obj, dict):
        v = obj.get(key)
    else:
        v = getattr(obj, key, None)
    if v is None:
        return ""
    return str(v).strip()


def _party_label(user: object | None, clerk_fallback: str) -> str:
    """Human-readable counterparty for Pushover copy; prefers Clerk first/last over username."""
    if user is None:
        return clerk_fallback
    first = _str_field(user, "first_name")
    last = _str_field(user, "last_name")
    from_given = " ".join(p for p in (first, last) if p)
    if from_given:
        return from_given
    name = _str_field(user, "name")
    if name:
        return name
    email = _str_field(user, "email")
    if email:
        return email
    username = _str_field(user, "username")
    if username:
        return username
    return clerk_fallback


async def _post_message(*, user_key: str, message: str) -> None:
    token = settings.pushover_application_token.strip()
    if not token:
        return
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            PUSHOVER_MESSAGES_URL,
            data={
                "token": token,
                "user": user_key.strip(),
                "message": message,
            },
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != 1:
            logger.warning("Pushover API returned non-success: %s", payload)


async def notify_wallet_transfer_pushover(
    *,
    sender_clerk_user_id: str,
    receiver_clerk_user_id: str,
    amount_usd_cents: int,
) -> None:
    """Notify sender and receiver via Pushover after a successful transfer (best-effort)."""
    if not settings.pushover_application_token.strip():
        logger.debug("Pushover disabled: pushover_application_token is empty")
        return

    client = get_mongo_client()
    database = client.get_default_database()
    if database is None:
        logger.warning("Pushover: no default database on Mongo client; skipping notifications")
        return

    users_coll = database[_USERS_COLLECTION]
    sender_doc = await users_coll.find_one({"clerk_user_id": sender_clerk_user_id})
    receiver_doc = await users_coll.find_one({"clerk_user_id": receiver_clerk_user_id})

    sender_key = _str_field(sender_doc, "pushover_user")
    receiver_key = _str_field(receiver_doc, "pushover_user")

    if not sender_key and not receiver_key:
        logger.debug(
            "Pushover: no user keys configured for sender=%s receiver=%s",
            sender_clerk_user_id,
            receiver_clerk_user_id,
        )
        return

    amt = _format_usd(amount_usd_cents)
    receiver_label = _party_label(receiver_doc, receiver_clerk_user_id)
    sender_label = _party_label(sender_doc, sender_clerk_user_id)

    tasks: list[asyncio.Task[object]] = []
    if sender_key:
        msg = f"You have sent {amt} USD to {receiver_label}."
        tasks.append(asyncio.create_task(_post_message(user_key=sender_key, message=msg)))
    if receiver_key:
        msg = f"You have received {amt} USD from {sender_label}."
        tasks.append(asyncio.create_task(_post_message(user_key=receiver_key, message=msg)))

    if not tasks:
        return
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, BaseException):
            logger.exception("Pushover send failed: %s", r)


def schedule_wallet_transfer_pushover_notifications(
    *,
    sender_clerk_user_id: str,
    receiver_clerk_user_id: str,
    amount_usd_cents: int,
) -> None:
    """Schedule Pushover sends in the background; never blocks or fails the money transfer."""

    async def _run() -> None:
        try:
            await notify_wallet_transfer_pushover(
                sender_clerk_user_id=sender_clerk_user_id,
                receiver_clerk_user_id=receiver_clerk_user_id,
                amount_usd_cents=amount_usd_cents,
            )
        except Exception:
            logger.exception("Background Pushover wallet transfer notifications failed")

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("No running event loop; skipping Pushover notifications for transfer")
        return
    loop.create_task(_run())
