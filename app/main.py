from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.db import connect, disconnect
from app.repositories.repository import User
from app.routers import users


@asynccontextmanager
async def lifespan(_: FastAPI):
    await connect(document_models=[User])
    try:
        yield
    finally:
        await disconnect()


app = FastAPI(
    title="capstone",
    lifespan=lifespan
)

app.include_router(users.router)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}