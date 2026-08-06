"""Model track record ("paper trading").

Two sources of picks:
- 'backtest': seeded from the leak-free walk-forward test predictions (see
  scripts/seed_picks.py) so the page shows a real out-of-sample record immediately.
- 'live': the current top-K by AI score, recorded going forward on each refresh and
  settled (realized return computed) once the horizon has elapsed.

Both use the same realized-return math, so the record is consistent.
"""

import logging
from datetime import date

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import ModelVersion, PickLog, ScreenerSnapshot
from app.services.market_data import load_bars
from app.services.universe import BENCHMARK_SYMBOL

logger = logging.getLogger(__name__)

TOP_K = 20


def _spy_forward_return(db: Session, as_of: date, horizon: int) -> float | None:
    bars = load_bars(db, BENCHMARK_SYMBOL)
    if bars.empty:
        return None
    idx = bars.index[bars.index <= as_of]
    if len(idx) == 0:
        return None
    start_pos = bars.index.get_loc(idx[-1])
    end_pos = start_pos + horizon
    if end_pos >= len(bars):
        return None
    return float(bars["close"].iloc[end_pos] / bars["close"].iloc[start_pos] - 1)


def record_live_picks(db: Session) -> str:
    """Log today's top-K by AI score (idempotent per day). Returns a status string."""
    active = db.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).first()
    if active is None:
        return "live picks skipped (no active model)"

    as_of = db.query(func.max(ScreenerSnapshot.as_of_date)).scalar()
    if as_of is None:
        return "live picks skipped (no snapshots)"
    if db.query(PickLog).filter(PickLog.as_of_date == as_of, PickLog.source == "live").first():
        return f"live picks already logged for {as_of}"

    top = (
        db.query(ScreenerSnapshot)
        .filter(ScreenerSnapshot.ai_prob_up.isnot(None))
        .order_by(ScreenerSnapshot.ai_prob_up.desc())
        .limit(TOP_K)
        .all()
    )
    for rank, snap in enumerate(top, start=1):
        db.add(
            PickLog(
                as_of_date=as_of,
                symbol=snap.symbol,
                prob=snap.ai_prob_up,
                rank=rank,
                horizon_days=active.horizon_days,
                model_version=active.version,
                source="live",
            )
        )
    db.commit()
    settle_open_picks(db)
    return f"logged {len(top)} live picks for {as_of}"


def settle_open_picks(db: Session) -> int:
    """Fill realized_return/spy_return for live picks whose horizon has elapsed."""
    open_picks = db.query(PickLog).filter(
        PickLog.source == "live", PickLog.realized_return.is_(None)
    ).all()
    settled = 0
    bars_cache: dict[str, pd.DataFrame] = {}
    for pick in open_picks:
        bars = bars_cache.get(pick.symbol)
        if bars is None:
            bars = load_bars(db, pick.symbol)
            bars_cache[pick.symbol] = bars
        if bars.empty or pick.as_of_date not in set(bars.index):
            continue
        start_pos = bars.index.get_loc(pick.as_of_date)
        end_pos = start_pos + pick.horizon_days
        if end_pos >= len(bars):
            continue  # horizon not elapsed yet
        pick.realized_return = float(bars["close"].iloc[end_pos] / bars["close"].iloc[start_pos] - 1)
        pick.spy_return = _spy_forward_return(db, pick.as_of_date, pick.horizon_days)
        settled += 1
    if settled:
        db.commit()
    return settled


def get_track_record(db: Session, recent_periods: int = 12) -> dict:
    """Summary stats + recent rebalance periods with their picks and outcomes."""
    picks = db.query(PickLog).order_by(PickLog.as_of_date, PickLog.rank).all()
    if not picks:
        return {"available": False}

    closed = [p for p in picks if p.realized_return is not None]
    by_date: dict[date, list[PickLog]] = {}
    for p in picks:
        by_date.setdefault(p.as_of_date, []).append(p)

    periods = []
    for d in sorted(by_date.keys()):
        group = by_date[d]
        realized = [p.realized_return for p in group if p.realized_return is not None]
        spy_vals = [p.spy_return for p in group if p.spy_return is not None]
        periods.append(
            {
                "date": str(d),
                "n_picks": len(group),
                "source": group[0].source,
                "avg_return": float(sum(realized) / len(realized)) if realized else None,
                "spy_return": float(sum(spy_vals) / len(spy_vals)) if spy_vals else None,
                "settled": len(realized) > 0,
                "picks": [
                    {"symbol": p.symbol, "prob": p.prob, "realized_return": p.realized_return}
                    for p in sorted(group, key=lambda x: x.rank)
                ],
            }
        )

    avg_return = sum(p.realized_return for p in closed) / len(closed) if closed else None
    spy_closed = [p.spy_return for p in closed if p.spy_return is not None]
    avg_spy = sum(spy_closed) / len(spy_closed) if spy_closed else None
    hit_rate = (
        sum(1 for p in closed if p.realized_return > 0) / len(closed) if closed else None
    )

    # Settled periods, chronological, for the equity curve and significance test.
    settled_periods = [p for p in periods if p["settled"]]
    equity_curve, strat, spy = [], 1.0, 1.0
    period_edges = []
    for p in settled_periods:
        strat *= 1 + (p["avg_return"] or 0.0)
        spy *= 1 + (p["spy_return"] or 0.0)
        equity_curve.append({"date": p["date"], "strategy": strat, "spy": spy})
        if p["avg_return"] is not None and p["spy_return"] is not None:
            period_edges.append(p["avg_return"] - p["spy_return"])

    from app.ml.stats import bootstrap_mean_ci

    significance = bootstrap_mean_ci(period_edges)

    return {
        "available": True,
        "model_version": picks[-1].model_version,
        "horizon_days": picks[-1].horizon_days,
        "top_k": TOP_K,
        "n_periods": len(by_date),
        "n_picks": len(picks),
        "n_settled": len(closed),
        "avg_pick_return": avg_return,
        "avg_spy_return": avg_spy,
        "edge": (avg_return - avg_spy) if (avg_return is not None and avg_spy is not None) else None,
        "hit_rate": hit_rate,
        "significance": significance,  # bootstrap CI + p-value + t-stat on per-period edge
        "equity_curve": equity_curve,
        "start": periods[0]["date"],
        "end": periods[-1]["date"],
        "periods": periods[-recent_periods:][::-1],  # most recent first
    }
