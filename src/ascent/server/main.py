import logging
import pathlib
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import Scope

from ascent.server.config import settings
from ascent.server.exceptions import AscentAPIError
from ascent.server.routers import (
    admin,
    assets,
    dashboard,
    exchanges,
    feeds,
    orders,
    portfolios,
    provider_assets,
    providers,
    strategies,
    trades,
    types,
)

logger = logging.getLogger(__name__)

UI_STATIC_DIR = pathlib.Path(__file__).parent / "ui"


class SPAStaticFiles(StaticFiles):
    """Serve index.html for unknown routes so client-side routing works."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except Exception:
            return await super().get_response("./index.html", scope)


def _create_tables() -> None:
    """Create all database tables if they don't exist."""
    from ascent.database.models import Base
    from ascent.server.dependencies import engine

    Base.metadata.create_all(bind=engine)


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        _create_tables()
        yield

    app = FastAPI(title="Ascent", lifespan=lifespan)

    # ---- Exception handlers ----

    @app.exception_handler(AscentAPIError)
    async def ascent_error_handler(request: Request, exc: AscentAPIError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {"code": exc.code, "message": exc.message, "status": exc.status_code}
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "validation_error", "message": str(exc), "status": 422}},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        if settings.debug:
            logger.error("Unhandled exception:\n%s", traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected error occurred",
                    "status": 500,
                }
            },
        )

    # ---- Middleware ----

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routes
    app.include_router(admin.router, prefix="/api")
    app.include_router(trades.router, prefix="/api")
    app.include_router(feeds.router, prefix="/api")
    app.include_router(strategies.router, prefix="/api")
    app.include_router(dashboard.router, prefix="/api")
    app.include_router(portfolios.router, prefix="/api")
    app.include_router(orders.router, prefix="/api")
    app.include_router(types.router, prefix="/api")
    app.include_router(assets.router, prefix="/api")
    app.include_router(providers.router, prefix="/api")
    app.include_router(provider_assets.router, prefix="/api")
    app.include_router(exchanges.router, prefix="/api")

    # Serve the UI if the static files exist
    if UI_STATIC_DIR.is_dir():
        app.mount("/", SPAStaticFiles(directory=str(UI_STATIC_DIR), html=True), name="ui")

    return app
