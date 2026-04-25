from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.db import connect, disconnect
from app.document_models import DOCUMENT_MODELS
from app.llm import init_openai
from app.routers import auth, chat, dev_wallet, users


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_openai()
    await connect(document_models=DOCUMENT_MODELS)
    try:
        yield
    finally:
        await disconnect()


app = FastAPI(
    title="capstone",
    lifespan=lifespan,
)

# Dev-friendly: allow any browser origin (LAN, tunnel, etc.). Starlette echoes
# the request Origin when allow_credentials=True with allow_origins=["*"].
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(dev_wallet.router)
app.include_router(users.router)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}


# Docker / single-binary deploy: Next `output: "export"` copied to ./static (cwd is WORKDIR).
_static = Path.cwd() / "static"
if _static.is_dir():
    app.mount("/", StaticFiles(directory=str(_static), html=True), name="static")
