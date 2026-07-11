import logging
import threading

from sqlalchemy.orm import Session

from app.ml.artifacts import load_active_booster
from app.ml.inference import score_latest
from app.models import ScreenerSnapshot
from app.services.market_data import load_bars
from app.services.universe import BENCHMARK_SYMBOL, active_symbols

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_cache: dict = {"loaded_version": None, "booster": None, "record": None}


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
            _cache["booster"], _cache["record"] = loaded
            _cache["loaded_version"] = active.version
        return _cache["booster"], _cache["record"]


def predict_symbol(db: Session, symbol: str) -> dict:
    loaded = get_active_model(db)
    if loaded is None:
        return {"model_available": False}
    booster, record = loaded

    bars = load_bars(db, symbol)
    spy = load_bars(db, BENCHMARK_SYMBOL)
    result = score_latest(booster, bars, spy["close"] if not spy.empty else None)
    if result is None:
        return {"model_available": False}

    return {
        "model_available": True,
        "symbol": symbol,
        "prob_up": result["prob_up"],
        "direction": "up" if result["prob_up"] >= 0.5 else "down",
        "horizon_days": record.horizon_days,
        "model_version": record.version,
        "as_of_date": result["as_of_date"],
        "top_contributions": result["contributions"],
    }


def score_all_snapshots(db: Session) -> str:
    """Batch-score every active ticker into screener_snapshots.ai_prob_up."""
    loaded = get_active_model(db)
    if loaded is None:
        return "AI scoring skipped (no trained model)"
    booster, record = loaded

    spy = load_bars(db, BENCHMARK_SYMBOL)
    spy_close = spy["close"] if not spy.empty else None
    scored = 0
    for symbol in active_symbols(db, include_benchmark=False):
        snapshot = db.get(ScreenerSnapshot, symbol)
        if snapshot is None:
            continue
        bars = load_bars(db, symbol)
        result = score_latest(booster, bars, spy_close)
        if result is None:
            continue
        snapshot.ai_prob_up = result["prob_up"]
        snapshot.ai_model_version = record.version
        scored += 1
        if scored % 100 == 0:
            db.commit()
    db.commit()
    return f"AI scores updated for {scored} tickers ({record.version})"
