import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Annotated

from agents import function_tool
from pydantic import Field

from app.db import get_mongo_client
from app.repositories.repository import (
    MAX_WALLET_TRANSFER_PER_TRANSACTION_USD_CENTS,
    Transaction,
    User,
    UserRepository,
    Wallet,
)
from app.tools.schemas import UserInfoByClerkIdNotFound, user_to_found_response


def _sender_receiver_clerk_ids(doc: dict) -> tuple[str | None, str | None]:
    sender_id = doc.get("sender_clerk_user_id")
    receiver_id = doc.get("receiver_clerk_user_id")
    if sender_id is not None and receiver_id is not None:
        return sender_id, receiver_id
    cp = doc.get("counterparty_clerk_user_id")
    cid = doc.get("clerk_user_id")
    if cp is not None and cid is not None:
        if doc.get("side") == "debit":
            return cid, cp
        return cp, cid
    return sender_id, receiver_id


def _user_embed(clerk_id: str | None, by_clerk: dict[str, User]) -> dict:
    if not clerk_id:
        return {"found": False, "clerk_user_id": None, "detail": "Missing clerk user id on transaction."}
    user = by_clerk.get(clerk_id)
    if user is None:
        return UserInfoByClerkIdNotFound(clerk_user_id=clerk_id).model_dump()
    return user_to_found_response(user).model_dump()


async def fetch_serialized_transactions_for_clerk(
    clerk_user_id: str,
    limit: int,
) -> tuple[Wallet | None, list[dict], str | None]:
    """
    Load recent wallet transactions with embedded counterparty users (same rows as getTransactions).

    Returns ``(wallet, serialized_rows, error)`` where ``error`` is ``"no_wallet"``, ``"no_database"``,
    or ``None`` on success.
    """
    cap = max(1, min(limit, 200))

    client = get_mongo_client()
    repo = UserRepository(client)
    wallet = await repo.get_wallet_by_clerk_id(clerk_user_id)
    if wallet is None:
        return None, [], "no_wallet"

    db = client.get_default_database()
    if db is None:
        return wallet, [], "no_database"

    coll = db[Transaction.Settings.name]
    cursor = coll.find({"clerk_user_id": clerk_user_id}).sort("created_at", -1).limit(cap)
    rows = await cursor.to_list(length=cap)

    party_ids: set[str] = set()
    resolved_rows: list[tuple[dict, str | None, str | None]] = []
    for doc in rows:
        sender_id, receiver_id = _sender_receiver_clerk_ids(doc)
        resolved_rows.append((doc, sender_id, receiver_id))
        if sender_id:
            party_ids.add(sender_id)
        if receiver_id:
            party_ids.add(receiver_id)

    users_by_clerk: dict[str, User] = {}
    if party_ids:
        users = await User.find({"clerk_user_id": {"$in": list(party_ids)}}).to_list()
        users_by_clerk = {u.clerk_user_id: u for u in users if u.clerk_user_id}

    serialized: list[dict] = []
    for doc, sender_id, receiver_id in resolved_rows:
        ca, ua = doc.get("created_at"), doc.get("updated_at")
        serialized.append(
            {
                "id": str(doc["_id"]),
                "clerk_user_id": doc["clerk_user_id"],
                "sender_clerk_user_id": sender_id,
                "receiver_clerk_user_id": receiver_id,
                "amount_usd_cents": doc["amount_usd_cents"],
                "side": doc["side"],
                "kind": doc.get("kind", "wallet_transfer"),
                "created_at": ca.isoformat() if ca else None,
                "updated_at": ua.isoformat() if ua else None,
                "sender_user": _user_embed(sender_id, users_by_clerk),
                "receiver_user": _user_embed(receiver_id, users_by_clerk),
            }
        )
    return wallet, serialized, None


def _parse_transfer_amount_usd_cents(amount: str) -> int:
    try:
        d = Decimal(amount.strip())
    except InvalidOperation as e:
        raise ValueError(
            "Invalid amount. Provide a positive decimal number (for example, 10.50)."
        ) from e
    if d <= 0:
        raise ValueError("Amount must be greater than zero.")
    cents = (d * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if cents <= 0:
        raise ValueError("Amount must be at least one cent.")
    return int(cents)


@function_tool(name_override="sendMoney")
async def send_money(
    from_clerk_user_id: Annotated[
        str,
        Field(
            description=(
                "Sender: use the authenticated user's Clerk id from system instructions — never ask the user."
            ),
        ),
    ],
    to_clerk_user_id: Annotated[
        str,
        Field(
            description=(
                "Recipient: use the clerk_user_id from the searchUsersByName result row after the user "
                "picks someone by name or email — never ask the user for an id."
            ),
        ),
    ],
    amount: Annotated[
        str,
        Field(
            description=(
                "Transfer amount as a decimal string (USD). "
                f"Maximum {MAX_WALLET_TRANSFER_PER_TRANSACTION_USD_CENTS // 100} USD per transfer; split larger amounts."
            )
        ),
    ],
    currency: Annotated[str, Field(description="ISO 4217 currency code; must be USD for wallet transfers.")],
) -> str:
    """Transfer funds between wallets (USD, integer cents). Fill Clerk ids from instructions and search results — never ask the user for them."""
    try:
        amount_usd_cents = _parse_transfer_amount_usd_cents(amount)
    except ValueError as e:
        return json.dumps({"ok": False, "detail": str(e), "tool": "sendMoney"})

    cur = currency.strip().upper()
    if cur != "USD":
        return json.dumps(
            {
                "ok": False,
                "detail": f"Only USD wallet transfers are supported; got currency {currency!r}.",
                "tool": "sendMoney",
            }
        )

    if amount_usd_cents > MAX_WALLET_TRANSFER_PER_TRANSACTION_USD_CENTS:
        max_usd = MAX_WALLET_TRANSFER_PER_TRANSACTION_USD_CENTS // 100
        return json.dumps(
            {
                "ok": False,
                "detail": (
                    f"A single transfer cannot exceed {max_usd} USD. "
                    "Split larger amounts into multiple transfers or reduce the amount."
                ),
                "attempted_amount_usd_cents": amount_usd_cents,
                "max_amount_usd_cents": MAX_WALLET_TRANSFER_PER_TRANSACTION_USD_CENTS,
                "tool": "sendMoney",
            }
        )

    repo = UserRepository(get_mongo_client())
    try:
        result = await repo.send_money_between_clerk_users(
            from_clerk_user_id,
            to_clerk_user_id,
            amount_usd_cents,
        )
    except ValueError as e:
        return json.dumps(
            {
                "ok": False,
                "detail": str(e),
                "tool": "sendMoney",
            }
        )
    except Exception as e:
        return json.dumps(
            {
                "ok": False,
                "detail": f"Transfer failed unexpectedly: {type(e).__name__}: {e}",
                "tool": "sendMoney",
            }
        )
    if not result.ok:
        err: dict = {
            "ok": False,
            "detail": result.detail,
            "tool": "sendMoney",
        }
        if result.amount_usd_cents is not None:
            err["attempted_amount_usd_cents"] = result.amount_usd_cents
        if result.sender_balance_usd_cents is not None:
            err["sender_balance_usd_cents"] = result.sender_balance_usd_cents
        return json.dumps(err)
    return json.dumps(
        {
            "ok": True,
            "from_clerk_user_id": result.from_clerk_user_id,
            "to_clerk_user_id": result.to_clerk_user_id,
            "amount_usd_cents": result.amount_usd_cents,
            "sender_balance_usd_cents_after": result.sender_balance_usd_cents_after,
            "currency": "USD",
            "tool": "sendMoney",
        }
    )


@function_tool(name_override="getBalance")
async def get_balance(
    clerk_user_id: Annotated[
        str,
        Field(
            description="The signed-in user's Clerk id from system instructions — never ask the user.",
        ),
    ],
) -> str:
    """Return the user's wallet balance from the wallets collection (USD, integer cents)."""
    repo = UserRepository(get_mongo_client())
    wallet = await repo.get_wallet_by_clerk_id(clerk_user_id)
    if wallet is None:
        return json.dumps(
            {
                "found": False,
                "clerk_user_id": clerk_user_id,
                "detail": "No wallet found for this Clerk user id.",
            }
        )
    return json.dumps(
        {
            "found": True,
            "clerk_user_id": clerk_user_id,
            "balance_usd_cents": wallet.balance,
            "currency": "USD",
        }
    )


@function_tool(name_override="getTransactions")
async def get_transactions(
    clerk_user_id: Annotated[
        str,
        Field(
            description="The signed-in user's Clerk id from system instructions — never ask the user.",
        ),
    ],
    limit: Annotated[
        int | None,
        Field(description="Optional maximum number of transactions to return."),
    ] = None,
) -> str:
    """List recent wallet ledger rows for the user from the transactions collection."""
    cap = limit if limit is not None else 50
    cap = max(1, min(cap, 200))

    wallet, serialized, err = await fetch_serialized_transactions_for_clerk(clerk_user_id, cap)
    if err == "no_wallet":
        return json.dumps(
            {
                "found": False,
                "clerk_user_id": clerk_user_id,
                "detail": "No wallet found for this Clerk user id.",
                "tool": "getTransactions",
            }
        )
    if err == "no_database":
        return json.dumps(
            {
                "found": False,
                "clerk_user_id": clerk_user_id,
                "detail": "Database URI must include a default database name.",
                "tool": "getTransactions",
            }
        )
    return json.dumps(
        {
            "found": True,
            "clerk_user_id": clerk_user_id,
            "currency": "USD",
            "limit": cap,
            "transactions": serialized,
            "tool": "getTransactions",
        }
    )
