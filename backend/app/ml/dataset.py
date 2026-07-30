"""Builds the pooled training panel: one row per (symbol, date).

Pipeline: per-symbol Stage-1 features + forward returns -> pool across the whole
universe -> Stage-2 cross-sectional rank features -> cross-sectional labels
(beat the same-day universe median). The forward-return column is retained so the
backtester can reuse it without recomputing.
"""

import logging

import pandas as pd
from sqlalchemy.orm import Session

from app.ml.cross_section import MODEL_FEATURE_COLUMNS, add_cross_sectional_features
from app.ml.features import FEATURE_COLUMNS, compute_features
from app.ml.labeling import compute_forward_returns, cross_sectional_labels
from app.services.market_data import load_bars
from app.services.universe import BENCHMARK_SYMBOL, active_symbols

logger = logging.getLogger(__name__)

# Skip the warm-up rows where long-window features are all NaN anyway.
MIN_BARS = 70


def build_dataset(db: Session, horizon: int) -> pd.DataFrame:
    """Returns a DataFrame with columns:
    symbol, date, label, fwd_ret, close, *MODEL_FEATURE_COLUMNS.

    Rows with NaN labels (the last `horizon` rows per symbol) are dropped; rows with
    some NaN features are kept — XGBoost handles them natively.
    """
    spy = load_bars(db, BENCHMARK_SYMBOL)
    spy_close = spy["close"] if not spy.empty else None

    frames = []
    for symbol in active_symbols(db, include_benchmark=False):
        bars = load_bars(db, symbol)
        if len(bars) < MIN_BARS:
            continue
        features = compute_features(bars, spy_close=spy_close)
        features["fwd_ret"] = compute_forward_returns(bars["close"], horizon)
        features["close"] = bars["close"]
        features["symbol"] = symbol
        # Drop warm-up rows where every Stage-1 feature is still NaN
        features = features.dropna(subset=FEATURE_COLUMNS, how="all")
        frames.append(features.reset_index())

    if not frames:
        return pd.DataFrame(columns=["symbol", "date", "label", "fwd_ret", "close", *MODEL_FEATURE_COLUMNS])

    panel = pd.concat(frames, ignore_index=True)
    panel["date"] = pd.to_datetime(panel["date"])

    # Stage-2: cross-sectional ranks within each date, then cross-sectional labels.
    panel = add_cross_sectional_features(panel)
    panel["label"] = cross_sectional_labels(panel, forward_col="fwd_ret")
    panel = panel.dropna(subset=["label"])

    logger.info(
        "Built dataset: %d rows, %d symbols, label mean %.4f",
        len(panel),
        panel["symbol"].nunique(),
        panel["label"].mean(),
    )
    return panel[["symbol", "date", "label", "fwd_ret", "close", *MODEL_FEATURE_COLUMNS]]
