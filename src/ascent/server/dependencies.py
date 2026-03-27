from collections.abc import Generator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session

from ascent.engine.cache import EngineCache
from ascent.server.config import settings

engine: Engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=300,
)
cache: EngineCache = EngineCache(settings.redis_url)


@event.listens_for(engine, "handle_error")
def _invalidate_on_stale_oid(context):  # type: ignore[no-untyped-def]
    """Auto-invalidate connections that hit stale OID errors after schema drops."""
    msg = str(context.original_exception)
    if "could not open relation with OID" in msg:
        context.invalidate_connection = True


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def get_cache() -> EngineCache:
    return cache
