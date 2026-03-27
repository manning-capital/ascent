from fastapi import APIRouter

from ascent.server.dependencies import engine

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/reset-pool")
def reset_pool():
    """Dispose the SQLAlchemy connection pool, forcing fresh connections."""
    engine.dispose()
    return {"status": "ok"}
