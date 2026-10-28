import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, engine
from app.routers import (
    admin,
    backtest,
    plan,
    predictions,
    screener,
    screens,
    search,
    stocks,
    track_record,
    watchlist,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

app = FastAPI(title="Stock Screener API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def init_db():
    # Local/dev (SQLite): auto-create tables for zero-config startup.
    # Production (Postgres): schema is managed by Alembic migrations, so skip.
    if settings.is_sqlite:
        Base.metadata.create_all(bind=engine)


app.include_router(screener.router)
app.include_router(screens.router)
app.include_router(search.router)
app.include_router(stocks.router)
app.include_router(predictions.router)
app.include_router(watchlist.router)
app.include_router(track_record.router)
app.include_router(backtest.router)
app.include_router(plan.router)
app.include_router(admin.router)


# Single-service deploy: serve the built frontend (frontend/dist) if STATIC_DIR is
# set. Registered after the API routers, so /api/* always wins; everything else
# falls back to index.html for client-side routing.
_static = Path(settings.static_dir) if settings.static_dir else None
if _static and _static.is_dir():
    assets = _static / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str):
        candidate = _static / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_static / "index.html")
