import httpx
from clerk_backend_api import Clerk
from clerk_backend_api.models.user import User as ClerkUser
from clerk_backend_api.security import AuthenticateRequestOptions
from fastapi import HTTPException, Request

from app.config import settings



_clerk: Clerk | None = None


def get_clerk() -> Clerk:
    global _clerk
    if _clerk is None:
        _clerk = Clerk(bearer_auth=settings.clerk_secret_key)
    return _clerk


def _build_auth_options() -> AuthenticateRequestOptions:
    parties = settings.clerk_authorized_party_list
    ap = parties if parties else None
    jwt_key = (settings.clerk_jwt_key or "").strip().replace("\\n", "\n")
    if jwt_key:
        return AuthenticateRequestOptions(jwt_key=jwt_key, authorized_parties=ap)
    if parties:
        return AuthenticateRequestOptions(authorized_parties=parties)
    return AuthenticateRequestOptions()


def _to_httpx_request(request: Request) -> httpx.Request:
    return httpx.Request(
        method=request.method,
        url=str(request.url),
        headers=dict(request.headers),
    )


async def get_clerk_session_payload(request: Request) -> dict:
    clerk = get_clerk()
    state = clerk.authenticate_request(
        _to_httpx_request(request),
        _build_auth_options(),
    )

    if not state.is_signed_in:
        raise HTTPException(
            status_code=401,
            detail=state.message or "Not authenticated",
        )

    if not state.payload:
        raise HTTPException(status_code=401, detail="Invalid session")

    return state.payload


def _primary_email_from_clerk_user(user: ClerkUser) -> str | None:
    if not user.email_addresses:
        return None
    by_id = {ea.id: ea.email_address for ea in user.email_addresses}
    if user.primary_email_address_id and user.primary_email_address_id in by_id:
        return by_id[user.primary_email_address_id]
    return user.email_addresses[0].email_address


async def enrich_session_payload_for_sync(payload: dict) -> dict:
    """Session JWTs often omit `email`; load the Clerk user when needed."""
    if payload.get("email"):
        return payload
    sub = payload.get("sub")
    if not sub or not isinstance(sub, str):
        raise HTTPException(status_code=401, detail="Invalid session token")
    user = await get_clerk().users.get_async(user_id=sub)
    email = _primary_email_from_clerk_user(user)
    if not email:
        raise HTTPException(
            status_code=400,
            detail="Clerk user has no email address; cannot sync to database.",
        )
    merged = dict(payload)
    merged["email"] = email
    if user.first_name and not merged.get("first_name"):
        merged["first_name"] = user.first_name
    if user.last_name and not merged.get("last_name"):
        merged["last_name"] = user.last_name
    if user.username and not merged.get("username"):
        merged["username"] = user.username
    image = user.image_url or user.profile_image_url
    if image and not merged.get("image_url") and not merged.get("picture"):
        merged["image_url"] = image
    return merged