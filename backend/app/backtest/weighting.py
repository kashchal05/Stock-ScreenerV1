"""Portfolio weighting schemes, shared by the backtest engine and the Plan builder.

- equal: 1/N across holdings.
- inverse_vol: weight proportional to 1/volatility, so each name contributes similar
  risk (a lightweight risk-parity). Names with a missing/zero vol get the average
  inverse weight; if no valid vols are available at all, falls back to equal weight.
"""

import numpy as np


def target_weights(symbols, vols: dict | None = None, scheme: str = "equal") -> dict:
    """Return {symbol: weight} summing to 1.0 for the given holdings."""
    symbols = list(symbols)
    n = len(symbols)
    if n == 0:
        return {}
    if scheme == "inverse_vol" and vols is not None:
        inv = {
            s: 1.0 / vols[s]
            for s in symbols
            if vols.get(s) is not None and np.isfinite(vols[s]) and vols[s] > 0
        }
        if inv:
            avg = float(np.mean(list(inv.values())))  # neutral fill for missing vols
            full = {s: inv.get(s, avg) for s in symbols}
            total = sum(full.values())
            return {s: w / total for s, w in full.items()}
    return {s: 1.0 / n for s in symbols}
