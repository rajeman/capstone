# SmartPay (capstone)

Full-stack demo banking app: a **Next.js** frontend with **Clerk** sign-in talks to a **FastAPI** backend that stores users, wallets, and transactions in **MongoDB**. A **GPT-4o-mini** agent (OpenAI Agents SDK) powers chat: balances, transfers, directory search, and optional **transaction analytics charts**. Optional **Pushover** notifies parties after wallet transfers. The same process can serve the exported static UI and the API (Docker / AWS App Runner).

---

## What it does

- **Authenticated banking chat** — `POST /chat` runs a capstone agent with tools for session checks, send-money validation and execution, balances, transaction history, user lookup, and a nested “chart specialist” agent for spending visuals.
- **Clerk + Mongo** — Session JWTs protect API routes; users sync into Mongo after sign-in.
- **Dev wallet funding** — Controlled dev endpoint for crediting wallets when explicitly enabled.
- **Deploy** — Multi-stage Docker image (Next static export + Python), Terraform for ECR/App Runner, GitHub Actions for tests and deploy.

For diagrams (agents, deploy, push, auth), see **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

---

## Repository layout

```text
capstone/
├── backend/                 # Python package (FastAPI app lives in app/)
│   ├── app/
│   │   ├── main.py          # FastAPI app, lifespan, static mount, /health
│   │   ├── config.py        # Pydantic settings (env)
│   │   ├── db.py            # Mongo / Beanie
│   │   ├── clerk_auth.py    # Clerk JWT verification
│   │   ├── deps.py          # FastAPI dependencies
│   │   ├── document_models.py
│   │   ├── models/
│   │   ├── repositories/    # User / wallet persistence
│   │   ├── routers/         # auth, chat, users, dev_wallet
│   │   ├── llm/             # agent, prompts, run_trace, OpenAI init
│   │   ├── tools/           # Agent tools (banking, session, user_info, …)
│   │   ├── notifications/   # Pushover
│   │   └── analytics/       # Transaction stats for chart tool
│   ├── tests/               # Pytest suite
│   ├── scripts/             # Optional maintenance / docs scripts
│   └── pyproject.toml
├── frontend/                # Next.js (pages router), Clerk, chat UI
├── terraform/               # ECR, IAM, App Runner, LangSmith vars
├── docs/
│   └── ARCHITECTURE.md      # Deep-dive architecture
├── Dockerfile               # Frontend build → static + backend image
└── .github/workflows/       # CI: pytest + Terraform; deploy on main
```

---

## Logging

The backend uses the **standard library `logging`** module (no structured logging framework).

- **Repositories** (`app/repositories/repository.py`) — `info` / `warning` / `error` / `exception` for wallet operations, send-money guards, and DB edge cases.
- **Pushover** (`app/notifications/pushover.py`) — `debug` when disabled or skipped, `warning` on API issues, `exception` on send failures.

Configure log level and format the usual way (e.g. `uvicorn` flags or `LOG_LEVEL` if you wrap startup). There is no custom logging middleware on the FastAPI app today.

---

## Tracing

Two related mechanisms:

### 1. LangSmith (OpenAI Agents SDK)

On startup, `init_openai()` in `backend/app/llm/openai_setup.py` registers the default `AsyncOpenAI` client and, when enabled, **`OpenAIAgentsTracingProcessor`** so agent runs emit traces to **LangSmith**.

Enable tracing when **either** `LANGSMITH_TRACING` **or** `LANGCHAIN_TRACING_V2` is set to a truthy string (`true`, `1`, `yes`, `on`) **and** `LANGSMITH_API_KEY` is non-empty. Optional: `LANGSMITH_ENDPOINT`, `LANGSMITH_PROJECT` (also wired through Terraform `locals.tf`).

If tracing is “on” but the API key is missing or the integration import fails, the app logs a **warning** and continues without LangSmith.

### 2. User-facing “thinking steps” (not OpenTelemetry)

`POST /chat` uses `user_facing_trace_steps()` in `backend/app/llm/run_trace.py` to turn SDK **run items** (tool calls, etc.) into **plain-language steps** for the chat UI—no raw payloads. This is product-facing trace summarization, not distributed tracing.

---

## Tests

- **Runner**: [pytest](https://docs.pytest.org/) with **pytest-asyncio** (`asyncio_mode = auto` in `backend/pyproject.toml`).
- **Location**: `backend/tests/` (`conftest.py` plus test modules).
- **Bootstrap**: `backend/tests/conftest.py` sets minimal env vars (`DATABASE_URI`, `CLERK_SECRET_KEY`, `OPENAI_API_KEY`) so `Settings()` can load before imports; point `DATABASE_URI` at a real Mongo instance when tests touch the DB.

**Local run** (from `backend/`):

```bash
uv sync --group dev && uv run --group dev pytest tests/ -q
```

**CI**: `.github/workflows/dev.yaml` runs the same `uv sync` + `pytest` on push/PR to `main`, before Terraform.

---

## Architecture (summary)

| Layer | Role |
|--------|------|
| **Browser** | Next.js + Clerk; Bearer JWT on API calls; static assets from same origin in container deploy. |
| **FastAPI** | REST: auth sync, chat, users, health; optional static `StaticFiles` for exported frontend. |
| **Agents** | Single main agent + tools; nested agent as `buildTransactionHistoryAnalytics` tool with an `input_builder` scoped to the signed-in user. |
| **MongoDB** | Beanie documents for users, wallets, ledger. |
| **AWS** | ECR image → App Runner; secrets via Terraform / GitHub Actions. |

**Full narrative**, Mermaid diagrams, and file-level references: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

---

## Quick start (local)

1. **MongoDB** — Running locally or remote; set `DATABASE_URI`.
2. **Backend** — From `backend/`: set `DATABASE_URI`, `CLERK_SECRET_KEY`, `OPENAI_API_KEY` (and other vars from `app/config.py` as needed), then `uv sync` and `uvicorn app.main:app --reload` (run with `cwd` = `backend/` so imports resolve, or install the package per your layout).
3. **Frontend** — From `frontend/`: `npm install`, set Clerk and API URL env vars per `next.config` / product pages, `npm run dev`.

Production-style run matches **Dockerfile**: build frontend to `out/`, copy to `./static` next to the installed `app` package, `uvicorn app.main:app --host 0.0.0.0 --port 8000`.

---

## License

See [LICENSE](LICENSE) in the repository root.
