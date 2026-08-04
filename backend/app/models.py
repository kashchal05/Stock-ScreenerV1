from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Ticker(Base):
    __tablename__ = "tickers"

    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str | None] = mapped_column(String)
    sector: Mapped[str | None] = mapped_column(String, index=True)
    industry: Mapped[str | None] = mapped_column(String)
    market_cap: Mapped[float | None] = mapped_column(Float)
    pe_ratio: Mapped[float | None] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    fetch_failures: Mapped[int] = mapped_column(Integer, default=0)
    fundamentals_updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class DailyBar(Base):
    __tablename__ = "daily_bars"
    __table_args__ = (
        UniqueConstraint("symbol", "date", name="uq_daily_bars_symbol_date"),
        Index("ix_daily_bars_symbol_date", "symbol", "date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("tickers.symbol"))
    date: Mapped[date] = mapped_column(Date)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)  # adjusted close
    volume: Mapped[float] = mapped_column(Float)


class ScreenerSnapshot(Base):
    __tablename__ = "screener_snapshots"

    symbol: Mapped[str] = mapped_column(ForeignKey("tickers.symbol"), primary_key=True)
    as_of_date: Mapped[date] = mapped_column(Date)
    price: Mapped[float | None] = mapped_column(Float)
    change_1d: Mapped[float | None] = mapped_column(Float)
    change_1w: Mapped[float | None] = mapped_column(Float)
    change_1m: Mapped[float | None] = mapped_column(Float)
    change_ytd: Mapped[float | None] = mapped_column(Float)
    avg_volume_20: Mapped[float | None] = mapped_column(Float)
    rsi_14: Mapped[float | None] = mapped_column(Float)
    pct_from_52w_high: Mapped[float | None] = mapped_column(Float)
    pct_from_52w_low: Mapped[float | None] = mapped_column(Float)
    market_cap: Mapped[float | None] = mapped_column(Float)
    pe_ratio: Mapped[float | None] = mapped_column(Float)
    sector: Mapped[str | None] = mapped_column(String, index=True)
    name: Mapped[str | None] = mapped_column(String)
    ai_prob_up: Mapped[float | None] = mapped_column(Float)
    ai_model_version: Mapped[str | None] = mapped_column(String)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("tickers.symbol"), index=True)
    buy_price: Mapped[float | None] = mapped_column(Float)
    quantity: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    added_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(String, unique=True)
    trained_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    horizon_days: Mapped[int] = mapped_column(Integer)
    train_start: Mapped[date | None] = mapped_column(Date)
    train_end: Mapped[date | None] = mapped_column(Date)
    feature_count: Mapped[int | None] = mapped_column(Integer)
    metrics_json: Mapped[str | None] = mapped_column(Text)
    backtest_json: Mapped[str | None] = mapped_column(Text)
    artifact_path: Mapped[str] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class RefreshRun(Base):
    __tablename__ = "refresh_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String)  # bars | fundamentals | snapshots | full
    status: Mapped[str] = mapped_column(String, default="running")  # running | succeeded | failed
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    detail: Mapped[str | None] = mapped_column(Text)


class SavedScreen(Base):
    __tablename__ = "saved_screens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    query: Mapped[str] = mapped_column(Text)  # URL query string, e.g. "min_rsi=70&sector=Energy"
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PickLog(Base):
    """Model track record: the top-K picks made on each rebalance date, and how
    they actually did. `source` is 'backtest' (seeded from leak-free walk-forward
    predictions) or 'live' (recorded going forward). realized_return is filled once
    the horizon has elapsed."""

    __tablename__ = "pick_log"
    __table_args__ = (
        UniqueConstraint("as_of_date", "symbol", "source", name="uq_pick_log_date_symbol_source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    as_of_date: Mapped[date] = mapped_column(Date, index=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("tickers.symbol"))
    prob: Mapped[float] = mapped_column(Float)
    rank: Mapped[int] = mapped_column(Integer)
    horizon_days: Mapped[int] = mapped_column(Integer)
    realized_return: Mapped[float | None] = mapped_column(Float)
    spy_return: Mapped[float | None] = mapped_column(Float)
    model_version: Mapped[str | None] = mapped_column(String)
    source: Mapped[str] = mapped_column(String, default="backtest")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
