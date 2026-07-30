"""Backtest the cross-sectional signal over the walk-forward test predictions.

Every `horizon` trading days, rank that day's predictions by probability and form
two portfolios:
- Long-only: hold the top-K equal-weight (the screener's headline strategy).
- Long-short: long top-K, short bottom-K equal-weight — market-neutral, so it
  isolates the cross-sectional edge from overall market direction.

Transaction costs are charged per rebalance. Reports total/annualized return,
Sharpe, volatility, max drawdown, hit rate, and the rank information coefficient
(the cleanest "is the signal real?" number). Predictions carry their own realized
forward return (fwd_ret) from the dataset, so nothing is recomputed here.
"""

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

TOP_K = 20
COST_PER_SIDE = 0.001  # 10 bps per side
PERIODS_PER_YEAR_BASE = 252

CAVEATS = [
    "Survivorship bias: the universe is today's S&P 500 members, so historical results are optimistic — losers that left the index are missing.",
    "Transaction costs are modeled crudely (10 bps/side on full rebalancing); real slippage and market impact vary.",
    "Free market data is ~15 minutes delayed and daily-bar based.",
    "Cross-sectional / market-neutral results do not include shorting costs or borrow availability.",
    "This is a modeling exercise, not investment advice.",
]


def _sharpe(period_returns: np.ndarray, periods_per_year: float) -> float | None:
    if len(period_returns) < 2 or period_returns.std() == 0:
        return None
    return float(period_returns.mean() / period_returns.std() * np.sqrt(periods_per_year))


def _curve_stats(period_returns: list[float], periods_per_year: float, years: float) -> dict:
    rets = np.array(period_returns)
    equity = np.concatenate([[1.0], np.cumprod(1 + rets)])
    running_max = np.maximum.accumulate(equity)
    max_dd = float(np.min(equity / running_max - 1)) if len(equity) > 1 else 0.0
    total = float(equity[-1] - 1)
    return {
        "total_return": total,
        "annualized_return": float(equity[-1] ** (1 / max(years, 1e-9)) - 1),
        "sharpe": _sharpe(rets, periods_per_year),
        "volatility": float(rets.std() * np.sqrt(periods_per_year)) if len(rets) > 1 else None,
        "max_drawdown": max_dd,
        "hit_rate": float(np.mean(rets > 0)) if len(rets) else None,
        "n_periods": len(rets),
        "equity": equity.tolist(),
    }


def _rank_ic(predictions: pd.DataFrame) -> float | None:
    ics = []
    for _, group in predictions.groupby("date"):
        if len(group) >= 10 and group["prob"].nunique() > 1 and group["fwd_ret"].nunique() > 1:
            ic, _ = spearmanr(group["prob"], group["fwd_ret"])
            if not np.isnan(ic):
                ics.append(ic)
    return float(np.mean(ics)) if ics else None


def run_backtest(fold_results: list[dict], spy_closes: pd.Series, horizon: int) -> dict:
    predictions = pd.concat([f["test_predictions"] for f in fold_results], ignore_index=True)
    if "fwd_ret" not in predictions:
        return {"error": "predictions missing forward returns"}
    predictions = predictions.dropna(subset=["fwd_ret"])
    if predictions.empty:
        return {"error": "no forward returns to backtest"}

    trade_dates = sorted(predictions["date"].unique())
    periods_per_year = PERIODS_PER_YEAR_BASE / horizon

    long_only, long_short, curve_dates = [], [], []
    i = 0
    while i < len(trade_dates):
        day = trade_dates[i]
        day_preds = predictions[predictions["date"] == day].sort_values("prob")
        if len(day_preds) >= 2 * TOP_K:
            longs = day_preds.tail(TOP_K)["fwd_ret"].mean()
            shorts = day_preds.head(TOP_K)["fwd_ret"].mean()
            # Long-only pays a round-trip cost; long-short pays it on both legs.
            long_only.append(float(longs - 2 * COST_PER_SIDE))
            long_short.append(float((longs - shorts) - 4 * COST_PER_SIDE))
            curve_dates.append(pd.Timestamp(day))
        i += horizon

    if not curve_dates:
        return {"error": "not enough breadth for top/bottom-K portfolios"}

    years = max((curve_dates[-1] - curve_dates[0]).days / 365.25, 1e-9)
    lo_stats = _curve_stats(long_only, periods_per_year, years)
    ls_stats = _curve_stats(long_short, periods_per_year, years)

    # SPY benchmark aligned to the same rebalance dates
    spy = spy_closes.copy()
    spy.index = pd.to_datetime(spy.index)
    spy_curve, spy_start = [], None
    for d in curve_dates:
        window = spy[spy.index <= d]
        if window.empty:
            spy_curve.append(None)
            continue
        if spy_start is None:
            spy_start = window.iloc[-1]
        spy_curve.append(float(window.iloc[-1] / spy_start))

    equity_curve = [
        {
            "date": str(d.date()),
            "long_only": lo,
            "long_short": ls,
            "spy": s,
        }
        for d, lo, ls, s in zip(curve_dates, lo_stats["equity"][1:], ls_stats["equity"][1:], spy_curve)
    ]

    return {
        "strategy": f"top/bottom-{TOP_K} by predicted probability, {horizon}-day rebalance, equal weight",
        "start": str(curve_dates[0].date()),
        "end": str(curve_dates[-1].date()),
        "horizon_days": horizon,
        "rank_ic": _rank_ic(predictions),
        "cost_per_side_bps": COST_PER_SIDE * 1e4,
        "spy_total_return": float(spy_curve[-1] - 1) if spy_curve and spy_curve[-1] else None,
        "long_only": {k: v for k, v in lo_stats.items() if k != "equity"},
        "long_short": {k: v for k, v in ls_stats.items() if k != "equity"},
        "equity_curve": equity_curve,
        "caveats": CAVEATS,
    }
