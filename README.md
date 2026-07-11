# Stock Screener + AI Portfolio

A full-stack stock screener for the S&P 500 with an honestly-evaluated ML trend model.

- **Screen** 500+ stocks by price, volume, market cap, P/E, RSI, momentum (1d/1w/1m/YTD), 52-week range position, sector, and AI score — server-side filtering over a local SQLite cache, so queries return in milliseconds.
- **Stock detail pages** with price/volume charts (1M–5Y), key stats, and computed technical indicators.
- **AI trend prediction**: an XGBoost classifier estimates the probability a stock closes higher in 10 trading days, with per-prediction explanations (TreeSHAP feature contributions) and a fully disclosed walk-forward evaluation.
- **Watchlist/portfolio**: track holdings with cost basis, live valuation, P/L, and AI score.
- **One-click data refresh**: incremental daily-bar updates, fundamentals, snapshot rebuild, and AI re-scoring run as a background job with status polling.

**Stack**: FastAPI + SQLAlchemy + SQLite · pandas + XGBoost · React 19 + Vite + Recharts · yfinance (swappable data-provider adapter).

## Setup

Prerequisites: Python 3.11+, Node 20+, and on macOS `brew install libomp` (required by XGBoost).

```bash
# Backend
cd backend
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/seed_universe.py     # S&P 500 universe (Wikipedia, CSV fallback)
.venv/bin/python scripts/refresh_data.py      # ~5-10 min first run: 5y of daily bars + fundamentals
.venv/bin/python scripts/train_model.py       # train + walk-forward evaluate + backtest

# Frontend
cd ../frontend
npm install

# Run both (from the repo root)
./start.sh          # backend on :8000, frontend on :5173
```

Configuration is env-driven (12-factor): copy `backend/.env.example` to `backend/.env` to override defaults (database URL, provider, batch sizes, horizon).

## How the ML works — and honest limitations

**Features (21)**: multi-horizon returns, RSI, MACD, price-vs-SMA(20/50/200) ratios, volatility (21/63d), ATR, volume trends, dollar volume, 52-week range position, and 1-month return relative to SPY. All computed with rolling windows only — a unit test asserts that mutating future rows cannot change past feature values.

**Labels**: 1 if the close is higher 10 trading days later, else 0.

**Evaluation**: 5-fold walk-forward with an expanding training window, split strictly by date, with a 10-day embargo before each test window so no training label's forward window overlaps test data. The report page shows accuracy *next to the base rate* (stocks drift up ~54% of the time, so accuracy alone flatters), ROC-AUC, hit rate on high-confidence picks, and a top-20 strategy backtest vs SPY buy-and-hold.

**Current honest result**: the model shows **no reliable predictive edge** (AUC ≈ 0.50, accuracy below base rate, backtest trails SPY). This is the expected outcome of a leak-free evaluation of technical features on daily data — the value of this project is the correct pipeline: shared feature engineering between training and serving (no train/serve skew), leakage-safe splits, and metrics that don't lie.

Known limitations, also disclosed in the UI:
- **Survivorship bias**: the universe is *today's* S&P 500 members, so backtests are optimistic.
- No transaction costs or slippage are modeled.
- yfinance data is ~15-minutes delayed, unofficial, and daily-bar based.
- **None of this is investment advice.**

## Architecture notes

```
yfinance → provider adapter → daily_bars (SQLite) → screener_snapshots → API → React
                                        ↘ features → XGBoost artifact → predictions
```

- `app/ml/features.py` is the single source of truth for indicator math — imported by the snapshot builder, training, backtesting, and inference. The artifact stores its feature list and inference asserts it matches.
- `app/providers/` isolates all yfinance quirks (MultiIndex normalization, batching, delisted-ticker handling) behind a `DataProvider` ABC; a paid API (Polygon/Finnhub) is a config change plus one new file.
- yfinance is never called in a request handler: refreshes run via FastAPI `BackgroundTasks` with a status row the UI polls, and all reads hit SQLite — if the data source is down, the app degrades to cached data.
- Model artifacts are versioned directories (`backend/artifacts/vYYYYMMDD_HHMM/`) using XGBoost's native JSON format, registered in a `model_versions` table with exactly one active version.

## Deployment (later)

The app is 12-factor ready: set `DATABASE_URL` (e.g. Postgres), serve `uvicorn app.main:app`, host `npm run build` output statically, and point a cron at `scripts/refresh_data.py` (e.g. Railway cron / GitHub Actions). Add Alembic before switching databases.

## Tests

```bash
cd backend && .venv/bin/python -m pytest tests/   # indicator math, no-lookahead, labeling, screener filters
cd frontend && npm run lint
```
