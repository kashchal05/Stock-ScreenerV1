"""Event-driven strategy backtest engine (Phase 1, rule-based, point-in-time).

`simulate` is a pure function over price/signal panels so it can be unit-tested with
synthetic data (see tests). `run_backtest` loads the cached universe and calls it.

Convention: on each rebalance date the signal is computed from data through that
date's close; the resulting equal-weight portfolio is entered at that close and held
until the next rebalance (a standard month-end-close convention). All Phase-1 signals
are slow-moving (momentum, RSI, trend), so entry-at-close carries no meaningful
same-bar advantage. Transaction costs are charged on the traded weight as the book
turns over.
"""

import logging
import threading

import numpy as np
import pandas as pd

from app.backtest.metrics import compute_metrics
from app.backtest.spec import AI_SIGNAL, SIGNAL_CHOICES, StrategySpec

logger = logging.getLogger(__name__)

MIN_BARS = 70
MAX_CURVE_POINTS = 300

# Universe cache: loading every symbol's bars is expensive, and they only change on
# a data refresh, so cache keyed by the latest bar date.
_lock = threading.Lock()
_cache: dict = {"key": None, "closes": None, "bars": None, "signals": {}}


def _load_universe(db):
    from app.models import DailyBar
    from app.services.universe import BENCHMARK_SYMBOL

    latest = db.query(DailyBar.date).order_by(DailyBar.date.desc()).limit(1).scalar()
    with _lock:
        if _cache["key"] == latest and _cache["closes"] is not None:
            return _cache["closes"], _cache["bars"]

        rows = db.query(
            DailyBar.symbol, DailyBar.date, DailyBar.open, DailyBar.high,
            DailyBar.low, DailyBar.close, DailyBar.volume,
        ).all()
        df = pd.DataFrame(rows, columns=["symbol", "date", "open", "high", "low", "close", "volume"])
        df["date"] = pd.to_datetime(df["date"])
        closes = df.pivot(index="date", columns="symbol", values="close").sort_index()
        bars = {}
        for symbol, g in df.groupby("symbol"):
            if symbol == BENCHMARK_SYMBOL or len(g) >= MIN_BARS:
                bars[symbol] = g.set_index("date")[["open", "high", "low", "close", "volume"]].sort_index()

        _cache.update({"key": latest, "closes": closes, "bars": bars, "signals": {}})
        return closes, bars


def _signal_panel(bars: dict, spy_close, feature: str, cache_key) -> pd.DataFrame:
    """Per-date, per-symbol values of one feature (point-in-time). Cached per (date, feature)."""
    from app.ml.features import compute_features
    from app.services.universe import BENCHMARK_SYMBOL

    ck = (cache_key, feature)
    with _lock:
        if ck in _cache["signals"]:
            return _cache["signals"][ck]

    cols = {}
    for symbol, sym_bars in bars.items():
        if symbol == BENCHMARK_SYMBOL or len(sym_bars) < MIN_BARS:
            continue
        feats = compute_features(sym_bars, spy_close=spy_close)
        cols[symbol] = feats[feature]
    panel = pd.DataFrame(cols).sort_index()
    with _lock:
        _cache["signals"][ck] = panel
    return panel


def _ai_signal_panel(db, cache_key) -> pd.DataFrame:
    """Out-of-sample walk-forward model scores, dates x symbols (from wf_predictions).
    Cached like rule signals. Empty if the panel hasn't been seeded."""
    from app.models import WfPrediction

    ck = (cache_key, AI_SIGNAL)
    with _lock:
        if ck in _cache["signals"]:
            return _cache["signals"][ck]

    rows = db.query(WfPrediction.date, WfPrediction.symbol, WfPrediction.prob).all()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["date", "symbol", "prob"])
    df["date"] = pd.to_datetime(df["date"])
    panel = df.pivot(index="date", columns="symbol", values="prob").sort_index()
    with _lock:
        _cache["signals"][ck] = panel
    return panel


def simulate(closes: pd.DataFrame, signal: pd.DataFrame, bench_close: pd.Series, spec: StrategySpec) -> dict:
    """Pure core. closes: dates x symbols. signal: dates x symbols (point-in-time).
    bench_close: benchmark close series. Returns a results dict or {"error": ...}."""
    idx = closes.index
    if spec.start is not None:
        idx = idx[idx >= pd.Timestamp(spec.start)]
    if spec.end is not None:
        idx = idx[idx <= pd.Timestamp(spec.end)]
    if len(idx) < spec.rebalance_days * 2:
        return {"error": "date range too short for this rebalance frequency"}

    closes = closes.loc[idx]
    signal = signal.reindex(index=idx, columns=closes.columns)
    daily_ret = closes.pct_change()

    valid_counts = signal.notna().sum(axis=1).to_numpy()
    starts = np.where(valid_counts >= spec.top_k)[0]
    if len(starts) == 0:
        return {"error": "not enough history for this signal and top-K"}
    rebal_pos = list(range(int(starts[0]), len(idx), spec.rebalance_days))
    rebal_dates = idx[rebal_pos]
    if len(rebal_dates) < 2:
        return {"error": "not enough rebalance periods in range"}

    ascending = spec.direction == "bottom"
    weights_at = pd.DataFrame(0.0, index=rebal_dates, columns=closes.columns)
    holdings = {}
    for t in rebal_dates:
        s = signal.loc[t].dropna()
        s = s[closes.loc[t, s.index].notna()]
        if s.empty:
            continue
        picks = s.sort_values(ascending=ascending).head(spec.top_k)
        weights_at.loc[t, picks.index] = 1.0 / len(picks)
        holdings[t] = picks

    # Effective weights: hold the target from each rebalance forward, applied with a
    # one-day lag (shift) so the signal bar isn't the first captured return beyond entry.
    weights = weights_at.reindex(idx).ffill().shift(1).fillna(0.0)
    port_daily = (weights * daily_ret).sum(axis=1)

    # Transaction costs charged on traded weight (both legs) when the book changes.
    traded = weights.diff().abs().sum(axis=1)
    port_daily = port_daily - traded * (spec.costs_bps / 10000.0)

    # Restrict to the invested window.
    first, last = rebal_dates[0], rebal_dates[-1]
    port_daily = port_daily.loc[first:last]
    bench_daily = bench_close.reindex(idx).pct_change().loc[first:last]

    # Per-period (rebalance-to-rebalance) compounded returns, for win rate + significance.
    equity = (1 + port_daily.fillna(0)).cumprod()
    bench_equity = (1 + bench_daily.fillna(0)).cumprod()
    period_returns, period_excess = [], []
    for a, b in zip(rebal_dates[:-1], rebal_dates[1:]):
        seg = equity.loc[a:b]
        bseg = bench_equity.loc[a:b]
        if len(seg) > 1 and len(bseg) > 1:
            pr = seg.iloc[-1] / seg.iloc[0] - 1
            br = bseg.iloc[-1] / bseg.iloc[0] - 1
            period_returns.append(float(pr))
            period_excess.append(float(pr - br))

    one_way_turnover = (traded.loc[first:last] / 2.0)
    avg_turnover = float(one_way_turnover[one_way_turnover > 0].mean()) if (one_way_turnover > 0).any() else 0.0

    metrics = compute_metrics(port_daily, bench_daily, period_returns, period_excess, avg_turnover)

    # Down-sample the equity curve for the chart.
    strat_curve = equity
    bench_curve = bench_equity.reindex(strat_curve.index).ffill()
    step = max(1, len(strat_curve) // MAX_CURVE_POINTS)
    curve = [
        {"date": d.strftime("%Y-%m-%d"), "strategy": float(s), "benchmark": float(b)}
        for d, s, b in zip(strat_curve.index[::step], strat_curve.values[::step], bench_curve.values[::step])
    ]

    latest_date = rebal_dates[-1]
    latest_holdings = [
        {"symbol": sym, "signal": float(val)}
        for sym, val in holdings.get(latest_date, pd.Series(dtype=float)).items()
    ]

    # Sanity flags: implausibly strong results almost always mean the biases below are
    # doing the work, not the signal. Surfaced in the UI so the numbers aren't trusted naively.
    warnings = []
    if (metrics.get("sharpe") or 0) > 2.5 or (metrics.get("cagr") or 0) > 0.4:
        warnings.append(
            "These results look implausibly strong — almost certainly inflated by "
            "survivorship bias (the universe is today's S&P 500 members) and a favorable "
            "regime. Treat as illustrative, not achievable."
        )

    return {
        "ok": True,
        "start": first.strftime("%Y-%m-%d"),
        "end": last.strftime("%Y-%m-%d"),
        "n_rebalances": len(rebal_dates),
        "final_value": spec.capital * float(equity.iloc[-1]),
        "metrics": metrics,
        "equity_curve": curve,
        "latest_holdings": latest_holdings,
        "latest_rebalance": latest_date.strftime("%Y-%m-%d"),
        "warnings": warnings,
    }


def run_backtest(db, spec: StrategySpec) -> dict:
    if spec.signal not in SIGNAL_CHOICES:
        return {"error": f"unknown signal: {spec.signal}"}
    from app.services.universe import BENCHMARK_SYMBOL

    closes, bars = _load_universe(db)
    if BENCHMARK_SYMBOL not in closes.columns:
        return {"error": "benchmark data not available — run a data refresh"}

    if spec.signal == AI_SIGNAL:
        signal = _ai_signal_panel(db, _cache["key"])
        if signal.empty:
            return {"error": "no walk-forward predictions yet — run scripts/seed_picks.py"}
    else:
        spy_close = bars.get(BENCHMARK_SYMBOL)
        spy_series = spy_close["close"] if spy_close is not None else None
        signal = _signal_panel(bars, spy_series, spec.signal, _cache["key"])

    universe_closes = closes.drop(columns=[BENCHMARK_SYMBOL], errors="ignore")
    result = simulate(universe_closes, signal, closes[BENCHMARK_SYMBOL], spec)
    if isinstance(result, dict) and result.get("ok"):
        result["out_of_sample"] = spec.signal == AI_SIGNAL
    return result
