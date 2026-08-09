"""Performance metrics for a backtested strategy vs its benchmark."""

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def _max_drawdown(equity: np.ndarray) -> float:
    running_max = np.maximum.accumulate(equity)
    return float(np.min(equity / running_max - 1)) if len(equity) else 0.0


def compute_metrics(
    port_daily: pd.Series,
    bench_daily: pd.Series,
    period_returns: list[float],
    period_excess: list[float],
    avg_turnover: float,
) -> dict:
    """port_daily / bench_daily: aligned daily return series. period_* : per-rebalance
    compounded returns (strategy, and strategy-minus-benchmark)."""
    from app.ml.stats import bootstrap_mean_ci

    daily = port_daily.dropna()
    if len(daily) < 2:
        return {"error": "not enough data to compute metrics"}

    equity = np.concatenate([[1.0], (1 + daily).cumprod().to_numpy()])
    n_years = max(len(daily) / TRADING_DAYS, 1e-9)
    total_return = float(equity[-1] - 1)
    cagr = float(equity[-1] ** (1 / n_years) - 1)
    vol = float(daily.std() * np.sqrt(TRADING_DAYS))
    sharpe = float(daily.mean() / daily.std() * np.sqrt(TRADING_DAYS)) if daily.std() > 0 else None
    downside = daily[daily < 0]
    sortino = (
        float(daily.mean() / downside.std() * np.sqrt(TRADING_DAYS))
        if len(downside) > 1 and downside.std() > 0
        else None
    )
    max_dd = _max_drawdown(equity)
    calmar = float(cagr / abs(max_dd)) if max_dd < 0 else None

    excess_daily = (port_daily - bench_daily).dropna()
    info_ratio = (
        float(excess_daily.mean() / excess_daily.std() * np.sqrt(TRADING_DAYS))
        if excess_daily.std() > 0
        else None
    )

    bench_equity = float((1 + bench_daily.dropna()).prod())
    win_rate = float(np.mean([r > 0 for r in period_returns])) if period_returns else None

    return {
        "total_return": total_return,
        "cagr": cagr,
        "benchmark_total_return": bench_equity - 1,
        "annual_volatility": vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": max_dd,
        "calmar": calmar,
        "information_ratio": info_ratio,
        "win_rate": win_rate,
        "avg_turnover": float(avg_turnover),
        "n_periods": len(period_returns),
        "significance": bootstrap_mean_ci(period_excess),
    }
