"""Simple top-K long strategy backtest over walk-forward test predictions.

Every `horizon` trading days: rank that day's test-window predictions by
probability, go long the top K equal-weight, hold for the horizon. Chained
into an equity curve and compared against SPY buy-and-hold over the same span.

Honest-limitations (also surfaced in the UI): survivorship bias (universe is
CURRENT S&P 500 members), no transaction costs or slippage, delayed data.
"""

import numpy as np
import pandas as pd

TOP_K = 20

CAVEATS = [
    "Survivorship bias: the universe is today's S&P 500 members, so historical results are optimistic — losers that left the index are missing.",
    "No transaction costs, slippage, or taxes are modeled.",
    "Free market data is ~15 minutes delayed and daily-bar based.",
    "This is a modeling exercise, not investment advice.",
]


def _forward_returns(panel: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Actual H-day forward return per (symbol, date), from the label source data."""
    frames = []
    for symbol, group in panel.groupby("symbol"):
        group = group.sort_values("date").copy()
        group["fwd_ret"] = group["close"].shift(-horizon) / group["close"] - 1
        frames.append(group[["symbol", "date", "fwd_ret"]])
    return pd.concat(frames, ignore_index=True)


def run_backtest(
    fold_results: list[dict],
    closes: pd.DataFrame,
    spy_closes: pd.Series,
    horizon: int,
) -> dict:
    """closes: DataFrame with columns symbol, date, close (the raw panel closes).
    spy_closes: date-indexed SPY adjusted close.
    """
    fwd = _forward_returns(closes, horizon)
    predictions = pd.concat(
        [f["test_predictions"] for f in fold_results], ignore_index=True
    ).merge(fwd, on=["symbol", "date"], how="left")
    predictions = predictions.dropna(subset=["fwd_ret"])
    if predictions.empty:
        return {"error": "no overlapping forward returns"}

    trade_dates = sorted(predictions["date"].unique())
    equity = [1.0]
    curve_dates = [trade_dates[0]]
    hits = 0
    periods = 0
    i = 0
    while i < len(trade_dates):
        day = trade_dates[i]
        picks = predictions[predictions["date"] == day].nlargest(TOP_K, "prob")
        if not picks.empty:
            period_ret = float(picks["fwd_ret"].mean())
            equity.append(equity[-1] * (1 + period_ret))
            curve_dates.append(day)
            hits += int(period_ret > 0)
            periods += 1
        i += horizon  # step forward one holding period

    equity = np.array(equity)
    curve_dates = [pd.Timestamp(d) for d in curve_dates]

    spy = spy_closes.copy()
    spy.index = pd.to_datetime(spy.index)
    spy_curve = []
    spy_start = None
    for d in curve_dates:
        window = spy[spy.index <= d]
        if window.empty:
            spy_curve.append(None)
            continue
        if spy_start is None:
            spy_start = window.iloc[-1]
        spy_curve.append(float(window.iloc[-1] / spy_start))

    total_return = float(equity[-1] - 1)
    n_years = max((curve_dates[-1] - curve_dates[0]).days / 365.25, 1e-9)
    running_max = np.maximum.accumulate(equity)
    max_drawdown = float(np.min(equity / running_max - 1))

    return {
        "strategy": f"top-{TOP_K} by predicted probability, {horizon}-day rebalance, equal weight",
        "start": str(curve_dates[0].date()),
        "end": str(curve_dates[-1].date()),
        "total_return": total_return,
        "annualized_return": float((equity[-1]) ** (1 / n_years) - 1),
        "spy_total_return": float(spy_curve[-1] - 1) if spy_curve and spy_curve[-1] else None,
        "max_drawdown": max_drawdown,
        "hit_rate": float(hits / periods) if periods else None,
        "n_periods": periods,
        "equity_curve": [
            {"date": str(d.date()), "strategy": float(e), "spy": s}
            for d, e, s in zip(curve_dates, equity, spy_curve)
        ],
        "caveats": CAVEATS,
    }
