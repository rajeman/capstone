import logging
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated, Literal

from beanie import Indexed
from pymongo import AsyncMongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.models.timestamped import TimestampedDocument

logger = logging.getLogger(__name__)


def _insufficient_funds_detail(*, balance_usd_cents: int, attempted_usd_cents: int) -> str:
    bal_usd = (Decimal(balance_usd_cents) / Decimal(100)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    amt_usd = (Decimal(attempted_usd_cents) / Decimal(100)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return (
        f"Insufficient funds. Current balance is {balance_usd_cents} USD cents "
        f"({format(bal_usd, 'f')} USD); attempted transfer is {attempted_usd_cents} USD cents "
        f"({format(amt_usd, 'f')} USD)."
    )


class DuplicateEmailError(Exception):
    pass


@dataclass(frozen=True)
class FundWalletResult:
    ok: bool
    detail: str | None = None
    not_found: bool = False
    clerk_user_id: str | None = None
    balance_usd_cents_before: int | None = None
    balance_usd_cents_after: int | None = None
    ledger_sender_clerk_user_id: str | None = None


@dataclass(frozen=True)
class SendMoneyResult:
    ok: bool
    detail: str | None = None
    amount_usd_cents: int | None = None
    from_clerk_user_id: str | None = None
    to_clerk_user_id: str | None = None
    sender_balance_usd_cents_after: int | None = None
    # Current sender wallet balance (e.g. when rejecting for insufficient funds).
    sender_balance_usd_cents: int | None = None


# 1000 USD in cents (integer).
INITIAL_WALLET_BALANCE_USD_CENTS = 1000 * 100

# Outbound wallet transfer cap per transaction (USD cents); enforced in send_money_between_clerk_users.
MAX_WALLET_TRANSFER_PER_TRANSACTION_USD_CENTS = 1500 * 100


def _synthetic_dev_fund_sender_id() -> str:
    """Unique synthetic sender for each dev_fund ledger row (not a Clerk user)."""
    return f"sender_id_{secrets.token_hex(12)}"


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
    # Optional Pushover user key (https://pushover.net/) for wallet transfer alerts.
    pushover_user: str | None = None

    class Settings:
        name = "users"


class Wallet(TimestampedDocument):
    clerk_user_id: Annotated[str, Indexed(unique=True)]
    balance: int

    class Settings:
        name = "wallets"


class Transaction(TimestampedDocument):
    """Ledger row for a wallet transfer leg (one document per party per transfer)."""

    clerk_user_id: Annotated[str, Indexed()]
    sender_clerk_user_id: str
    receiver_clerk_user_id: str
    amount_usd_cents: int
    side: Literal["debit", "credit"]
    kind: str = "wallet_transfer"

    class Settings:
        name = "transactions"


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

    async def get_wallet_by_clerk_id(self, clerk_user_id: str) -> Wallet | None:
        return await Wallet.find_one(Wallet.clerk_user_id == clerk_user_id)

    @staticmethod
    def _contains_regex_fragment(value: str) -> dict[str, str]:
        return {"$regex": f".*{re.escape(value)}.*", "$options": "i"}

    async def search_users_by_name(
        self,
        *,
        query: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        limit: int = 25,
    ) -> list[User]:
        """Match users by optional broad `query` (first, last, or display name) and/or field filters (AND)."""
        q = (query or "").strip()
        fn = (first_name or "").strip()
        ln = (last_name or "").strip()
        if not q and not fn and not ln:
            return []

        clauses: list[dict] = []
        if q:
            rx = self._contains_regex_fragment(q)
            clauses.append(
                {
                    "$or": [
                        {"first_name": rx},
                        {"last_name": rx},
                        {"name": rx},
                    ]
                }
            )
        if fn:
            clauses.append({"first_name": self._contains_regex_fragment(fn)})
        if ln:
            clauses.append({"last_name": self._contains_regex_fragment(ln)})

        mongo_filter: dict = clauses[0] if len(clauses) == 1 else {"$and": clauses}
        return await User.find(mongo_filter).limit(limit).to_list()

    async def send_money_between_clerk_users(
        self,
        from_clerk_user_id: str,
        to_clerk_user_id: str,
        amount_usd_cents: int,
    ) -> SendMoneyResult:
        """Debit sender and credit receiver atomically (USD wallet balances in cents)."""
        logger.info(
            "send_money_between_clerk_users: invoked raw_from=%r raw_to=%r amount_usd_cents=%s",
            from_clerk_user_id,
            to_clerk_user_id,
            amount_usd_cents,
        )
        sender_id = from_clerk_user_id.strip()
        receiver_id = to_clerk_user_id.strip()
        if not sender_id or not receiver_id:
            logger.warning(
                "send_money_between_clerk_users: rejected empty id after_strip "
                "sender_id=%r receiver_id=%r amount_usd_cents=%s",
                sender_id,
                receiver_id,
                amount_usd_cents,
            )
            return SendMoneyResult(
                ok=False,
                detail="Sender and recipient Clerk user ids must be non-empty.",
            )
        if sender_id == receiver_id:
            logger.warning(
                "send_money_between_clerk_users: rejected self-transfer clerk_user_id=%r amount_usd_cents=%s",
                sender_id,
                amount_usd_cents,
            )
            return SendMoneyResult(
                ok=False,
                detail="You cannot send money to yourself.",
            )
        if amount_usd_cents <= 0:
            logger.warning(
                "send_money_between_clerk_users: rejected non-positive amount "
                "sender_id=%r receiver_id=%r amount_usd_cents=%s",
                sender_id,
                receiver_id,
                amount_usd_cents,
            )
            return SendMoneyResult(
                ok=False,
                detail="Transfer amount must be at least one cent.",
            )
        if amount_usd_cents > MAX_WALLET_TRANSFER_PER_TRANSACTION_USD_CENTS:
            max_usd = MAX_WALLET_TRANSFER_PER_TRANSACTION_USD_CENTS // 100
            logger.warning(
                "send_money_between_clerk_users: rejected over per-tx cap "
                "sender_id=%s receiver_id=%s amount_usd_cents=%s cap=%s",
                sender_id,
                receiver_id,
                amount_usd_cents,
                MAX_WALLET_TRANSFER_PER_TRANSACTION_USD_CENTS,
            )
            return SendMoneyResult(
                ok=False,
                detail=(
                    f"A single transfer cannot exceed {max_usd} USD. "
                    "Split larger amounts into multiple transfers or reduce the amount."
                ),
                amount_usd_cents=amount_usd_cents,
                from_clerk_user_id=sender_id,
                to_clerk_user_id=receiver_id,
            )

        db = self._client.get_default_database()
        if db is None:
            logger.error("send_money_between_clerk_users: no default database on client uri")
            raise ValueError(
                "database_uri must include a database name in the path, "
                "e.g. mongodb://localhost:27017/mwallet"
            )
        wallets = db[Wallet.Settings.name]
        transactions_coll = db[Transaction.Settings.name]

        prior_sender = await wallets.find_one({"clerk_user_id": sender_id})
        if prior_sender is None:
            logger.warning(
                "send_money_between_clerk_users: no sender wallet before transaction "
                "sender_id=%s amount_usd_cents=%s",
                sender_id,
                amount_usd_cents,
            )
            return SendMoneyResult(
                ok=False,
                detail="No wallet exists for the sender account.",
                amount_usd_cents=amount_usd_cents,
                from_clerk_user_id=sender_id,
                to_clerk_user_id=receiver_id,
            )
        current_balance = int(prior_sender.get("balance") or 0)
        if current_balance < amount_usd_cents:
            detail = _insufficient_funds_detail(
                balance_usd_cents=current_balance,
                attempted_usd_cents=amount_usd_cents,
            )
            logger.warning(
                "send_money_between_clerk_users: insufficient balance before transaction "
                "sender_id=%s balance_usd_cents=%s attempted_usd_cents=%s",
                sender_id,
                current_balance,
                amount_usd_cents,
            )
            return SendMoneyResult(
                ok=False,
                detail=detail,
                amount_usd_cents=amount_usd_cents,
                sender_balance_usd_cents=current_balance,
                from_clerk_user_id=sender_id,
                to_clerk_user_id=receiver_id,
            )

        logger.info(
            "send_money_between_clerk_users: starting transaction collection=%s "
            "sender_id=%s receiver_id=%s amount_usd_cents=%s",
            Wallet.Settings.name,
            sender_id,
            receiver_id,
            amount_usd_cents,
        )

        class _TxnAbort(Exception):
            __slots__ = ("message", "amount_cents", "balance_cents")

            def __init__(
                self,
                message: str,
                *,
                amount_cents: int | None = None,
                balance_cents: int | None = None,
            ) -> None:
                self.message = message
                self.amount_cents = amount_cents
                self.balance_cents = balance_cents

        try:
            async with self._client.start_session() as session:
                async with await session.start_transaction():
                    debit = await wallets.update_one(
                        {
                            "clerk_user_id": sender_id,
                            "balance": {"$gte": amount_usd_cents},
                        },
                        {"$inc": {"balance": -amount_usd_cents}},
                        session=session,
                    )
                    logger.info(
                        "send_money_between_clerk_users: debit update sender_id=%s "
                        "matched_count=%s modified_count=%s amount_usd_cents=%s",
                        sender_id,
                        debit.matched_count,
                        debit.modified_count,
                        amount_usd_cents,
                    )
                    if debit.modified_count == 0:
                        sender = await wallets.find_one(
                            {"clerk_user_id": sender_id},
                            session=session,
                        )
                        if sender is None:
                            logger.warning(
                                "send_money_between_clerk_users: debit failed no sender wallet "
                                "sender_id=%s receiver_id=%s amount_usd_cents=%s",
                                sender_id,
                                receiver_id,
                                amount_usd_cents,
                            )
                            raise _TxnAbort(
                                "No wallet exists for the sender account.",
                                amount_cents=amount_usd_cents,
                            ) from None
                        sender_balance = int(sender.get("balance") or 0)
                        logger.warning(
                            "send_money_between_clerk_users: debit failed insufficient funds "
                            "sender_id=%s receiver_id=%s amount_usd_cents=%s sender_balance_usd_cents=%s",
                            sender_id,
                            receiver_id,
                            amount_usd_cents,
                            sender_balance,
                        )
                        raise _TxnAbort(
                            _insufficient_funds_detail(
                                balance_usd_cents=sender_balance,
                                attempted_usd_cents=amount_usd_cents,
                            ),
                            amount_cents=amount_usd_cents,
                            balance_cents=sender_balance,
                        ) from None

                    credit = await wallets.update_one(
                        {"clerk_user_id": receiver_id},
                        {"$inc": {"balance": amount_usd_cents}},
                        session=session,
                    )
                    logger.info(
                        "send_money_between_clerk_users: credit update receiver_id=%s "
                        "matched_count=%s modified_count=%s amount_usd_cents=%s",
                        receiver_id,
                        credit.matched_count,
                        credit.modified_count,
                        amount_usd_cents,
                    )
                    if credit.modified_count == 0:
                        logger.warning(
                            "send_money_between_clerk_users: credit failed no receiver wallet "
                            "sender_id=%s receiver_id=%s amount_usd_cents=%s (transaction will abort)",
                            sender_id,
                            receiver_id,
                            amount_usd_cents,
                        )
                        raise _TxnAbort(
                            "No wallet exists for the recipient account.",
                            amount_cents=amount_usd_cents,
                        ) from None

                    now = datetime.now(timezone.utc)
                    tx_common = {
                        "amount_usd_cents": amount_usd_cents,
                        "kind": "wallet_transfer",
                        "created_at": now,
                        "updated_at": now,
                    }
                    ins_sender = await transactions_coll.insert_one(
                        {
                            "clerk_user_id": sender_id,
                            "sender_clerk_user_id": sender_id,
                            "receiver_clerk_user_id": receiver_id,
                            "side": "debit",
                            **tx_common,
                        },
                        session=session,
                    )
                    ins_receiver = await transactions_coll.insert_one(
                        {
                            "clerk_user_id": receiver_id,
                            "sender_clerk_user_id": sender_id,
                            "receiver_clerk_user_id": receiver_id,
                            "side": "credit",
                            **tx_common,
                        },
                        session=session,
                    )
                    logger.info(
                        "send_money_between_clerk_users: ledger inserts sender_tx_id=%s receiver_tx_id=%s",
                        ins_sender.inserted_id,
                        ins_receiver.inserted_id,
                    )

                    sender_after = await wallets.find_one(
                        {"clerk_user_id": sender_id},
                        session=session,
                    )
                    if sender_after is None:
                        raise _TxnAbort(
                            "Sender wallet record missing after debit.",
                            amount_cents=amount_usd_cents,
                        )
                    new_balance = int(sender_after.get("balance", 0))
                    logger.info(
                        "send_money_between_clerk_users: success sender_id=%s receiver_id=%s "
                        "amount_usd_cents=%s sender_balance_usd_cents_after=%s",
                        sender_id,
                        receiver_id,
                        amount_usd_cents,
                        new_balance,
                    )

                transfer_result = SendMoneyResult(
                    ok=True,
                    amount_usd_cents=amount_usd_cents,
                    from_clerk_user_id=sender_id,
                    to_clerk_user_id=receiver_id,
                    sender_balance_usd_cents_after=new_balance,
                )
                try:
                    schedule_wallet_transfer_pushover_notifications(
                        sender_clerk_user_id=sender_id,
                        receiver_clerk_user_id=receiver_id,
                        amount_usd_cents=amount_usd_cents,
                    )
                except Exception:
                    logger.exception(
                        "send_money_between_clerk_users: post-commit notification scheduling failed "
                        "(transfer already committed)"
                    )
                return transfer_result
        except _TxnAbort as e:
            logger.warning(
                "send_money_between_clerk_users: aborted sender_id=%s receiver_id=%s "
                "amount_usd_cents=%s detail=%s",
                sender_id,
                receiver_id,
                amount_usd_cents,
                e.message,
            )
            return SendMoneyResult(
                ok=False,
                detail=e.message,
                amount_usd_cents=e.amount_cents if e.amount_cents is not None else amount_usd_cents,
                sender_balance_usd_cents=e.balance_cents,
                from_clerk_user_id=sender_id,
                to_clerk_user_id=receiver_id,
            )
        except PyMongoError as e:
            logger.exception(
                "send_money_between_clerk_users: database error sender_id=%s receiver_id=%s "
                "amount_usd_cents=%s",
                sender_id,
                receiver_id,
                amount_usd_cents,
            )
            return SendMoneyResult(
                ok=False,
                detail=(
                    "The transfer could not be completed due to a database error "
                    f"({type(e).__name__}: {e}). If you use a standalone MongoDB "
                    "server, configure a replica set so multi-document transactions work."
                ),
            )

    async def fund_wallet_for_clerk_user(
        self,
        clerk_user_id: str,
        amount_usd_cents: int,
    ) -> FundWalletResult:
        """Credit a wallet and append a dev_fund ledger row (no debit peer)."""
        uid = clerk_user_id.strip()
        if not uid:
            return FundWalletResult(ok=False, detail="clerk_user_id must be non-empty.")
        if amount_usd_cents <= 0:
            return FundWalletResult(
                ok=False,
                detail="amount_usd_cents must be a positive integer (USD cents).",
            )

        db = self._client.get_default_database()
        if db is None:
            logger.error("fund_wallet_for_clerk_user: no default database on client uri")
            return FundWalletResult(
                ok=False,
                detail="database_uri must include a database name in the path.",
            )

        wallets = db[Wallet.Settings.name]
        transactions_coll = db[Transaction.Settings.name]

        prior = await wallets.find_one({"clerk_user_id": uid})
        if prior is None:
            return FundWalletResult(
                ok=False,
                not_found=True,
                detail="No wallet exists for this Clerk user id.",
                clerk_user_id=uid,
            )

        balance_before = int(prior.get("balance") or 0)
        inc = await wallets.update_one(
            {"clerk_user_id": uid},
            {"$inc": {"balance": amount_usd_cents}},
        )
        if inc.modified_count == 0:
            return FundWalletResult(
                ok=False,
                detail="Wallet balance update failed.",
                clerk_user_id=uid,
            )

        after_doc = await wallets.find_one({"clerk_user_id": uid})
        balance_after = int(after_doc.get("balance") or 0) if after_doc else balance_before + amount_usd_cents

        ledger_sender = _synthetic_dev_fund_sender_id()
        now = datetime.now(timezone.utc)
        await transactions_coll.insert_one(
            {
                "clerk_user_id": uid,
                "sender_clerk_user_id": ledger_sender,
                "receiver_clerk_user_id": uid,
                "amount_usd_cents": amount_usd_cents,
                "side": "credit",
                "kind": "dev_fund",
                "created_at": now,
                "updated_at": now,
            }
        )
        logger.info(
            "fund_wallet_for_clerk_user: credited clerk_user_id=%s amount_usd_cents=%s balance_after=%s",
            uid,
            amount_usd_cents,
            balance_after,
        )
        return FundWalletResult(
            ok=True,
            clerk_user_id=uid,
            balance_usd_cents_before=balance_before,
            balance_usd_cents_after=balance_after,
            ledger_sender_clerk_user_id=ledger_sender,
        )

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


# Imported after models and UserRepository are defined to avoid circular imports with
# `app.notifications.pushover` (which imports `User` from this module).
from app.notifications.pushover import schedule_wallet_transfer_pushover_notifications  # noqa: E402
