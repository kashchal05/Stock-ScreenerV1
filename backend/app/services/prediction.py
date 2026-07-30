import logging
import threading
from datetime import date

from sqlalchemy.orm import Session

from app.ml.artifacts import load_active_booster
from app.ml.cross_section import MODEL_FEATURE_COLUMNS, build_latest_cross_section
from app.ml.inference import score_row
from app.models import ScreenerSnapshot

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_cache: dict = {"loaded_version": None, "booster": None, "record": None, "calibration": None}
# The current-universe cross-section is expensive to build (loads every symbol's
# bars), so cache it per as-of date; the on-demand detail endpoint reuses it.
_xsection_cache: dict = {"date": None, "frame": None}


def get_active_model(db: Session):
    """Lazily load and cache the active booster; reload if the active version changed."""
    from app.models import ModelVersion

    active = db.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).first()
    if active is None:
        return None
    with _lock:
        if _cache["loaded_version"] != active.version:
            loaded = load_active_booster(db)
            if loaded is None:
                return None
            _cache["booster"], _cache["record"], _cache["calibration"] = loaded
            _cache["loaded_version"] = active.version
        return _cache["booster"], _cache["record"], _cache["calibration"]


def _get_cross_section(db: Session, force: bool = False):
    today = date.today()
    with _lock:
        if force or _xsection_cache["date"] != today or _xsection_cache["frame"] is None:
            _xsection_cache["frame"] = build_latest_cross_section(db, MODEL_FEATURE_COLUMNS)
            _xsection_cache["date"] = today
        return _xsection_cache["frame"]


def predict_symbol(db: Session, symbol: str) -> dict:
    loaded = get_active_model(db)
    if loaded is None:
        return {"model_available": False}
    booster, record, calibration = loaded

    frame = _get_cross_section(db)
    if frame.empty or symbol not in frame.index:
        return {"model_available": False}
    row = frame.loc[symbol]
    result = score_row(booster, row, calibration=calibration)
    if result is None:
        return {"model_available": False}

    return {
        "model_available": True,
        "symbol": symbol,
        "prob_up": result["prob_up"],
        "direction": "outperform" if result["prob_up"] >= 0.5 else "underperform",
        "horizon_days": record.horizon_days,
        "model_version": record.version,
        "as_of_date": row["date"],
        "top_contributions": result["contributions"],
    }


def score_all_snapshots(db: Session) -> str:
    """Batch-score every active ticker into screener_snapshots.ai_prob_up.

    Builds the universe cross-section once (so xs_* ranks are consistent), then
    scores every row — this is the canonical cross-sectional scoring pass.
    """
    loaded = get_active_model(db)
    if loaded is None:
        return "AI scoring skipped (no trained model)"
    booster, record, calibration = loaded

    frame = _get_cross_section(db, force=True)
    if frame.empty:
        return "AI scoring skipped (no universe data)"

    scored = 0
    for symbol, row in frame.iterrows():
        snapshot = db.get(ScreenerSnapshot, symbol)
        if snapshot is None:
            continue
        result = score_row(booster, row, calibration=calibration)
        if result is None:
            continue
        snapshot.ai_prob_up = result["prob_up"]
        snapshot.ai_model_version = record.version
        scored += 1
        if scored % 100 == 0:
            db.commit()
    db.commit()
    return f"AI scores updated for {scored} tickers ({record.version})"
