"""Builds the pooled training panel: one row per (symbol, date)."""

import logging

import pandas as pd
from sqlalchemy.orm import Session

from app.ml.features import FEATURE_COLUMNS, compute_features
from app.ml.labeling import compute_labels
from app.services.market_data import load_bars
from app.services.universe import BENCHMARK_SYMBOL, active_symbols

logger = logging.getLogger(__name__)

# Skip the warm-up rows where long-window features are all NaN anyway.
MIN_BARS = 70


def build_dataset(db: Session, horizon: int) -> pd.DataFrame:
    """Returns a DataFrame with columns: symbol, date, label, *FEATURE_COLUMNS.

    Rows with NaN labels (the last `horizon` rows per symbol) are kept out;
    rows with some NaN features are kept — XGBoost handles them natively.
    """
    spy = load_bars(db, BENCHMARK_SYMBOL)
    spy_close = spy["close"] if not spy.empty else None

    frames = []
    symbols = active_symbols(db, include_benchmark=False)
    for symbol in symbols:
        bars = load_bars(db, symbol)
        if len(bars) < MIN_BARS:
            continue
        features = compute_features(bars, spy_close=spy_close)
        features["label"] = compute_labels(bars["close"], horizon)
        features["symbol"] = symbol
        features = features.dropna(subset=["label"])
        # Drop warm-up rows where every feature is still NaN
        features = features.dropna(subset=FEATURE_COLUMNS, how="all")
        frames.append(features.reset_index())

    if not frames:
        return pd.DataFrame(columns=["symbol", "date", "label", *FEATURE_COLUMNS])
    panel = pd.concat(frames, ignore_index=True)
    panel["date"] = pd.to_datetime(panel["date"])
    logger.info("Built dataset: %d rows, %d symbols", len(panel), panel["symbol"].nunique())
    return panel[["symbol", "date", "label", *FEATURE_COLUMNS]]
