# Stock Screener + AI Portfolio

A full-stack stock screener for the S&P 500 with an honestly-evaluated ML trend model.

- **Screen** 500+ stocks by price, volume, market cap, P/E, RSI, momentum (1d/1w/1m/YTD), 52-week range position, sector, and AI score — server-side filtering over a local SQLite cache, so queries return in milliseconds.
- **Stock detail pages** with price/volume charts (1M–5Y), key stats, and computed technical indicators.
- **AI prediction**: an XGBoost cross-sectional classifier estimates the probability a stock **beats the S&P 500 median** over the next 21 trading days, with per-prediction explanations (TreeSHAP) and a fully disclosed walk-forward evaluation.
- **Build a Plan**: turn a dollar amount into a dated buy list — AI picks sized for the current market regime, with the model's backtested track record as the expectation.
- **Backtest lab**: test any rule-based strategy or the AI itself (out-of-sample) over history — equity curve, Sharpe/Sortino/drawdown, and a significance test.
- **Watchlist/portfolio**: track holdings with cost basis, live valuation, P/L, and AI score.
- **One-click data refresh**: incremental daily-bar updates, fundamentals, snapshot rebuild, and AI re-scoring run as a background job with status polling.

**Stack**: FastAPI + SQLAlchemy + SQLite · pandas + XGBoost · React 19 + Vite + Recharts · yfinance (swappable data-provider adapter).

## Documentation

- **[docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md)** — the comprehensive, current from-scratch guide: every package, the full data pipeline, all 9 DB tables and ~22 endpoints, the ML + backtest + plan systems, the frontend, testing, and how to extend it. **Start here.**
- [docs/ABOUT.md](docs/ABOUT.md) — user-facing overview of what each page does.
- [docs/DEPLOY.md](docs/DEPLOY.md) — take it live: Alembic migrations, Postgres, Railway/Render, single- vs two-service, and the data-refresh cron.
- [docs/BACKTESTER_PLAN.md](docs/BACKTESTER_PLAN.md) — the backtester design doc.
- [docs/ROADMAP.md](docs/ROADMAP.md) · [docs/CHECKLIST.md](docs/CHECKLIST.md) — future work and status.
- [docs/CODE_GUIDE.md](docs/CODE_GUIDE.md) — an earlier, shorter tour (superseded by the Developer's Guide).

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

**Target (cross-sectional)**: the model predicts which stocks will **outperform the S&P 500 median** over the next 21 trading days — not whether a stock rises. Absolute direction is ~90% market noise; the cross-sectional target removes the market factor, is 50/50 balanced by construction, and is the standard quant formulation.

**Features (32)**: two stages, both used identically in training and serving (no skew). *Stage 1 (per-symbol)*: multi-horizon returns, RSI, MACD, SMA ratios, volatility, ATR, volume trends, 52-week range, SPY-relative return, and momentum factors (12-1 and 6-1 month momentum, risk-adjusted momentum). *Stage 2 (cross-sectional)*: each stock's percentile **rank within its date** for the signals that matter relatively. All rolling/shift-only — a unit test asserts mutating future rows can't change past features, and another asserts within-date ranks don't leak across dates.

**Labels**: 1 if a stock's 21-day forward return beats its date's universe median.

**Evaluation**: 5-fold walk-forward, expanding window, split strictly by date, with a 21-day embargo before each test window. The `/model` page reports the **rank information coefficient (IC)** — the correlation between the model's ranking and reality, the cleanest signal-quality measure — alongside ROC-AUC, accuracy vs base rate, isotonic-**calibrated** probabilities, and a backtest with transaction costs showing both long-only and market-neutral **long-short** curves (Sharpe, drawdown) vs SPY.

**Current honest result**: **rank IC ≈ +0.03** (4 of 5 folds positive) and a **market-neutral long-short Sharpe ≈ 0.5** after costs — a small but genuine edge, up from the previous absolute-direction model that had none (AUC 0.497). AUC is ~0.51, i.e. *not* suspiciously high, so this is real signal, not leakage. The flashy long-only backtest (beats SPY) is inflated by market beta and survivorship bias; the long-short number is the truthful measure of stock-picking skill. Equity prediction has a low ceiling — the point is a correct, leak-free pipeline whose metrics don't lie.

Known limitations, also disclosed in the UI:
- **Survivorship bias**: the universe is *today's* S&P 500 members, so backtests are optimistic.
- Transaction costs are modeled crudely (10 bps/side); shorting/borrow costs aren't included.
- yfinance data is ~15-minutes delayed, unofficial, and daily-bar based.
- **None of this is investment advice.**

## Architecture notes

```
yfinance → provider adapter → daily_bars (SQLite) → screener_snapshots → API → React
                                        ↘ Stage-1 features → Stage-2 cross-sectional
                                          ranks → XGBoost artifact → predictions
```

- `app/ml/features.py` (Stage 1) + `app/ml/cross_section.py` (Stage 2) are the single source of truth for feature math — imported by the snapshot builder, training, backtesting, and inference. The artifact stores its 32-feature list and inference asserts it matches, so training and serving can't diverge.
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
