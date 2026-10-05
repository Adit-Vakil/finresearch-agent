from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("FinResearch API starting up")
    from app.db.connection import check_db_health
    db_ok = check_db_health()
    if db_ok:
        logger.info("Database connection: OK")
    else:
        logger.warning("Database connection: FAILED — check DATABASE_URL and that the DB is running")
    yield
    logger.info("FinResearch API shutting down")


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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
