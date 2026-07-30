"""Prediction targets.

Everything here uses shift(-H), so a row's label depends strictly on future data
while its features depend only on past data. The last H rows per symbol have no
forward return and are left unlabeled (NaN) — excluded from training, and the
newest of them is exactly what live inference scores.

Two targets:
- compute_labels (absolute): 1 if the stock itself is up over the horizon.
- cross-sectional (the model's target): 1 if the stock beats the universe median
  forward return on its date. Assigned in dataset.py, which has the whole panel.
"""

import numpy as np
import pandas as pd


def compute_forward_returns(close: pd.Series, horizon: int) -> pd.Series:
    """H-day forward return: close(t+H)/close(t) - 1. NaN for the last H rows."""
    return close.shift(-horizon) / close - 1


def compute_labels(close: pd.Series, horizon: int) -> pd.Series:
    """Absolute up/down label (kept for reference and the absolute-target path)."""
    forward_return = compute_forward_returns(close, horizon)
    labels = pd.Series(np.nan, index=close.index)
    labels[forward_return > 0] = 1.0
    labels[forward_return <= 0] = 0.0
    return labels


def cross_sectional_labels(panel: pd.DataFrame, forward_col: str = "fwd_ret") -> pd.Series:
    """Label = 1 if a row's forward return beats its date's cross-sectional median.

    panel must have columns `date` and `forward_col`. Rows whose forward return is
    NaN (the unlabeled tail) get NaN. Balanced ~50/50 by construction, and
    market-neutral: a day when everything rises has as many 1s as 0s.
    """
    median_by_date = panel.groupby("date")[forward_col].transform("median")
    labels = pd.Series(np.nan, index=panel.index)
    valid = panel[forward_col].notna() & median_by_date.notna()
    labels[valid] = (panel.loc[valid, forward_col] > median_by_date[valid]).astype(float)
    return labels
