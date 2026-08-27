import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, text

from app.config import settings
from app.observability.logging import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize structured JSON logging
    setup_logging()
    logger.info("Application starting up environment=%s", settings.app_env)

    # Optional auto-ingestion check on boot
    try:
        engine = create_engine(settings.database_url, pool_pre_ping=True)
        with engine.connect() as conn:
            chunk_count = 0
            try:
                chunk_count = conn.execute(text("SELECT count(*) FROM chunks")).scalar() or 0
            except Exception:
                chunk_count = 0

            logger.info("Database checked at boot chunk_count=%d", chunk_count)
            if chunk_count == 0:
                logger.info("Database chunks table empty — triggering auto-ingestion pipeline")
                from app.ingestion.pipeline import run_pipeline
                run_pipeline()
        engine.dispose()
    except Exception as exc:
        logger.warning("Auto-ingestion boot check error: %s", exc)

    yield

    logger.info("Application shutting down")


app = FastAPI(title="Case Intelligence RAG", version="0.1.0", lifespan=lifespan)

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
    start_time = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception as exc:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.error(
            "Unhandled server exception path=%s duration_ms=%.2f error=%s",
            request.url.path,
            duration_ms,
            exc,
            extra={"request_id": request_id, "duration_ms": duration_ms, "status_code": 500},
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "message": str(exc) if settings.app_env == "development" else "An unexpected error occurred",
                "request_id": request_id,
            },
            headers={"X-Request-ID": request_id},
        )

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "http_request path=%s method=%s status_code=%d duration_ms=%.2f",
        request.url.path,
        request.method,
        response.status_code,
        duration_ms,
        extra={"request_id": request_id, "duration_ms": duration_ms, "status_code": response.status_code},
    )
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "request_id": request_id},
        headers={"X-Request-ID": request_id},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=422,
        content={"error": "Validation Error", "details": exc.errors(), "request_id": request_id},
        headers={"X-Request-ID": request_id},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    errors: list[str] = []

    if not settings.database_url:
        errors.append("DATABASE_URL not set")

    db_ok = False
    db_error: str | None = None
    try:
        engine = create_engine(settings.database_url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
        engine.dispose()
    except Exception as exc:  # noqa: BLE001
        db_error = str(exc)
        errors.append(f"database unreachable: {db_error}")

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


from app.api.routes.query import router as query_router
app.include_router(query_router, prefix="/api/v1")

