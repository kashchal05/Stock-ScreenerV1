"""Shared feature engineering.

This module is the single source of truth for indicator math. It is imported
by the screener snapshot builder, the training pipeline, the backtester, and
live inference — training and serving must compute features identically, so
indicators live here and nowhere else.

Every feature uses only rolling windows and non-negative shifts, so the value
at row t depends solely on data at or before t (no lookahead).
"""

import numpy as np
import pandas as pd

# Order matters: stored in the model artifact and asserted at inference load.
FEATURE_COLUMNS = [
    "ret_1d",
    "ret_5d",
    "ret_10d",
    "ret_21d",
    "ret_63d",
    "rsi_14",
    "macd_line_norm",
    "macd_hist_norm",
    "close_sma20_ratio",
    "close_sma50_ratio",
    "close_sma200_ratio",
    "sma20_sma50_ratio",
    "vol_21d",
    "vol_63d",
    "atr14_norm",
    "vol_ratio_20",
    "vol_trend",
    "log_dollar_vol",
    "pos_52w",
    "pct_off_52w_high",
    "rel_ret_21d",
]

# Human-readable labels for prediction explanations.
FEATURE_LABELS = {
    "ret_1d": "1-day return",
    "ret_5d": "1-week return",
    "ret_10d": "2-week return",
    "ret_21d": "1-month return",
    "ret_63d": "3-month return",
    "rsi_14": "RSI (14)",
    "macd_line_norm": "MACD line",
    "macd_hist_norm": "MACD histogram",
    "close_sma20_ratio": "Price vs 20-day average",
    "close_sma50_ratio": "Price vs 50-day average",
    "close_sma200_ratio": "Price vs 200-day average",
    "sma20_sma50_ratio": "20-day vs 50-day trend",
    "vol_21d": "1-month volatility",
    "vol_63d": "3-month volatility",
    "atr14_norm": "Average true range",
    "vol_ratio_20": "Volume vs 20-day average",
    "vol_trend": "Volume trend",
    "log_dollar_vol": "Dollar volume",
    "pos_52w": "Position in 52-week range",
    "pct_off_52w_high": "Distance from 52-week high",
    "rel_ret_21d": "1-month return vs S&P 500",
}


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, min_periods=period).mean()
    # loss == 0 -> rs = inf -> RSI = 100 (correct limit); 0/0 stays NaN
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = gain / loss
    return 100 - 100 / (1 + rs)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = close.ewm(span=fast, min_periods=fast).mean()
    ema_slow = close.ewm(span=slow, min_periods=slow).mean()
    line = ema_fast - ema_slow
    signal_line = line.ewm(span=signal, min_periods=signal).mean()
    return line, line - signal_line


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period).mean()


def compute_features(df: pd.DataFrame, spy_close: pd.Series | None = None) -> pd.DataFrame:
    """Compute the full feature frame for one symbol.

    df: DataFrame indexed by date with columns open/high/low/close/volume
        (close adjusted), sorted ascending.
    spy_close: optional SPY adjusted-close series (date-indexed) for the
        market-relative feature; if None, rel_ret_21d is NaN.
    """
    close, high, low, volume = df["close"], df["high"], df["low"], df["volume"]
    out = pd.DataFrame(index=df.index)

    for n, col in [(1, "ret_1d"), (5, "ret_5d"), (10, "ret_10d"), (21, "ret_21d"), (63, "ret_63d")]:
        out[col] = close.pct_change(n)

    out["rsi_14"] = rsi(close)

    macd_line, macd_hist = macd(close)
    out["macd_line_norm"] = macd_line / close
    out["macd_hist_norm"] = macd_hist / close

    sma20 = close.rolling(20, min_periods=20).mean()
    sma50 = close.rolling(50, min_periods=50).mean()
    sma200 = close.rolling(200, min_periods=200).mean()
    out["close_sma20_ratio"] = close / sma20 - 1
    out["close_sma50_ratio"] = close / sma50 - 1
    out["close_sma200_ratio"] = close / sma200 - 1
    out["sma20_sma50_ratio"] = sma20 / sma50 - 1

    daily_ret = close.pct_change()
    out["vol_21d"] = daily_ret.rolling(21, min_periods=21).std()
    out["vol_63d"] = daily_ret.rolling(63, min_periods=63).std()
    out["atr14_norm"] = atr(high, low, close) / close

    avg_vol_20 = volume.rolling(20, min_periods=20).mean()
    out["vol_ratio_20"] = volume / avg_vol_20 - 1
    out["vol_trend"] = volume.rolling(5, min_periods=5).mean() / avg_vol_20 - 1
    out["log_dollar_vol"] = np.log1p(close * avg_vol_20)

    high_52w = close.rolling(252, min_periods=60).max()
    low_52w = close.rolling(252, min_periods=60).min()
    span = (high_52w - low_52w).replace(0, np.nan)
    out["pos_52w"] = (close - low_52w) / span
    out["pct_off_52w_high"] = close / high_52w - 1

    if spy_close is not None:
        spy_ret_21d = spy_close.pct_change(21).reindex(df.index)
        out["rel_ret_21d"] = out["ret_21d"] - spy_ret_21d
    else:
        out["rel_ret_21d"] = np.nan

    return out
