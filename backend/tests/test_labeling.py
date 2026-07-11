import numpy as np
import pandas as pd

from app.ml.labeling import compute_labels


def test_label_alignment():
    close = pd.Series([100, 101, 102, 99, 98, 97, 103, 104, 105, 90, 110, 111])
    labels = compute_labels(close, horizon=2)
    # label(t) compares close(t+2) vs close(t)
    assert labels.iloc[0] == 1.0  # 102 > 100
    assert labels.iloc[1] == 0.0  # 99 < 101
    assert labels.iloc[2] == 0.0  # 98 < 102


def test_last_horizon_rows_unlabeled():
    close = pd.Series(np.linspace(100, 120, 30))
    labels = compute_labels(close, horizon=10)
    assert labels.iloc[-10:].isna().all()
    assert labels.iloc[:-10].notna().all()


def test_flat_forward_return_is_down():
    close = pd.Series([100.0] * 20)
    labels = compute_labels(close, horizon=5)
    # zero forward return is labeled 0 (not up)
    assert (labels.dropna() == 0.0).all()
