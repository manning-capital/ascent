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
    attributes,
    composites,
    dashboard,
    data_explorer,
    exchanges,
    feeds,
    instruments,
    metadata,
    orders,
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
    from sqlalchemy import text

    from ascent.database.models import Base
    from ascent.server.dependencies import engine

    Base.metadata.create_all(bind=engine)

    # Convert attribute tables to TimescaleDB hypertables (daily chunks)
    from ascent.database.setup import ensure_hypertables

    ensure_hypertables(engine)

    # Add columns that create_all() won't add to existing tables
    with engine.connect() as conn:
        conn.execute(
            text(
                "ALTER TABLE asset_type ADD COLUMN IF NOT EXISTS "
                "parent_type_id UUID REFERENCES asset_type(id)"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE provider_type ADD COLUMN IF NOT EXISTS "
                "parent_type_id UUID REFERENCES provider_type(id)"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE instrument_type ADD COLUMN IF NOT EXISTS "
                "parent_type_id UUID REFERENCES instrument_type(id)"
            )
        )
        conn.execute(
            text("ALTER TABLE metadata ADD COLUMN IF NOT EXISTS display_name VARCHAR(200)")
        )
        # Backfill display_name from name for any rows missing it
        conn.execute(
            text(
                "UPDATE metadata SET display_name = INITCAP(REPLACE(name, '_', ' ')) "
                "WHERE display_name IS NULL"
            )
        )
        # Now make it NOT NULL
        conn.execute(text("ALTER TABLE metadata ALTER COLUMN display_name SET NOT NULL"))
        # Migrate old value_type values to new ones
        conn.execute(text("UPDATE metadata SET value_type = 'float' WHERE value_type = 'number'"))
        conn.execute(text("UPDATE metadata SET value_type = 'string' WHERE value_type = 'json'"))
        conn.execute(text("ALTER TABLE metadata ADD COLUMN IF NOT EXISTS config JSONB"))
        # Convert any non-primitive (dict/list) metadata values to JSON strings
        for tbl in ["asset_metadata", "provider_metadata", "provider_asset_metadata"]:
            conn.execute(
                text(
                    f"UPDATE {tbl} SET value = to_jsonb(value::text) "
                    f"WHERE jsonb_typeof(value) IN ('object', 'array')"
                )
            )
        # Feed scope columns: provider_id, instrument_type_id, composite_type_id
        conn.execute(
            text(
                "ALTER TABLE feed ADD COLUMN IF NOT EXISTS provider_id UUID REFERENCES provider(id)"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE feed ADD COLUMN IF NOT EXISTS "
                "instrument_type_id UUID REFERENCES instrument_type(id)"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE feed ADD COLUMN IF NOT EXISTS "
                "composite_type_id UUID REFERENCES composite_type(id)"
            )
        )
        # XOR check: exactly one of instrument_type_id / composite_type_id must be set.
        # Added NOT VALID so existing rows (which may have both NULL before backfill)
        # don't block the constraint creation.
        conn.execute(
            text(
                "DO $$ BEGIN "
                "ALTER TABLE feed ADD CONSTRAINT ck_feed_scope_xor CHECK ("
                "(instrument_type_id IS NOT NULL AND composite_type_id IS NULL) OR "
                "(instrument_type_id IS NULL AND composite_type_id IS NOT NULL)"
                ") NOT VALID; EXCEPTION WHEN duplicate_object THEN NULL; END $$"
            )
        )
        conn.commit()


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
        logger.error("Unhandled exception:\n%s", traceback.format_exc())
        detail = {"code": "internal_error", "status": 500}
        if settings.debug:
            detail["message"] = str(exc)
            detail["traceback"] = traceback.format_exc()
        else:
            detail["message"] = "An unexpected error occurred"
        return JSONResponse(status_code=500, content={"error": detail})

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
    app.include_router(orders.router, prefix="/api")
    app.include_router(types.router, prefix="/api")
    app.include_router(assets.router, prefix="/api")
    app.include_router(providers.router, prefix="/api")
    app.include_router(instruments.router, prefix="/api")
    app.include_router(composites.router, prefix="/api")
    app.include_router(exchanges.router, prefix="/api")
    app.include_router(attributes.router, prefix="/api")
    app.include_router(metadata.router, prefix="/api")
    app.include_router(data_explorer.router, prefix="/api")

    # Serve the UI if the static files exist
    if UI_STATIC_DIR.is_dir():
        app.mount("/", SPAStaticFiles(directory=str(UI_STATIC_DIR), html=True), name="ui")

    return app
