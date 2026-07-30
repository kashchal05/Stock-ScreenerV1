"""Score a single stock from its (already cross-sectional) feature row and explain it.

The feature row must come from cross_section.build_latest_cross_section so it carries
the xs_* ranks computed against the current universe — scoring one stock in isolation
would omit those and skew the prediction. Uses XGBoost's built-in TreeSHAP
(pred_contribs=True) for exact per-feature contributions, no separate shap dependency.
"""

import numpy as np
import pandas as pd
import xgboost as xgb

from app.ml.cross_section import MODEL_FEATURE_COLUMNS, MODEL_FEATURE_LABELS


def apply_calibration(prob: float, calibration: dict | None) -> float:
    """Map a raw probability through the stored isotonic calibration (x/y knots)."""
    if not calibration:
        return prob
    return float(np.interp(prob, calibration["x"], calibration["y"]))


def score_row(
    booster: xgb.Booster,
    feature_row: pd.Series,
    calibration: dict | None = None,
    top_n: int = 5,
) -> dict | None:
    """Score one row of MODEL_FEATURE_COLUMNS. Returns prob/contributions or None."""
    values = feature_row.reindex(MODEL_FEATURE_COLUMNS)
    if values.isna().all():
        return None

    frame = values.to_frame().T.astype(float)
    dmatrix = xgb.DMatrix(frame, feature_names=MODEL_FEATURE_COLUMNS)
    raw_prob = float(booster.predict(dmatrix)[0])
    prob = apply_calibration(raw_prob, calibration)
    # contribs: one value per feature + bias term (last column), in logit space
    contribs = booster.predict(dmatrix, pred_contribs=True)[0][:-1]

    order = np.argsort(-np.abs(contribs))[:top_n]
    contributions = []
    for idx in order:
        feature = MODEL_FEATURE_COLUMNS[idx]
        raw_value = values.iloc[idx]
        contributions.append(
            {
                "feature": feature,
                "label": MODEL_FEATURE_LABELS.get(feature, feature),
                "value": float(raw_value) if pd.notna(raw_value) else None,
                "contribution": float(contribs[idx]),
            }
        )

    return {
        "prob_up": prob,
        "raw_prob": raw_prob,
        "contributions": contributions,
    }
