import logging
from datetime import datetime

from app.database import SessionLocal
from app.models import RefreshRun

logger = logging.getLogger(__name__)


def get_running_run(db) -> RefreshRun | None:
    return db.query(RefreshRun).filter(RefreshRun.status == "running").first()


def start_run(db, kind: str) -> RefreshRun:
    run = RefreshRun(kind=kind, status="running")
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def execute_full_refresh(run_id: int) -> None:
    """Runs in a background thread: bars -> fundamentals -> snapshots -> AI scores.

    Opens its own session — the request session is long gone by the time this runs.
    """
    db = SessionLocal()
    details = []
    try:
        from app.services import market_data, snapshots

        details.append(market_data.refresh_bars(db))
        details.append(market_data.refresh_fundamentals(db))
        details.append(snapshots.rebuild_snapshots(db))
        try:
            from app.services.prediction import score_all_snapshots

            details.append(score_all_snapshots(db))
        except Exception:
            logger.exception("AI scoring failed; snapshots remain usable without scores")
            details.append("AI scoring skipped (see logs)")
        try:
            from app.services.picks import record_live_picks

            details.append(record_live_picks(db))
        except Exception:
            logger.exception("Live pick recording failed")
            details.append("live picks skipped (see logs)")
        _finish(db, run_id, "succeeded", "; ".join(details))
    except Exception as exc:
        logger.exception("Refresh run %d failed", run_id)
        _finish(db, run_id, "failed", f"{'; '.join(details)}; error: {exc}")
    finally:
        db.close()


def _finish(db, run_id: int, status: str, detail: str) -> None:
    run = db.get(RefreshRun, run_id)
    run.status = status
    run.finished_at = datetime.utcnow()
    run.detail = detail
    db.commit()
