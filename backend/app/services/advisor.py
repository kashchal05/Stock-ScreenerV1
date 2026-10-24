"""Build a concrete, dated action plan from a dollar amount.

Synthesizes the three things the app knows: the AI algorithm's current picks, its
validated out-of-sample track record, and the current market regime. Everything is
model-driven and heavily caveated — illustrative, not investment advice.
"""

import logging
import math
from datetime import date, timedelta

import numpy as np

from sqlalchemy.orm import Session

from app.backtest.weighting import target_weights
from app.models import ModelVersion, ScreenerSnapshot, Ticker
from app.services.market_data import load_bars
from app.services.universe import BENCHMARK_SYMBOL

logger = logging.getLogger(__name__)

TRADING_DAYS = 252
SECTOR_CAP = 3  # max holdings per sector, for basic diversification


def assess_market(db: Session) -> dict:
    """Read the current regime from SPY (trend + volatility) and market breadth."""
    spy = load_bars(db, BENCHMARK_SYMBOL)
    if spy.empty or len(spy) < 200:
        return {"available": False}

    close = spy["close"]
    last = float(close.iloc[-1])
    sma200 = float(close.rolling(200).mean().iloc[-1])
    trend_up = last > sma200
    pct_vs_sma200 = last / sma200 - 1

    daily = close.pct_change()
    vol_21 = float(daily.iloc[-21:].std() * np.sqrt(TRADING_DAYS))
    vol_median = float((daily.rolling(21).std() * np.sqrt(TRADING_DAYS)).median())
    high_vol = vol_21 > vol_median * 1.2

    # Breadth: fraction of the universe trading above its own 200-day average.
    breadth = None
    try:
        from app.backtest.engine import _cache, _load_universe, _signal_panel

        _, bars = _load_universe(db)
        spy_series = bars[BENCHMARK_SYMBOL]["close"] if BENCHMARK_SYMBOL in bars else None
        panel = _signal_panel(bars, spy_series, "close_sma200_ratio", _cache["key"])
        last_row = panel.iloc[-1].dropna()
        if len(last_row):
            breadth = float((last_row > 0).mean())
    except Exception:
        logger.exception("breadth computation failed")

    if trend_up and not high_vol:
        regime, stance = "Risk-on uptrend", "risk_on"
    elif trend_up and high_vol:
        regime, stance = "Volatile uptrend", "cautious"
    elif not trend_up and high_vol:
        regime, stance = "Risk-off / high volatility", "defensive"
    else:
        regime, stance = "Weak / rangebound", "cautious"

    return {
        "available": True,
        "as_of": str(close.index[-1]),
        "regime": regime,
        "stance": stance,
        "trend_up": trend_up,
        "spy_vs_200d": pct_vs_sma200,
        "volatility_annualized": vol_21,
        "volatility_vs_normal": vol_21 / vol_median if vol_median else None,
        "high_vol": high_vol,
        "breadth": breadth,
    }


def _stance_params(stance: str) -> dict:
    """How aggressive to be, by regime. Calmer regimes ride momentum equal-weight;
    volatile/weak regimes size by risk (inverse volatility) and hold cash."""
    return {
        "risk_on": {"positions": 18, "invested": 1.0, "require_uptrend": False, "weighting": "equal"},
        "cautious": {"positions": 14, "invested": 0.8, "require_uptrend": True, "weighting": "inverse_vol"},
        "defensive": {"positions": 10, "invested": 0.6, "require_uptrend": True, "weighting": "inverse_vol"},
    }[stance]


_WEIGHTING_LABELS = {"equal": "Equal weight", "inverse_vol": "Risk-based (inverse volatility)"}


def build_plan(db: Session, capital: float, num_positions: int | None = None) -> dict:
    active = db.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).first()
    if active is None:
        return {"available": False, "reason": "no_model"}

    market = assess_market(db)
    if not market.get("available"):
        return {"available": False, "reason": "no_market_data"}

    params = _stance_params(market["stance"])
    k = int(num_positions) if num_positions else params["positions"]
    invested_fraction = params["invested"]
    weighting = params["weighting"]

    # Point-in-time panels: the uptrend filter (defensive/cautious) and the per-name
    # volatilities used for risk-based sizing.
    uptrend_symbols = None
    vol_lookup: dict = {}
    try:
        from app.backtest.engine import _cache, _load_universe, _signal_panel

        _, bars = _load_universe(db)
        spy_series = bars[BENCHMARK_SYMBOL]["close"] if BENCHMARK_SYMBOL in bars else None
        if params["require_uptrend"]:
            trend = _signal_panel(bars, spy_series, "close_sma200_ratio", _cache["key"])
            last_row = trend.iloc[-1]
            uptrend_symbols = set(last_row[last_row > 0].dropna().index)
        if weighting == "inverse_vol":
            vol_panel = _signal_panel(bars, spy_series, "vol_21d", _cache["key"])
            vol_lookup = vol_panel.iloc[-1].dropna().to_dict()
    except Exception:
        logger.exception("plan panels failed")

    candidates = (
        db.query(ScreenerSnapshot)
        .filter(ScreenerSnapshot.ai_prob_up.isnot(None), ScreenerSnapshot.price.isnot(None))
        .order_by(ScreenerSnapshot.ai_prob_up.desc())
        .all()
    )

    invest_budget = capital * invested_fraction

    # 1) Select eligible holdings (top-K by AI score, uptrend + sector-cap filtered).
    #    Selection is independent of the weighting scheme.
    selected = []
    sector_counts: dict[str, int] = {}
    for snap in candidates:
        if len(selected) >= k:
            break
        if uptrend_symbols is not None and snap.symbol not in uptrend_symbols:
            continue
        sector = snap.sector or "Unknown"
        if sector_counts.get(sector, 0) >= SECTOR_CAP:
            continue
        if not snap.price or snap.price <= 0 or snap.price > invest_budget:
            continue  # can't afford even one share within the budget
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
        selected.append(snap)

    # 2) Target weights (equal or inverse-vol), then size in whole shares.
    weights = target_weights(
        [s.symbol for s in selected], vols=vol_lookup or None, scheme=weighting
    )
    picks = []
    spent = 0.0
    for snap in selected:
        target_dollar = invest_budget * weights.get(snap.symbol, 0.0)
        shares = math.floor(target_dollar / snap.price)
        if shares < 1:
            continue
        allocation = shares * snap.price
        spent += allocation
        picks.append(
            {
                "symbol": snap.symbol,
                "name": snap.name,
                "sector": snap.sector or "Unknown",
                "price": snap.price,
                "shares": shares,
                "allocation": allocation,
                "weight": None,  # filled after we know total spent
                "ai_prob_up": snap.ai_prob_up,
            }
        )

    for p in picks:
        p["weight"] = p["allocation"] / spent if spent else None

    horizon = active.horizon_days
    review_date = date.fromisoformat(market["as_of"]) + timedelta(days=int(horizon * 1.5))

    # Backtested expectation: the model's own out-of-sample track record.
    from app.services.picks import get_track_record

    tr = get_track_record(db)
    expectation = None
    if tr.get("available"):
        sig = tr.get("significance") or {}
        expectation = {
            "avg_return_per_period": tr.get("avg_pick_return"),
            "avg_spy_per_period": tr.get("avg_spy_return"),
            "edge_per_period": tr.get("edge"),
            "hit_rate": tr.get("hit_rate"),
            "n_periods": tr.get("n_periods"),
            "edge_significant": bool(sig.get("ci_low", 0) and sig["ci_low"] > 0),
            "edge_ci_low": sig.get("ci_low"),
            "edge_ci_high": sig.get("ci_high"),
        }

    return {
        "available": True,
        "capital": capital,
        "market": market,
        "strategy": {
            "approach": "AI cross-sectional model — buy the names most likely to beat the S&P 500 median",
            "stance": market["stance"],
            "num_positions": len(picks),
            "target_positions": k,
            "weighting": _WEIGHTING_LABELS.get(weighting, weighting),
            "invested_fraction": invested_fraction,
            "horizon_days": horizon,
            "review_date": str(review_date),
            "rationale": _rationale(market, params),
        },
        "picks": picks,
        "invested": spent,
        "cash_reserve": capital - spent,
        "model_version": active.version,
        "expectation": expectation,
        "caveats": [
            "This is a model-generated, illustrative plan — NOT investment advice. Consult a licensed advisor.",
            "The model's edge is real but modest and uncertain (out-of-sample rank IC ~0.03); most of any single month's result is noise.",
            "Backtested/track-record numbers are inflated by survivorship bias (today's S&P 500 members) and exclude taxes and real slippage.",
            "Data is delayed daily bars; prices shown are last close, not live quotes.",
        ],
    }


def _rationale(market: dict, params: dict) -> str:
    bits = []
    bits.append(
        f"SPY is {'above' if market['trend_up'] else 'below'} its 200-day average "
        f"({market['spy_vs_200d']:+.1%})"
    )
    if market.get("breadth") is not None:
        bits.append(f"{market['breadth']:.0%} of stocks are in an uptrend")
    bits.append(
        f"volatility is {'elevated' if market['high_vol'] else 'normal'} "
        f"({market['volatility_annualized']:.0%} annualized)"
    )
    tail = (
        "so the plan holds fewer names and keeps some cash."
        if params["invested"] < 1.0
        else "so the plan is fully invested across more names."
    )
    return "Because " + ", ".join(bits) + ", " + tail
