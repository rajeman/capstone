"""Unauthenticated wallet funding for local/testing only."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.deps import get_user_repository
from app.repositories.repository import UserRepository

router = APIRouter(prefix="/dev", tags=["dev"])


class FundWalletBody(BaseModel):
    clerk_user_id: str = Field(min_length=1)
    amount_usd_cents: int = Field(gt=0, le=1_000_000_000)


@router.post("/wallet/fund", status_code=200)
async def fund_wallet(
    body: FundWalletBody,
    repo: UserRepository = Depends(get_user_repository),
):
    if not settings.allow_unprotected_wallet_fund:
        raise HTTPException(status_code=404, detail="Not found")

    result = await repo.fund_wallet_for_clerk_user(
        body.clerk_user_id,
        body.amount_usd_cents,
    )
    if result.not_found:
        raise HTTPException(status_code=404, detail=result.detail)
    if not result.ok:
        raise HTTPException(status_code=400, detail=result.detail or "Fund failed")

    return {
        "clerk_user_id": result.clerk_user_id,
        "amount_usd_cents": body.amount_usd_cents,
        "balance_usd_cents_before": result.balance_usd_cents_before,
        "balance_usd_cents_after": result.balance_usd_cents_after,
        "sender_clerk_user_id": result.ledger_sender_clerk_user_id,
    }
