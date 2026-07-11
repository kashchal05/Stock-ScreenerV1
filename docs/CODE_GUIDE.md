# Code Guide

A file-by-file tour of the codebase, plus what every package does and why it was chosen. Read this top to bottom once and you'll understand the whole app.

## 1. The big picture

```
                    ┌────────────────────────  BACKEND (Python/FastAPI)  ───────────────────────┐
Yahoo Finance ──▶ provider adapter ──▶ daily_bars table ──┬──▶ screener_snapshots table ──▶ /api/screener
 (yfinance)      (app/providers/)      (SQLite cache)     │         ▲
                                                          │         │ ai_prob_up column
                                                          ▼         │
                                              feature engineering ──┴──▶ XGBoost model ──▶ /api/predictions
                                              (app/ml/features.py)       (artifacts/)
                    └───────────────────────────────────────────────────────────────────────────┘
                                                          │
                                                     JSON over HTTP
                                                          │
                    ┌──────────────  FRONTEND (React/Vite)  ──────────────┐
                    │  Screener page · Stock detail · Watchlist · Model   │
                    └──────────────────────────────────────────────────────┘
```

Two rules shape the whole design:

1. **Yahoo Finance is never called while serving a web request.** Downloads happen in background jobs or CLI scripts and land in SQLite. Every API request reads only from SQLite, so pages are fast and the app still works if Yahoo is down.
2. **One module owns the indicator math** (`app/ml/features.py`). The screener stats, the model's training data, and live predictions all import the same functions. If training computed RSI one way and serving computed it another way (a bug called *train/serve skew*), predictions would be silently garbage. Sharing one module makes that bug impossible.

## 2. Packages and why they're here

### Backend (`backend/requirements.txt`)

| Package | What it is | Why it's here |
|---|---|---|
| **fastapi** | Modern Python web framework | Defines the REST API. You declare a function + type hints; FastAPI handles routing, validation, and auto-generates docs at `/docs`. |
| **uvicorn** | ASGI web server | The actual server process that runs the FastAPI app. |
| **sqlalchemy** | Database toolkit / ORM | Lets us define tables as Python classes (`app/models.py`) and write queries in Python instead of raw SQL. Works with SQLite now, Postgres later, without code changes. |
| **pydantic** | Data validation | Every API request/response shape is a Pydantic model (`app/schemas.py`). Bad input (e.g. `limit=-5`) is rejected automatically with a clear error. |
| **pydantic-settings** | Config from env vars | Reads `.env` into a typed `Settings` object (`app/config.py`). This is what makes the app deployable without editing code. |
| **pandas** | DataFrames (tables in memory) | All price-series math: rolling averages, percent changes, joins. The core tool of the ML pipeline. |
| **numpy** | Fast numeric arrays | Underpins pandas; used directly for things like drawdown math. |
| **yfinance** | Unofficial Yahoo Finance client | The free data source. Quirky (see `providers/yfinance_provider.py`), so it's quarantined behind an adapter. |
| **lxml** | HTML/XML parser | Lets pandas parse the Wikipedia S&P 500 table (`pd.read_html`). |
| **xgboost** | Gradient-boosted decision trees | The ML model. Best-in-class on tabular data, handles missing values natively, and has built-in SHAP explanations — no extra package needed. Needs `brew install libomp` on macOS. |
| **scikit-learn** | ML utilities | Used only for metrics (`roc_auc_score`, `accuracy_score`). |
| **pytest / httpx** | Testing | `pytest` runs the tests; `httpx` would power FastAPI's test client if API-level tests are added. |

### Frontend (`frontend/package.json`)

| Package | What it is | Why it's here |
|---|---|---|
| **react / react-dom** | UI library | Components + state → the entire interface. |
| **react-router-dom** | Client-side routing | Maps URLs (`/stocks/AAPL`, `/watchlist`) to page components without full page reloads. Also powers URL-stored filters via `useSearchParams`. |
| **axios** | HTTP client | All API calls, wrapped in one file (`src/api.js`). |
| **recharts** | Charting library | The price chart and the backtest equity curve. Declarative: you describe the chart in JSX. |
| **date-fns** | Date utilities | Lightweight date formatting. |
| **vite** | Dev server + bundler | Instant hot reload in dev, optimized static build for production. Its proxy sends `/api/*` to the backend on port 8000 so the frontend never hardcodes a server address. |
| **eslint** (+ react plugins) | Linter | Catches bugs like misused React hooks. `npm run lint`. |

## 3. Backend walkthrough (`backend/app/`)

### Foundation

- **`config.py`** — a `Settings` class that reads environment variables (or `backend/.env`), with sensible defaults: database URL, artifacts directory, batch size, the 10-day prediction horizon. Everything configurable lives here; nothing is hardcoded elsewhere.
- **`database.py`** — creates the SQLAlchemy engine and `SessionLocal` factory, and the `get_db()` dependency that gives each request a database session and closes it afterward. Same pattern as the finance-tracker project.
- **`models.py`** — the six database tables:
  - `tickers` — the stock universe: symbol, name, sector, market cap, P/E, plus bookkeeping (`is_active`, `fetch_failures` for delisted-stock handling).
  - `daily_bars` — the big one (~625k rows): one row per stock per trading day with open/high/low/close/volume. `close` is *adjusted* close (splits/dividends baked in). Unique on (symbol, date) so re-downloading can't create duplicates.
  - `screener_snapshots` — one precomputed row per stock: current price, all the % changes, RSI, 52-week stats, AI probability. **The screener page queries only this table**, which is why filtering is instant — nothing is computed per request.
  - `watchlist_items` — your saved stocks with optional buy price/quantity/notes.
  - `model_versions` — a registry of trained models: version name, metrics JSON, backtest JSON, artifact path, and an `is_active` flag (exactly one active at a time).
  - `refresh_runs` — status rows for background refresh jobs (`running`/`succeeded`/`failed` + detail text) so the UI can poll progress.
- **`schemas.py`** — Pydantic classes describing every API input and output (e.g. `ScreenerParams` validates all filter query params; `PredictionOut` shapes the prediction response). This is the API's contract with the frontend.
- **`main.py`** — assembles the app: creates tables on startup, adds CORS middleware, plugs in the five routers.

### Data layer (`providers/` + `services/`)

- **`providers/base.py`** — an abstract `DataProvider` interface: `get_daily_bars()`, `get_fundamentals()`, `get_quote()`. This is the swap point: to move to a paid API later, write one new file implementing these three methods and change one env var.
- **`providers/yfinance_provider.py`** — the yfinance implementation, and the only file that knows yfinance's quirks:
  - Downloads in **batches of 100 tickers** with a polite sleep between batches (rate-limit safety).
  - Normalizes yfinance's inconsistent output — multi-ticker downloads return two-level (MultiIndex) columns, single-ticker downloads return flat columns — into one clean per-symbol DataFrame shape. No quirk escapes this file.
  - Always passes `auto_adjust=True` explicitly (the default has flipped between yfinance versions).
- **`services/universe.py`** — loads the S&P 500 list. Scrapes Wikipedia (with a custom User-Agent — Wikipedia blocks the default one), converts symbols like `BRK.B` → `BRK-B` (yfinance's format), writes a fallback CSV so the app still seeds offline, and always includes **SPY** (the S&P 500 ETF) as a benchmark ticker used by the ML features and backtest.
- **`services/market_data.py`** — the cache orchestrator:
  - `refresh_bars()` — for each ticker, finds the latest cached date and downloads only what's missing (first run = 5-year backfill, daily runs = one day). Uses SQLite *upsert* (`INSERT ... ON CONFLICT DO UPDATE`) so re-running is always safe. Tickers that repeatedly return nothing get deactivated (they're probably delisted) instead of crashing the batch.
  - `refresh_fundamentals()` — market cap / P/E / sector, fetched per-ticker (slow), so it's throttled: only tickers whose fundamentals are older than 7 days.
  - `load_bars()` — reads one stock's cached history into a DataFrame; used everywhere downstream.
- **`services/snapshots.py`** — rebuilds `screener_snapshots` after each refresh: loads each stock's bars, calls the shared feature module for RSI/52-week stats, computes the % changes, copies in fundamentals. ~500 rows rebuilt in seconds.
- **`services/screener.py`** — translates filter query params into a SQLAlchemy query. Note `RANGE_FILTERS`: every min/max filter is one row in a table instead of 20 near-identical `if` statements. `SORTABLE_COLUMNS` is a whitelist so nobody can sort by an arbitrary column name (a mild injection defense).
- **`services/portfolio.py`** — watchlist CRUD plus valuation math: joins each item to its snapshot for current price, computes market value / gain-loss, and portfolio totals.
- **`services/prediction.py`** — serving-side ML: lazily loads the active model into a cached singleton (reloading only when the active version changes), scores one symbol on demand, and batch-scores all snapshots after each refresh.
- **`services/refresh.py`** — the background job: bars → fundamentals → snapshots → AI scores, writing progress into `refresh_runs`. Runs in FastAPI's thread pool via `BackgroundTasks`; opens its own DB session because the request that triggered it is long gone.

### ML pipeline (`ml/`)

- **`features.py`** — *the most important file in the repo.* Hand-rolled implementations of RSI, MACD, ATR, moving-average ratios, volatility, volume trends, 52-week range position, and SPY-relative return — ~21 features total, each 3–6 lines of rolling-window pandas. Hand-rolled because the popular `pandas-ta` package is unmaintained (breaks with numpy 2) and because owning the math means training and serving *cannot* diverge. Every feature uses only past data (rolling windows / non-negative shifts); a unit test proves changing future rows can't change past features. `FEATURE_COLUMNS` (the ordered list) is stored inside each model artifact and checked at load time.
- **`labeling.py`** — the prediction target: `label = 1` if the close is higher 10 trading days later. Uses `shift(-10)`, so the *label* looks forward while *features* look backward — the last 10 rows per stock have no label and are excluded from training (the newest of them is exactly what live predictions score).
- **`dataset.py`** — stacks every stock's feature rows into one big training table (~618k rows × 21 features + symbol/date/label metadata).
- **`train.py`** — training and honest evaluation:
  - **Walk-forward validation**: 5 folds, each training on all data *before* a 6-month test window and testing on that window. Time-ordered splits, never random — random splits would let the model "see the future" and produce fake accuracy.
  - **Embargo**: additionally drops the last ~10 trading days of training data before each test window, because those rows' labels peek into the test period. This is the leak almost everyone misses.
  - Metrics per fold: accuracy, ROC-AUC, and hit rate on high-confidence picks — always alongside the **base rate** (stocks rise ~54% of 10-day windows, so 54% accuracy = zero skill).
  - Finally retrains on all labeled data for the production artifact.
- **`backtest.py`** — simulates "every 10 days, buy the model's top-20 picks, equal weight" across the walk-forward test windows and compares the equity curve to just holding SPY. Also defines the `CAVEATS` list shown in the UI (survivorship bias, no trading costs, delayed data, not advice).
- **`artifacts.py`** — saves each trained model as a versioned folder (`artifacts/v20260711_0023/`) containing the model in XGBoost's native JSON format (stable across versions, unlike pickle), the feature list, metadata, and backtest results; registers it in `model_versions` and flips `is_active`.
- **`inference.py`** — scores a stock's latest bar and explains it: XGBoost's built-in TreeSHAP (`pred_contribs=True`) returns exactly how much each feature pushed this prediction up or down; the top 5 become the signal bars in the UI.

### API routes (`routers/`)

| File | Endpoints |
|---|---|
| `screener.py` | `GET /api/screener` — validated filters → snapshot query |
| `stocks.py` | `GET /api/stocks/{symbol}`, `/history?range=`, `/indicators` |
| `predictions.py` | `GET /api/predictions/{symbol}`, `GET /api/model/report` |
| `watchlist.py` | `GET/POST /api/watchlist`, `PUT/DELETE /api/watchlist/{id}` |
| `admin.py` | `POST /api/admin/refresh` (409 if one is already running — SQLite allows one writer), `GET /api/admin/refresh/status`, `GET /api/meta`, `GET /api/health` |

Handlers are deliberately plain `def` (not `async def`): FastAPI runs them in a thread pool, so the pandas/DB work inside them can't stall the server's event loop.

### Scripts and tests

- **`scripts/seed_universe.py`** — one-time: load the S&P 500 list.
- **`scripts/refresh_data.py`** — CLI version of the full refresh; this is what a cron job would run in production.
- **`scripts/train_model.py`** — dataset → walk-forward eval (prints the fold table) → backtest → save artifact → re-score snapshots. Prints a warning if AUC looks suspiciously high (that means leakage, not brilliance).
- **`tests/test_features.py`** — indicator math vs hand-computed values; RSI bounds; **the no-lookahead property test**.
- **`tests/test_labeling.py`** — label alignment and the unlabeled tail.
- **`tests/test_screener.py`** — filter/sort/pagination logic against an in-memory SQLite database.

## 4. Frontend walkthrough (`frontend/src/`)

- **`main.jsx`** — entry point: mounts `<App>` inside a `BrowserRouter`.
- **`App.jsx`** — layout (navbar + page area) and the four routes.
- **`api.js`** — every backend call as a named function around one axios instance with `baseURL: '/api'`. Vite's dev proxy forwards `/api` to port 8000; in production a reverse proxy does the same job.
- **`utils/format.js`** — money/percent/compact-number formatters (`2.11T`, `+17.20%`) and the green/red CSS class helper. All formatting lives here so it's consistent everywhere.
- **`index.css`** — the entire design system: CSS variables for the dark theme (`--bg`, `--pos` green, `--neg` red…), panels, tables, forms, the modal, prediction-card bars. No CSS framework — it's ~300 lines and you own all of it.

### Pages (`pages/`)

- **`Screener.jsx`** — reads filters from the URL (`useSearchParams`), fetches results, renders `FilterPanel` + `ResultsTable` + pagination. Two patterns worth understanding:
  - *Derived loading state*: results are stored with the params-key they were fetched for; if the stored key ≠ current key, we're loading. This avoids setting state synchronously inside effects (a React anti-pattern the linter now flags).
  - The `FilterPanel` gets `key={paramsKey}`, so when the URL changes React remounts it with fresh state — simpler than syncing props to state.
- **`StockDetail.jsx`** — fetches the snapshot, then composes `PriceChart`, `StatsGrid`, `PredictionCard`, `IndicatorPanel`, and the watchlist button/modal.
- **`Watchlist.jsx`** — portfolio totals header + holdings table + edit/delete, with a confirm before removal.
- **`ModelReport.jsx`** — metric cards, the per-fold table, the equity-curve chart, and the honest-limitations box. Renders a "train a model first" empty state when no model exists.

### Components (`components/`)

- **`Navbar.jsx`** — links, the data-freshness badge, and the **Refresh** button: POSTs the refresh, then polls the status endpoint every 3s; when done it fires a `data-refreshed` window event that open pages listen for to reload their data.
- **`FilterPanel.jsx`** — the filter form. Percent filters are typed as whole numbers (5 = 5%) and converted to fractions (0.05) for the API — that mapping lives in one `PERCENT_FIELDS` set.
- **`ResultsTable.jsx`** — column definitions in one array; click a header to sort (server-side), click a row to navigate.
- **`PriceChart.jsx`** — Recharts `ComposedChart`: price area (green if up over the window, red if down) + volume bars on a hidden second axis + range tabs.
- **`StatsGrid.jsx` / `IndicatorPanel.jsx`** — stat cards and the indicator table with bullish/bearish/overbought tags.
- **`PredictionCard.jsx`** — the probability gauge and the five signed SHAP contribution bars (green = pushed up, red = pushed down), plus the not-investment-advice footer.
- **`EquityCurveChart.jsx`** — strategy-vs-SPY line chart for the model report.
- **`AddToWatchlistModal.jsx`** — one modal for both add and edit.
- **`LoadingSpinner` / `ErrorBanner` / `EmptyState`** — the three shared UI states every page uses.

## 5. Concepts glossary

- **Adjusted close** — price corrected for splits/dividends; the only sane series for computing returns.
- **RSI / MACD / ATR / SMA** — classic technical indicators: momentum oscillator (0–100), trend-following momentum (moving-average differences), average daily trading range, simple moving average.
- **Train/serve skew** — when the features a model sees in production are computed differently than in training. Prevented here by the shared `features.py` + an artifact-time feature-list assertion.
- **Lookahead bias / leakage** — accidentally letting information from the future into training. Prevented by rolling-window-only features, date-ordered splits, and the embargo.
- **Walk-forward validation** — evaluating on chronologically-later data than training, repeatedly, like the model would actually be used.
- **Base rate** — the accuracy of always predicting the most common class. The bar any real model must beat.
- **SHAP / TreeSHAP** — a method that fairly attributes a prediction to each input feature; XGBoost computes it natively.
- **Survivorship bias** — today's S&P 500 excludes past losers that were removed, which flatters any backtest run on it.
- **Upsert** — insert-or-update in one statement; makes data refreshes idempotent (safe to re-run).
