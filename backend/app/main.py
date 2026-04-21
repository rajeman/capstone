from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import connect, disconnect
from app.document_models import DOCUMENT_MODELS
from app.routers import auth, users


@asynccontextmanager
async def lifespan(_: FastAPI):
    await connect(document_models=DOCUMENT_MODELS)
    try:
        yield
    finally:
        await disconnect()


app = FastAPI(
    title="capstone",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(users.router)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}
