from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.ml.features import FEATURE_LABELS, compute_features
from app.models import ScreenerSnapshot, Ticker, WatchlistItem
from app.schemas import BarOut, HistoryResponse, IndicatorsOut, SnapshotOut, StockDetail
from app.services.market_data import load_bars
from app.services.universe import normalize_symbol

router = APIRouter(prefix="/api/stocks", tags=["stocks"])

RANGE_DAYS = {"1m": 31, "3m": 92, "6m": 183, "1y": 366, "5y": 1830}

# Indicators surfaced on the detail page (subset of FEATURE_COLUMNS)
DETAIL_INDICATORS = [
    "rsi_14",
    "macd_line_norm",
    "macd_hist_norm",
    "close_sma20_ratio",
    "close_sma50_ratio",
    "close_sma200_ratio",
    "vol_21d",
    "atr14_norm",
    "vol_ratio_20",
    "pos_52w",
    "pct_off_52w_high",
    "ret_21d",
]


def _get_ticker(db: Session, symbol: str) -> Ticker:
    ticker = db.get(Ticker, normalize_symbol(symbol))
    if ticker is None:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")
    return ticker


@router.get("/{symbol}", response_model=StockDetail)
def stock_detail(symbol: str, db: Session = Depends(get_db)):
    ticker = _get_ticker(db, symbol)
    snapshot = db.get(ScreenerSnapshot, ticker.symbol)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail=f"No snapshot for {ticker.symbol} yet — run a data refresh first",
        )
    bars = load_bars(db, ticker.symbol)
    in_watchlist = (
        db.query(WatchlistItem).filter(WatchlistItem.symbol == ticker.symbol).first() is not None
    )
    return StockDetail(
        snapshot=SnapshotOut.model_validate(snapshot),
        industry=ticker.industry,
        bar_count=len(bars),
        first_bar_date=bars.index[0] if not bars.empty else None,
        in_watchlist=in_watchlist,
    )


@router.get("/{symbol}/history", response_model=HistoryResponse)
def history(
    symbol: str,
    range: str = Query("1y", pattern="^(1m|3m|6m|1y|5y)$"),
    db: Session = Depends(get_db),
):
    ticker = _get_ticker(db, symbol)
    start = date.today() - timedelta(days=RANGE_DAYS[range])
    bars = load_bars(db, ticker.symbol, start=start)
    return HistoryResponse(
        symbol=ticker.symbol,
        range=range,
        bars=[
            BarOut(
                date=bar_date,
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
            )
            for bar_date, row in bars.iterrows()
        ],
    )


@router.get("/{symbol}/indicators", response_model=IndicatorsOut)
def indicators(symbol: str, db: Session = Depends(get_db)):
    ticker = _get_ticker(db, symbol)
    bars = load_bars(db, ticker.symbol)
    if bars.empty:
        raise HTTPException(status_code=404, detail=f"No cached bars for {ticker.symbol}")
    features = compute_features(bars)
    last = features.iloc[-1]
    values = {
        name: (float(last[name]) if last.notna()[name] else None) for name in DETAIL_INDICATORS
    }
    return IndicatorsOut(symbol=ticker.symbol, as_of_date=bars.index[-1], indicators=values)
