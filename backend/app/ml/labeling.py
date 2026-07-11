"""Forward-return labels.

label(t) = 1 if close(t+H)/close(t) - 1 > 0 else 0, computed with shift(-H)
so the label at row t uses strictly-future data and features at row t use
only past data. The last H rows per symbol are unlabeled (NaN) — they are
excluded from training, and the newest of them is exactly what live
inference scores.
"""

import numpy as np
import pandas as pd


def compute_labels(close: pd.Series, horizon: int) -> pd.Series:
    forward_return = close.shift(-horizon) / close - 1
    labels = pd.Series(np.nan, index=close.index)
    labels[forward_return > 0] = 1.0
    labels[forward_return <= 0] = 0.0
    return labels
