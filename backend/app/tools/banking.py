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


def build_evaluate_send_money_instruction_tool(*, auth_clerk_user_id: str):
    """
    Pre-flight check for a transfer from the signed-in user's wallet only (same rules as sendMoney).
    """
    auth_id = auth_clerk_user_id.strip()

    @function_tool(name_override="evaluateSendMoneyInstruction")
    async def evaluate_send_money_instruction(
        session_clerk_user_id: Annotated[
            str,
            Field(
                description=(
                    "Must be the exact clerk_user_id from getAuthenticatedClerkUserId — call that tool first, "
                    "then pass the returned string here so the transfer is validated against the real signed-in user."
                ),
            ),
        ],
        recipient_clerk_user_id: Annotated[
            str,
            Field(
                description=(
                    "Recipient Clerk id from searchUsersByName (same value you would pass to sendMoney). "
                    "Debits are always from the signed-in user's wallet only — another person's wallet cannot be used."
                ),
            ),
        ],
        amount: Annotated[
            str,
            Field(description="Transfer amount as a decimal string (USD), same as for sendMoney."),
        ],
        currency: Annotated[
            str, Field(description="ISO 4217 currency code; must be USD (same as for sendMoney).")
        ],
    ) -> str:
        """Evaluate whether a send-money request is allowed before calling sendMoney (own wallet only)."""
        tool = "evaluateSendMoneyInstruction"

        if not auth_id:
            return json.dumps(
                {
                    "allowed": False,
                    "code": "no_session",
                    "message_for_user": (
                        "We could not verify your session, so transfers are not available right now. "
                        "Please sign in again and try once more."
                    ),
                    "tool": tool,
                }
            )

        if session_clerk_user_id.strip() != auth_id:
            return json.dumps(
                {
                    "allowed": False,
                    "code": "session_verification_failed",
                    "message_for_user": (
                        "We could not match this transfer to your signed-in account. "
                        "Please call getAuthenticatedClerkUserId and use that exact id as session_clerk_user_id, then try again."
                    ),
                    "tool": tool,
                }
            )

        recipient = recipient_clerk_user_id.strip()
        if not recipient:
            return json.dumps(
                {
                    "allowed": False,
                    "code": "missing_recipient",
                    "message_for_user": "I need a clear recipient before we can send money. Try searching by name first.",
                    "tool": tool,
                }
            )
        if recipient == auth_id:
            return json.dumps(
                {
                    "allowed": False,
                    "code": "self_transfer",
                    "message_for_user": "Transfers have to go to someone other than yourself. Pick a recipient from your contacts search.",
                    "tool": tool,
                }
            )

        try:
            amount_usd_cents = _parse_transfer_amount_usd_cents(amount)
        except ValueError as e:
            return json.dumps(
                {
                    "allowed": False,
                    "code": "invalid_amount",
                    "message_for_user": str(e),
                    "tool": tool,
                }
            )

        cur = currency.strip().upper()
        if cur != "USD":
            return json.dumps(
                {
                    "allowed": False,
                    "code": "unsupported_currency",
                    "message_for_user": "Only US dollar transfers are supported here. Please choose USD.",
                    "tool": tool,
                }
            )

        if amount_usd_cents > MAX_WALLET_TRANSFER_PER_TRANSACTION_USD_CENTS:
            max_usd = MAX_WALLET_TRANSFER_PER_TRANSACTION_USD_CENTS // 100
            return json.dumps(
                {
                    "allowed": False,
                    "code": "amount_over_limit",
                    "message_for_user": (
                        f"Each transfer can be at most {max_usd} USD. "
                        "You can send a smaller amount or split it into more than one transfer."
                    ),
                    "tool": tool,
                }
            )

        repo = UserRepository(get_mongo_client())
        recv_wallet = await repo.get_wallet_by_clerk_id(recipient)
        if recv_wallet is None:
            return json.dumps(
                {
                    "allowed": False,
                    "code": "recipient_no_wallet",
                    "message_for_user": (
                        "That recipient does not have an active wallet in Smart Pay yet, "
                        "so we cannot complete a transfer to them."
                    ),
                    "tool": tool,
                }
            )

        return json.dumps(
            {
                "allowed": True,
                "code": "ok",
                "message_for_user": (
                    "This transfer looks fine to send from your own wallet. "
                    "You can go ahead and complete it with sendMoney using the same recipient, amount, and currency."
                ),
                "tool": tool,
            }
        )

    return evaluate_send_money_instruction


def build_send_money_tool(*, auth_clerk_user_id: str):
    """
    sendMoney bound to the signed-in user: debits only their wallet (sender id is not model-supplied).
    """
    sender_id = auth_clerk_user_id.strip()

    @function_tool(name_override="sendMoney")
    async def send_money_from_my_account(
        to_clerk_user_id: Annotated[
            str,
            Field(
                description=(
                    "Recipient only: clerk_user_id from searchUsersByName after the user picks someone "
                    "by name or email — never ask the user for an id. You cannot send from anyone else's account."
                ),
            ),
        ],
        amount: Annotated[
            str,
            Field(
                description=(
                    "Transfer amount as a decimal string (USD), from the signed-in user's wallet. "
                    f"Maximum {MAX_WALLET_TRANSFER_PER_TRANSACTION_USD_CENTS // 100} USD per transfer; split larger amounts."
                )
            ),
        ],
        currency: Annotated[
            str, Field(description="ISO 4217 currency code; must be USD for wallet transfers.")
        ],
    ) -> str:
        """Send money from the signed-in user's wallet to another user (USD). Recipient id comes from search results only."""
        if not sender_id:
            return json.dumps(
                {
                    "ok": False,
                    "detail": "Cannot send money: session is missing a valid authenticated user id.",
                    "tool": "sendMoney",
                }
            )

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
                sender_id,
                to_clerk_user_id,
                amount_usd_cents,
                allowed_debit_clerk_user_id=sender_id,
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

    return send_money_from_my_account


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
