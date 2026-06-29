"""FastAPI application entrypoint.

Uses the application-factory pattern (`create_app`) so the app can be built
with different configs for tests vs. production, and so startup logic lives in
one place. Run with:  uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks."""
    configure_logging()
    settings.RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    settings.SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    # Dev convenience: create tables if missing. Set AUTO_CREATE_TABLES=false
    # in .env once you're managing the schema with Alembic.
    if settings.AUTO_CREATE_TABLES:
        from app.db.base import Base  # imports all models
        from app.db.session import engine
        Base.metadata.create_all(bind=engine)

    logger.info("Starting %s (env=%s)", settings.APP_NAME, settings.ENVIRONMENT)
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=__version__,
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    @app.get("/", tags=["root"])
    def root() -> dict:
        return {
            "message": f"{settings.APP_NAME} API",
            "docs": "/docs",
            "health": f"{settings.API_V1_PREFIX}/health",
        }

    return app


app = create_app()
