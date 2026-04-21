from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_uri: str
    clerk_secret_key: str
    clerk_authorized_parties: str = ""
    clerk_jwt_key: str = Field(
        default="",
        description="PEM JWT public key from Clerk Dashboard (networkless verify; fixes JWKS kid mismatch).",
    )
    clerk_sync_secret: str = Field(
        default="",
        description="Optional: shared secret for Next.js verified-claims sync.",
    )

    @property
    def clerk_authorized_party_list(self) -> list[str]:
        return [p.strip() for p in self.clerk_authorized_parties.split(",") if p.strip()]


settings = Settings()
