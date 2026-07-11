import logging
from datetime import date

import pandas as pd
from sqlalchemy.orm import Session

from app.ml.features import compute_features
from app.models import ScreenerSnapshot, Ticker
from app.services.market_data import load_bars
from app.services.universe import BENCHMARK_SYMBOL, active_symbols

logger = logging.getLogger(__name__)


def _pct_change_over(close: pd.Series, periods: int) -> float | None:
    if len(close) <= periods:
        return None
    value = close.iloc[-1] / close.iloc[-1 - periods] - 1
    return float(value) if pd.notna(value) else None


def _ytd_change(close: pd.Series) -> float | None:
    year_start = date(close.index[-1].year, 1, 1)
    prior = close[close.index < year_start]
    if prior.empty:
        return None
    value = close.iloc[-1] / prior.iloc[-1] - 1
    return float(value) if pd.notna(value) else None


def _clean(value) -> float | None:
    return float(value) if pd.notna(value) else None


def rebuild_snapshots(db: Session) -> str:
    symbols = active_symbols(db, include_benchmark=False)
    spy = load_bars(db, BENCHMARK_SYMBOL)
    spy_close = spy["close"] if not spy.empty else None

    built = 0
    for symbol in symbols:
        bars = load_bars(db, symbol)
        if bars.empty:
            continue
        close = bars["close"]
        features = compute_features(bars, spy_close=spy_close)
        last = features.iloc[-1]
        ticker = db.get(Ticker, symbol)

        snapshot = db.get(ScreenerSnapshot, symbol)
        if snapshot is None:
            snapshot = ScreenerSnapshot(symbol=symbol)
            db.add(snapshot)
        snapshot.as_of_date = bars.index[-1]
        snapshot.price = float(close.iloc[-1])
        snapshot.change_1d = _pct_change_over(close, 1)
        snapshot.change_1w = _pct_change_over(close, 5)
        snapshot.change_1m = _pct_change_over(close, 21)
        snapshot.change_ytd = _ytd_change(close)
        snapshot.avg_volume_20 = _clean(bars["volume"].rolling(20).mean().iloc[-1])
        snapshot.rsi_14 = _clean(last["rsi_14"])
        snapshot.pct_from_52w_high = _clean(last["pct_off_52w_high"])
        low_52w = close.rolling(252, min_periods=60).min().iloc[-1]
        snapshot.pct_from_52w_low = (
            float(close.iloc[-1] / low_52w - 1) if pd.notna(low_52w) and low_52w > 0 else None
        )
        snapshot.market_cap = ticker.market_cap
        snapshot.pe_ratio = ticker.pe_ratio
        snapshot.sector = ticker.sector
        snapshot.name = ticker.name
        built += 1
        if built % 100 == 0:
            db.commit()
    db.commit()
    return f"snapshots rebuilt for {built} tickers"
