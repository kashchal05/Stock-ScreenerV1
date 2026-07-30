"""Stage-2 cross-sectional features.

Stage-1 features (app/ml/features.py) are per-symbol time series. Cross-sectional
features rank each stock against the rest of the universe *on the same date*, which
is what a market-neutral, relative-performance model actually needs. Ranking within
a date uses only same-date data, so there is no lookahead.

Both training (dataset.py) and inference (build_latest_cross_section) call
add_cross_sectional_features, so the two paths cannot diverge (no train/serve skew).
"""

import logging

import pandas as pd

from app.ml.features import FEATURE_COLUMNS, FEATURE_LABELS

logger = logging.getLogger(__name__)

# Stage-1 columns that get a same-date percentile-rank counterpart. These are the
# signals with real cross-sectional meaning (momentum, trend, relative strength).
_RANK_SOURCES = {
    "mom_12_1": "xs_mom_12_1",
    "mom_6_1": "xs_mom_6_1",
    "ret_21d": "xs_ret_21d",
    "rsi_14": "xs_rsi_14",
    "vol_21d": "xs_vol_21d",
    "close_sma200_ratio": "xs_close_sma200_ratio",
    "rel_ret_21d": "xs_rel_ret_21d",
    "pos_52w": "xs_pos_52w",
}

XS_FEATURE_COLUMNS = list(_RANK_SOURCES.values())

XS_FEATURE_LABELS = {
    "xs_mom_12_1": "12-1 momentum rank",
    "xs_mom_6_1": "6-1 momentum rank",
    "xs_ret_21d": "1-month return rank",
    "xs_rsi_14": "RSI rank",
    "xs_vol_21d": "Volatility rank",
    "xs_close_sma200_ratio": "Trend (vs 200-day) rank",
    "xs_rel_ret_21d": "Relative-strength rank",
    "xs_pos_52w": "52-week position rank",
}

# The model's full feature set = Stage-1 (per-symbol) + Stage-2 (cross-sectional).
# This is the ordered list stored in the artifact and asserted at inference load.
MODEL_FEATURE_COLUMNS = FEATURE_COLUMNS + XS_FEATURE_COLUMNS
MODEL_FEATURE_LABELS = {**FEATURE_LABELS, **XS_FEATURE_LABELS}


def add_cross_sectional_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add xs_* percentile-rank columns to a pooled (symbol, date, features) frame.

    Rank is computed within each date across all symbols present that day, scaled
    to (0, 1]. NaN source values stay NaN (XGBoost handles them). Returns a new
    frame; input is not mutated.
    """
    out = df.copy()
    grouped = out.groupby("date", sort=False)
    for source, target in _RANK_SOURCES.items():
        out[target] = grouped[source].rank(pct=True)
    return out


def build_latest_cross_section(db, feature_columns: list[str]) -> pd.DataFrame:
    """Build the current-universe cross-section for inference.

    Loads every active symbol's bars, computes Stage-1 features' latest row, stacks
    them, and adds Stage-2 xs_* ranks — the same transformation training used, so a
    single stock's live features match what the screener scores.

    Returns a frame indexed by symbol with all `feature_columns`, plus an
    `as_of_date` column. Symbols without enough history are dropped.
    """
    # Imported here to avoid a circular import (services -> ml -> services).
    from app.ml.features import compute_features
    from app.services.market_data import load_bars
    from app.services.universe import BENCHMARK_SYMBOL, active_symbols

    spy = load_bars(db, BENCHMARK_SYMBOL)
    spy_close = spy["close"] if not spy.empty else None

    rows = []
    for symbol in active_symbols(db, include_benchmark=False):
        bars = load_bars(db, symbol)
        if len(bars) < 70:
            continue
        feats = compute_features(bars, spy_close=spy_close)
        last = feats.iloc[-1]
        row = {"symbol": symbol, "date": bars.index[-1]}
        row.update(last.to_dict())
        rows.append(row)

    if not rows:
        return pd.DataFrame(columns=["symbol", "date", *feature_columns])

    frame = pd.DataFrame(rows)
    frame = add_cross_sectional_features(frame)
    frame = frame.set_index("symbol")
    return frame
