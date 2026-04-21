from fastapi import APIRouter, Depends, HTTPException, Request

from app.clerk_auth import enrich_session_payload_for_sync, get_clerk_session_payload
from app.config import settings
from app.deps import get_user_repository
from app.repositories.repository import DuplicateEmailError, UserRepository

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/clerk/sync", status_code=200)
async def clerk_sync(
    request: Request,
    repo: UserRepository = Depends(get_user_repository),
):
    internal = request.headers.get("X-Clerk-Sync-Secret")
    if (
        settings.clerk_sync_secret
        and internal
        and internal == settings.clerk_sync_secret
    ):
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body") from None
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="Body must be a JSON object")
        payload = body
    else:
        payload = await get_clerk_session_payload(request)
    payload = await enrich_session_payload_for_sync(payload)
    try:
        user_id, created = await repo.sync_user_from_clerk(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except DuplicateEmailError:
        raise HTTPException(
            status_code=409,
            detail="A user with this email already exists.",
        ) from None
    return {"id": user_id, "created": created}
