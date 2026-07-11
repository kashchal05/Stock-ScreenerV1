from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ModelVersion, RefreshRun, ScreenerSnapshot, Ticker
from app.schemas import MetaOut, RefreshStatus
from app.services.refresh import execute_full_refresh, get_running_run, start_run
from app.services.universe import BENCHMARK_SYMBOL

router = APIRouter(prefix="/api", tags=["admin"])


@router.post("/admin/refresh", response_model=RefreshStatus, status_code=202)
def trigger_refresh(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    # SQLite has a single writer: one refresh job at a time.
    if get_running_run(db) is not None:
        raise HTTPException(status_code=409, detail="A refresh is already running")
    run = start_run(db, kind="full")
    background_tasks.add_task(execute_full_refresh, run.id)
    return RefreshStatus.model_validate(run, from_attributes=True)


@router.get("/admin/refresh/status", response_model=RefreshStatus)
def refresh_status(db: Session = Depends(get_db)):
    run = db.query(RefreshRun).order_by(RefreshRun.id.desc()).first()
    if run is None:
        return RefreshStatus()
    return RefreshStatus.model_validate(run, from_attributes=True)


@router.get("/meta", response_model=MetaOut)
def meta(db: Session = Depends(get_db)):
    universe_size = (
        db.query(func.count(Ticker.symbol))
        .filter(Ticker.is_active.is_(True), Ticker.symbol != BENCHMARK_SYMBOL)
        .scalar()
    )
    sectors = [
        row[0]
        for row in db.query(ScreenerSnapshot.sector)
        .filter(ScreenerSnapshot.sector.isnot(None))
        .distinct()
        .order_by(ScreenerSnapshot.sector)
        .all()
    ]
    data_as_of = db.query(func.max(ScreenerSnapshot.as_of_date)).scalar()
    last_run = db.query(RefreshRun).order_by(RefreshRun.id.desc()).first()
    model_available = (
        db.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).first() is not None
    )
    return MetaOut(
        universe_size=universe_size or 0,
        sectors=sectors,
        data_as_of=data_as_of,
        last_refresh=RefreshStatus.model_validate(last_run, from_attributes=True) if last_run else None,
        model_available=model_available,
    )


@router.get("/health")
def health():
    return {"status": "ok"}
