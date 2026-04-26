"""Guard rails on wallet transfers (no Mongo — early returns only)."""

import pytest

from app.repositories.repository import (
    MAX_WALLET_TRANSFER_PER_TRANSACTION_USD_CENTS,
    UserRepository,
)


class _NoDbClient:
    """Repository must not reach Mongo for these scenarios."""

    def get_default_database(self):
        raise AssertionError("unexpected database access")


@pytest.fixture
def repo() -> UserRepository:
    return UserRepository(_NoDbClient())


@pytest.mark.asyncio
async def test_send_money_rejects_when_debit_does_not_match_allowed_clerk(repo: UserRepository) -> None:
    out = await repo.send_money_between_clerk_users(
        "user_alice",
        "user_bob",
        100,
        allowed_debit_clerk_user_id="user_attacker",
    )
    assert out.ok is False
    assert "own Smart Pay wallet" in (out.detail or "")
    assert out.from_clerk_user_id == "user_alice"
    assert out.to_clerk_user_id == "user_bob"


@pytest.mark.asyncio
async def test_send_money_rejects_empty_sender(repo: UserRepository) -> None:
    out = await repo.send_money_between_clerk_users(
        "   ",
        "user_bob",
        50,
        allowed_debit_clerk_user_id="user_bob",
    )
    assert out.ok is False
    assert "non-empty" in (out.detail or "").lower()


@pytest.mark.asyncio
async def test_send_money_rejects_self_transfer_before_db(repo: UserRepository) -> None:
    out = await repo.send_money_between_clerk_users(
        "same_user",
        "same_user",
        10,
        allowed_debit_clerk_user_id="same_user",
    )
    assert out.ok is False
    assert "yourself" in (out.detail or "").lower()


@pytest.mark.asyncio
async def test_send_money_rejects_non_positive_amount(repo: UserRepository) -> None:
    out = await repo.send_money_between_clerk_users(
        "u1",
        "u2",
        0,
        allowed_debit_clerk_user_id="u1",
    )
    assert out.ok is False
    assert "one cent" in (out.detail or "").lower()


@pytest.mark.asyncio
async def test_send_money_rejects_over_per_transaction_cap(repo: UserRepository) -> None:
    over = MAX_WALLET_TRANSFER_PER_TRANSACTION_USD_CENTS + 1
    out = await repo.send_money_between_clerk_users(
        "u1",
        "u2",
        over,
        allowed_debit_clerk_user_id="u1",
    )
    assert out.ok is False
    assert "1500" in (out.detail or "") or "exceed" in (out.detail or "").lower()
    assert out.amount_usd_cents == over
