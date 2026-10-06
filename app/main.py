from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("FinResearch API starting up (env=%s)", settings.APP_ENV)

    # Create tables and pgvector extension on first run.
    # init_db() is idempotent — safe to call on every startup.
    try:
        from app.db.connection import init_db
        init_db()
        logger.info("Database initialized")
    except Exception as exc:
        logger.warning("Database init failed: %s — continuing without DB", exc)

    yield
    logger.info("FinResearch API shutting down")


def _cors_origins() -> list[str]:
    raw = settings.ALLOWED_ORIGINS.strip()
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


app = FastAPI(
    title="FinResearch API",
    description="Evidence-grounded financial research over SEC filings using hybrid retrieval and RAG.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
