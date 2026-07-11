"""Score the latest bar of a symbol and explain the prediction.

Uses XGBoost's built-in TreeSHAP (pred_contribs=True) for exact per-feature
contributions — no separate shap dependency needed.
"""

import numpy as np
import pandas as pd
import xgboost as xgb

from app.ml.features import FEATURE_COLUMNS, FEATURE_LABELS, compute_features


def score_latest(
    booster: xgb.Booster,
    bars: pd.DataFrame,
    spy_close: pd.Series | None,
    top_n: int = 5,
) -> dict | None:
    """Returns {prob_up, as_of_date, contributions} or None if not enough data."""
    if len(bars) < 70:
        return None
    features = compute_features(bars, spy_close=spy_close)
    last = features[FEATURE_COLUMNS].iloc[[-1]]
    if last.isna().all(axis=None):
        return None

    dmatrix = xgb.DMatrix(last, feature_names=FEATURE_COLUMNS)
    prob = float(booster.predict(dmatrix)[0])
    # contribs: one value per feature + bias term (last column), in logit space
    contribs = booster.predict(dmatrix, pred_contribs=True)[0][:-1]

    order = np.argsort(-np.abs(contribs))[:top_n]
    contributions = []
    for idx in order:
        feature = FEATURE_COLUMNS[idx]
        raw_value = last.iloc[0, idx]
        contributions.append(
            {
                "feature": feature,
                "label": FEATURE_LABELS.get(feature, feature),
                "value": float(raw_value) if pd.notna(raw_value) else None,
                "contribution": float(contribs[idx]),
            }
        )

    return {
        "prob_up": prob,
        "as_of_date": bars.index[-1],
        "contributions": contributions,
    }
