from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class SnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    name: str | None = None
    sector: str | None = None
    as_of_date: date
    price: float | None = None
    change_1d: float | None = None
    change_1w: float | None = None
    change_1m: float | None = None
    change_ytd: float | None = None
    avg_volume_20: float | None = None
    rsi_14: float | None = None
    pct_from_52w_high: float | None = None
    pct_from_52w_low: float | None = None
    market_cap: float | None = None
    pe_ratio: float | None = None
    ai_prob_up: float | None = None
    ai_model_version: str | None = None


class ScreenerResponse(BaseModel):
    results: list[SnapshotOut]
    total: int
    as_of_date: date | None = None


class ScreenerParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_price: float | None = None
    max_price: float | None = None
    min_avg_volume: float | None = None
    min_market_cap: float | None = None
    max_market_cap: float | None = None
    min_pe: float | None = None
    max_pe: float | None = None
    min_rsi: float | None = None
    max_rsi: float | None = None
    min_change_1d: float | None = None
    max_change_1d: float | None = None
    min_change_1w: float | None = None
    max_change_1w: float | None = None
    min_change_1m: float | None = None
    max_change_1m: float | None = None
    min_change_ytd: float | None = None
    max_change_ytd: float | None = None
    min_pct_from_52w_high: float | None = None
    max_pct_from_52w_high: float | None = None
    min_ai_prob: float | None = Field(default=None, ge=0, le=1)
    sector: str | None = None
    sort_by: str | None = None
    sort_dir: str | None = Field(default="desc", pattern="^(asc|desc)$")
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class BarOut(BaseModel):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float


class HistoryResponse(BaseModel):
    symbol: str
    range: str
    bars: list[BarOut]


class StockDetail(BaseModel):
    snapshot: SnapshotOut
    industry: str | None = None
    bar_count: int
    first_bar_date: date | None = None
    in_watchlist: bool


class IndicatorsOut(BaseModel):
    symbol: str
    as_of_date: date
    indicators: dict[str, float | None]


class FeatureContribution(BaseModel):
    feature: str
    label: str
    value: float | None = None
    contribution: float


class PredictionOut(BaseModel):
    model_available: bool
    symbol: str | None = None
    prob_up: float | None = None
    direction: str | None = None
    horizon_days: int | None = None
    model_version: str | None = None
    as_of_date: date | None = None
    top_contributions: list[FeatureContribution] = []


class ModelReportOut(BaseModel):
    model_available: bool
    version: str | None = None
    target: str | None = None
    trained_at: datetime | None = None
    horizon_days: int | None = None
    train_start: date | None = None
    train_end: date | None = None
    feature_count: int | None = None
    metrics: dict | None = None
    backtest: dict | None = None
    calibration: dict | None = None
    caveats: list[str] = []


class WatchlistItemIn(BaseModel):
    symbol: str
    buy_price: float | None = Field(default=None, gt=0)
    quantity: float | None = Field(default=None, gt=0)
    notes: str | None = None


class WatchlistItemUpdate(BaseModel):
    buy_price: float | None = Field(default=None, gt=0)
    quantity: float | None = Field(default=None, gt=0)
    notes: str | None = None


class WatchlistItemOut(BaseModel):
    id: int
    symbol: str
    name: str | None = None
    buy_price: float | None = None
    quantity: float | None = None
    notes: str | None = None
    added_at: datetime
    current_price: float | None = None
    market_value: float | None = None
    gain_loss: float | None = None
    gain_loss_pct: float | None = None
    change_1d: float | None = None
    ai_prob_up: float | None = None


class WatchlistResponse(BaseModel):
    items: list[WatchlistItemOut]
    total_value: float | None = None
    total_cost: float | None = None
    total_gain_loss: float | None = None
    total_gain_loss_pct: float | None = None


class RefreshStatus(BaseModel):
    id: int | None = None
    kind: str | None = None
    status: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    detail: str | None = None


class SavedScreenIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    query: str = Field(max_length=1000)


class SavedScreenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    query: str
    created_at: datetime


class TrackRecordOut(BaseModel):
    available: bool
    model_version: str | None = None
    horizon_days: int | None = None
    top_k: int | None = None
    n_periods: int | None = None
    n_picks: int | None = None
    n_settled: int | None = None
    avg_pick_return: float | None = None
    avg_spy_return: float | None = None
    edge: float | None = None
    hit_rate: float | None = None
    start: str | None = None
    end: str | None = None
    periods: list[dict] = []


class MetaOut(BaseModel):
    universe_size: int
    sectors: list[str]
    data_as_of: date | None = None
    last_refresh: RefreshStatus | None = None
    model_available: bool
