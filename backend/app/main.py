import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, text

from app.config import settings

logger = logging.getLogger(__name__)

app = FastAPI(title="Case Intelligence RAG", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    # Check required config
    errors: list[str] = []

    if not settings.database_url:
        errors.append("DATABASE_URL not set")

    # DB connectivity check — use sync engine for simplicity in Phase 1
    # Convert async URL (postgresql+psycopg) to sync-compatible check
    db_ok = False
    db_error: str | None = None
    try:
        # Use sync engine; psycopg works with postgresql+psycopg URL
        engine = create_engine(settings.database_url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
        engine.dispose()
    except Exception as exc:  # noqa: BLE001
        db_error = str(exc)
        errors.append(f"database unreachable: {db_error}")

    # Anthropic key presence check (only hard-fail if LLM is required at ready time)
    # Spec §38 says /ready asserts ANTHROPIC_API_KEY is set
    if not settings.anthropic_api_key:
        errors.append("ANTHROPIC_API_KEY not set")

    if errors:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "errors": errors,
                "database": "ok" if db_ok else f"error: {db_error}",
                "config": "ok" if settings.database_url else "missing",
            },
        )

    return {
        "status": "ready",
        "database": "ok",
        "config": "ok",
        "anthropic_key": "present",
    }


@app.get("/")
async def root():
    return {"service": "case-intelligence-rag", "health": "/health", "ready": "/ready"}


# Placeholder query endpoint — full implementation in Phase 8
@app.post("/api/v1/query")
async def query_placeholder(payload: dict):
    return JSONResponse(
        status_code=501,
        content={
            "detail": "query endpoint not yet implemented (Phase 8)",
            "request_id": str(uuid.uuid4()),
        },
    )
