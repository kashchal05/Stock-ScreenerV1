import logging
from datetime import date, datetime, timedelta

import pandas as pd
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.config import settings
from app.models import DailyBar, Ticker
from app.providers import get_provider
from app.services.universe import active_symbols

logger = logging.getLogger(__name__)

MAX_FETCH_FAILURES = 3
FUNDAMENTALS_MAX_AGE_DAYS = 7


def _latest_dates(db: Session) -> dict[str, date]:
    rows = db.query(DailyBar.symbol, func.max(DailyBar.date)).group_by(DailyBar.symbol).all()
    return {symbol: latest for symbol, latest in rows}


def _upsert_bars(db: Session, symbol: str, frame: pd.DataFrame) -> int:
    records = [
        {
            "symbol": symbol,
            "date": bar_date,
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row["volume"]) if pd.notna(row["volume"]) else 0.0,
        }
        for bar_date, row in frame.iterrows()
        if pd.notna(row["close"])
    ]
    if not records:
        return 0
    # Dialect-aware upsert: both SQLite and Postgres support ON CONFLICT DO UPDATE.
    insert = sqlite_insert if db.bind.dialect.name == "sqlite" else pg_insert
    stmt = insert(DailyBar).values(records)
    stmt = stmt.on_conflict_do_update(
        index_elements=["symbol", "date"],
        set_={c: getattr(stmt.excluded, c) for c in ["open", "high", "low", "close", "volume"]},
    )
    db.execute(stmt)
    return len(records)


def refresh_bars(db: Session) -> str:
    """Incrementally fetch missing daily bars for all active tickers.

    Groups tickers by how far back they need data so backfills and daily
    top-ups run as separate batched downloads.
    """
    provider = get_provider()
    symbols = active_symbols(db)
    latest = _latest_dates(db)
    today = date.today()
    backfill_start = today - timedelta(days=settings.backfill_years * 365)

    groups: dict[date, list[str]] = {}
    for symbol in symbols:
        start = latest[symbol] + timedelta(days=1) if symbol in latest else backfill_start
        if start > today:
            continue  # already current
        groups.setdefault(start, []).append(symbol)

    updated, failed = 0, []
    for start, group_symbols in sorted(groups.items()):
        frames = provider.get_daily_bars(group_symbols, start=start, end=today)
        for symbol in group_symbols:
            ticker = db.get(Ticker, symbol)
            frame = frames.get(symbol)
            if frame is None or frame.empty:
                # No data may just mean no new trading day yet; only count as a
                # failure when the symbol has no bars at all (likely delisted).
                if symbol not in latest:
                    ticker.fetch_failures += 1
                    if ticker.fetch_failures >= MAX_FETCH_FAILURES:
                        ticker.is_active = False
                        logger.warning("Deactivated %s after %d failed fetches", symbol, ticker.fetch_failures)
                    failed.append(symbol)
                continue
            updated += 1
            ticker.fetch_failures = 0
            _upsert_bars(db, symbol, frame)
        db.commit()

    detail = f"{updated}/{len(symbols)} tickers updated"
    if failed:
        detail += f", {len(failed)} failures: {', '.join(failed[:10])}"
    return detail


def refresh_fundamentals(db: Session, max_age_days: int = FUNDAMENTALS_MAX_AGE_DAYS) -> str:
    """Update market cap / PE / sector for tickers with stale fundamentals.

    Hits yfinance per-ticker, so it's throttled by staleness — bar refreshes
    never wait on this path.
    """
    provider = get_provider()
    cutoff = datetime.utcnow() - timedelta(days=max_age_days)
    stale = (
        db.query(Ticker)
        .filter(
            Ticker.is_active.is_(True),
            (Ticker.fundamentals_updated_at.is_(None)) | (Ticker.fundamentals_updated_at < cutoff),
        )
        .all()
    )
    updated = 0
    for ticker in stale:
        f = provider.get_fundamentals(ticker.symbol)
        if f.market_cap is not None:
            ticker.market_cap = f.market_cap
        if f.pe_ratio is not None:
            ticker.pe_ratio = f.pe_ratio
        if f.sector and not ticker.sector:
            ticker.sector = f.sector
        if f.industry and not ticker.industry:
            ticker.industry = f.industry
        ticker.fundamentals_updated_at = datetime.utcnow()
        updated += 1
        if updated % 50 == 0:
            db.commit()
    db.commit()
    return f"fundamentals updated for {updated} tickers"


def load_bars(db: Session, symbol: str, start: date | None = None) -> pd.DataFrame:
    """Load cached bars for one symbol as a date-indexed OHLCV DataFrame."""
    query = db.query(DailyBar).filter(DailyBar.symbol == symbol)
    if start is not None:
        query = query.filter(DailyBar.date >= start)
    rows = query.order_by(DailyBar.date).all()
    if not rows:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    frame = pd.DataFrame(
        {
            "open": [r.open for r in rows],
            "high": [r.high for r in rows],
            "low": [r.low for r in rows],
            "close": [r.close for r in rows],
            "volume": [r.volume for r in rows],
        },
        index=pd.Index([r.date for r in rows], name="date"),
    )
    return frame
