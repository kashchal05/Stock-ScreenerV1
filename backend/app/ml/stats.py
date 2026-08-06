"""Small statistics helpers for validating strategy performance honestly.

Used by the track record and model report to answer "is this edge real, or luck?"
"""

import numpy as np
from scipy import stats as sp_stats


def bootstrap_mean_ci(
    values: list[float], n_boot: int = 10000, conf: float = 0.95, seed: int = 7
) -> dict:
    """Bootstrap CI + two-sided p-value for the mean of `values` vs 0.

    Bootstrap at the sample level provided (e.g. per-rebalance-period edges, which
    respects the fact that picks within a period are correlated). Returns mean, the
    conf-level CI, a two-sided p-value against 0, and the t-statistic.
    """
    arr = np.asarray([v for v in values if v is not None], dtype=float)
    if len(arr) < 3:
        return {"mean": None, "ci_low": None, "ci_high": None, "p_value": None, "t_stat": None, "n": int(len(arr))}

    rng = np.random.default_rng(seed)
    boot_means = arr[rng.integers(0, len(arr), size=(n_boot, len(arr)))].mean(axis=1)
    lo = float(np.percentile(boot_means, (1 - conf) / 2 * 100))
    hi = float(np.percentile(boot_means, (1 + conf) / 2 * 100))
    # two-sided p-value: how often bootstrap means fall on the other side of 0
    mean = float(arr.mean())
    p = 2 * min(np.mean(boot_means <= 0), np.mean(boot_means >= 0))
    se = arr.std(ddof=1) / np.sqrt(len(arr))
    t_stat = float(mean / se) if se > 0 else None
    return {
        "mean": mean,
        "ci_low": lo,
        "ci_high": hi,
        "p_value": float(min(p, 1.0)),
        "t_stat": t_stat,
        "n": int(len(arr)),
    }


def probabilistic_sharpe_ratio(returns: list[float], benchmark_sr: float = 0.0) -> dict:
    """Probability that the true Sharpe ratio exceeds `benchmark_sr`, adjusting for
    sample length, skew, and kurtosis (Bailey & López de Prado). A PSR near 1 means
    the positive Sharpe is unlikely to be a fluke; near 0.5 means it's indistinct
    from the benchmark.
    """
    arr = np.asarray([r for r in returns if r is not None], dtype=float)
    n = len(arr)
    if n < 5 or arr.std(ddof=1) == 0:
        return {"sharpe": None, "psr": None, "n": int(n)}
    sr = arr.mean() / arr.std(ddof=1)  # per-period Sharpe
    skew = float(sp_stats.skew(arr))
    kurt = float(sp_stats.kurtosis(arr, fisher=False))  # non-excess kurtosis
    denom = np.sqrt(1 - skew * sr + (kurt - 1) / 4 * sr**2)
    if denom <= 0:
        return {"sharpe": float(sr), "psr": None, "n": int(n)}
    z = (sr - benchmark_sr) * np.sqrt(n - 1) / denom
    return {"sharpe": float(sr), "psr": float(sp_stats.norm.cdf(z)), "n": int(n)}
