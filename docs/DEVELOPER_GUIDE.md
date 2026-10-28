# Developer's Guide

A complete, from-scratch walkthrough of the Stock Screener + AI Portfolio app: what it is, every package, how the code is organized, how the whole pipeline fits together, and how each part works. Read this top to bottom and you'll understand the entire system.

> This is the authoritative, current guide. `CODE_GUIDE.md` is an older, shorter tour; `README.md` is the quickstart; `ABOUT.md` is the user-facing overview; `ROADMAP.md` / `CHECKLIST.md` track future work; `BACKTESTER_PLAN.md` is the backtester design doc.

---

## 1. What the app is (the one-paragraph mental model)

You keep a **local cache of ~5 years of daily prices** for every S&P 500 stock in SQLite. From that cache you (a) **screen** stocks by dozens of criteria, (b) compute an **AI score** — the probability each stock beats the S&P 500 median over the next 21 trading days — using a gradient-boosted model, (c) **backtest** any strategy (a rule or the AI itself) over history with honest statistics, (d) track the model's **live out-of-sample picks**, and (e) turn a **dollar amount into a dated buy list** that accounts for the current market regime. The guiding principle throughout is **honesty**: leak-free evaluation, disclosed survivorship bias, and metrics that don't flatter.

Two hard rules shape the entire codebase:

1. **yfinance is never called while serving a web request.** Downloads happen in background jobs / CLI scripts and land in SQLite. Every API request reads only SQLite, so pages are fast and the app still works if Yahoo is down.
2. **One module owns each piece of math.** Feature engineering lives in exactly one place (`ml/features.py` + `ml/cross_section.py`) used by training, snapshot-building, scoring, AND the backtester — so training and serving can never diverge (a bug called *train/serve skew*).

---

## 2. Tech stack — every package and why

### Backend (`backend/requirements.txt`)

| Package | Role | Why it's here |
|---|---|---|
| **fastapi** | Web framework | Declares the REST API from typed functions; auto-generates docs at `/docs`. |
| **uvicorn** | ASGI server | Runs the FastAPI app. |
| **sqlalchemy** (2.0) | ORM / DB toolkit | Tables as Python classes (`models.py`); queries in Python. Works with SQLite now, Postgres later, unchanged. |
| **pydantic** (2) | Validation | Every request/response shape (`schemas.py`, `backtest/spec.py`). Bad input is rejected with clear errors. |
| **pydantic-settings** | Config from env | `config.py` reads `.env` into a typed `Settings` — the key to being deployable without code edits. |
| **pandas** | DataFrames | All price-series math: rolling windows, pct-changes, pivots, joins. The core tool of the ML + backtest code. |
| **numpy** | Numeric arrays | Underpins pandas; direct use for drawdowns, equity curves, bootstrap. |
| **yfinance** | Market data | Free (unofficial) Yahoo Finance client — the only data source, quarantined behind an adapter. |
| **lxml** | HTML parser | Lets pandas parse the Wikipedia S&P 500 table. |
| **xgboost** (2.1) | ML model | Gradient-boosted trees — best-in-class on tabular data, handles NaN natively, and ships **TreeSHAP** for free explanations. Needs `brew install libomp` on macOS. |
| **scikit-learn** | ML utilities | Metrics (`roc_auc_score`, `accuracy_score`) and `IsotonicRegression` for probability calibration. |
| **scipy** | Stats | `spearmanr` (rank IC), `norm` (probabilistic Sharpe ratio). |
| **pytest** | Tests | 42 tests across 7 files. |
| **httpx** | Test client | Powers FastAPI's `TestClient` in `test_api.py`. |

### Frontend (`frontend/package.json`)

| Package | Role | Why it's here |
|---|---|---|
| **react / react-dom** (19) | UI library | Components + state → the whole interface. |
| **react-router-dom** (7) | Routing | Maps URLs to pages; URL-stored screener filters via `useSearchParams`. |
| **axios** | HTTP client | All API calls, wrapped in `src/api.js`. |
| **recharts** (3) | Charts | Price chart, equity curves, calibration curve. Declarative JSX charts. |
| **date-fns** | Dates | Lightweight date helpers. |
| **vite** (dev) | Dev server + bundler | Instant HMR in dev, optimized static build for prod. Proxies `/api` → `localhost:8000` so the frontend never hardcodes a host. |
| **eslint** (+ react plugins) | Linter | `npm run lint`; enforces React hook rules. |

**Not used (deliberately):** `pandas-ta`/`ta` (indicators hand-rolled — unmaintained + guarantees no skew), `shap` (XGBoost has TreeSHAP built in), Alembic (deferred to pre-deploy), Celery/APScheduler (refresh is on-demand locally).

---

## 3. Repository layout

```
stock-screener/
├── README.md  ABOUT / ROADMAP / CHECKLIST / CODE_GUIDE / BACKTESTER_PLAN / DEVELOPER_GUIDE (docs/)
├── start.sh                      # launches backend (uvicorn) + frontend (vite) together
├── .github/workflows/ci.yml      # CI: backend pytest + frontend lint & build on every push
├── backend/
│   ├── requirements.txt, .env.example
│   ├── data/sp500_fallback.csv   # offline S&P 500 list (fallback for the Wikipedia scrape)
│   ├── artifacts/                # trained model artifacts (gitignored)
│   ├── screener.db               # the SQLite cache (gitignored)
│   ├── scripts/                  # seed_universe · refresh_data · train_model · seed_picks
│   ├── tests/                    # 7 test files, 42 tests
│   └── app/
│       ├── main.py, config.py, database.py, models.py, schemas.py
│       ├── providers/            # base.py (ABC) + yfinance_provider.py
│       ├── services/             # universe, market_data, snapshots, screener, portfolio,
│       │                         #   prediction, refresh, picks, advisor
│       ├── ml/                   # features, cross_section, labeling, dataset, train,
│       │                         #   backtest, artifacts, inference, stats
│       ├── backtest/             # spec, engine, metrics, weighting  (the Backtest lab)
│       └── routers/              # screener, screens, search, stocks, predictions,
│                                 #   watchlist, track_record, backtest, plan, admin
└── frontend/
    └── src/
        ├── main.jsx, App.jsx, api.js, index.css
        ├── utils/                # format.js, theme.js
        ├── pages/                # Screener, Plan, StockDetail, Watchlist, Compare,
        │                         #   Backtest, TrackRecord, ModelReport
        └── components/           # Navbar, SearchBox, FilterPanel, ResultsTable,
                                  #   ScreenerPresets, SavedScreens, PriceChart, StatsGrid,
                                  #   IndicatorPanel, PredictionCard, EquityCurveChart,
                                  #   CalibrationChart, AddToWatchlistModal, + Loading/Error/Empty
```

---

## 4. Running it from scratch

**Prerequisites:** Python 3.11 (`/opt/homebrew/bin/python3.11` — the system 3.9 breaks on modern type syntax), Node 20+, and on macOS `brew install libomp` (XGBoost needs OpenMP).

```bash
# Backend
cd backend
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/seed_universe.py      # S&P 500 list -> tickers table
.venv/bin/python scripts/refresh_data.py       # ~5-10 min first run: 5y bars + fundamentals + snapshots
.venv/bin/python scripts/train_model.py         # train + walk-forward eval + backtest -> artifact
.venv/bin/python scripts/seed_picks.py          # seed the track record + wf_predictions (for AI backtest)

# Frontend
cd ../frontend && npm install

# Run both from repo root
./start.sh      # backend :8000, frontend :5173  ->  open http://localhost:5173
```

**The four CLI scripts** (in `backend/scripts/`):
- `seed_universe.py` — load the S&P 500 ticker list (Wikipedia scrape, CSV fallback). One-time.
- `refresh_data.py` — incremental bars → fundamentals → rebuild snapshots → AI-score → log live picks. The production cron entry point.
- `train_model.py` — build the dataset, walk-forward evaluate, calibrate, backtest, save the artifact, re-score snapshots.
- `seed_picks.py` — populate the model track record (`pick_log`) and the full out-of-sample prediction panel (`wf_predictions`) from leak-free walk-forward predictions.

**Config** (`config.py`, all env-overridable via `backend/.env`): `database_url` (default local SQLite), `artifacts_dir`, `data_provider` (`yfinance`), `cors_origins`, `yf_batch_size` (100), `backfill_years` (5), `prediction_horizon_days` (**21**).

---

## 5. End-to-end data flow (the whole pipeline on one page)

```
                    ┌──────────────────────── OFFLINE (scripts / background jobs) ───────────────────────┐
Yahoo Finance ─▶ providers/ ─▶ daily_bars ─┬─▶ services/snapshots ─▶ screener_snapshots ──┐
 (yfinance)      (adapter)     (SQLite)     │        (uses ml/features)                     │ ai_prob_up
                                            │                                               │ (filled by
                                            ├─▶ ml/dataset ─▶ ml/train (walk-forward) ──────┤  services/prediction)
                                            │     (features + cross_section + labeling)      │
                                            │                        │                      ▼
                                            │                        ├─▶ artifacts/ (XGBoost model + calibration)
                                            │                        └─▶ wf_predictions + pick_log (seed_picks)
                                            └──────────────────────────────────────────────┘
                    └───────────────────────────────────────────────────────────────────────────────────┘
                                                        │ (all reads hit SQLite only)
                    ┌─────────────────────────────── ONLINE (FastAPI, plain `def` handlers) ──────────────┐
  screener_snapshots ─▶ routers/screener, plan, track_record …   daily_bars ─▶ routers/stocks, backtest …
                                                        │  JSON over HTTP (Vite proxies /api → :8000)
                    ┌──────────────────────────────── FRONTEND (React / Vite) ───────────────────────────┐
     api.js ─▶ pages (Screener · Plan · Backtest · Track record · Stock detail · Watchlist · Compare · Model)
```

**A data refresh** (`services/refresh.py` → `execute_full_refresh`, triggered by the navbar button via `POST /api/admin/refresh` or by `refresh_data.py`) runs, in order:
1. `market_data.refresh_bars` — fetch only missing daily bars (incremental; 5y backfill on first run).
2. `market_data.refresh_fundamentals` — market cap / P/E / sector for stale tickers (throttled).
3. `snapshots.rebuild_snapshots` — recompute one `screener_snapshots` row per stock (price, % changes, RSI, 52-week stats…).
4. `prediction.score_all_snapshots` — fill `ai_prob_up` for every snapshot using the active model.
5. `picks.record_live_picks` — log today's top-20 AI picks to the track record (grows forward).

It runs in a background thread (FastAPI `BackgroundTasks`), writing progress to a `refresh_runs` row the UI polls. **Handlers are plain `def`** (not `async def`) so FastAPI runs them in a threadpool and the pandas/DB work can't stall the event loop.

---

## 6. Database schema (`app/models.py`) — all 9 tables

SQLite via `DATABASE_URL`; `Base.metadata.create_all` creates missing tables at startup (no Alembic yet — noted as a pre-deploy step).

| Table | Purpose | Key columns |
|---|---|---|
| **tickers** | Universe + slow fundamentals | `symbol` (PK, yfinance-normalized e.g. `BRK-B`), name, sector, industry, market_cap, pe_ratio, `is_active`, `fetch_failures` (delisted handling), fundamentals_updated_at |
| **daily_bars** | The OHLCV cache (~625k rows) | symbol, date (unique together), open/high/low/close/volume — `close` is **adjusted** close |
| **screener_snapshots** | One precomputed row/stock — what the screener & plan query | price, change_1d/1w/1m/ytd, avg_volume_20, rsi_14, pct_from_52w_high/low, market_cap, pe_ratio, sector, **ai_prob_up**, ai_model_version, as_of_date |
| **watchlist_items** | Saved holdings | symbol, buy_price?, quantity?, notes?, added_at |
| **model_versions** | Trained-model registry | version, trained_at, horizon_days, metrics_json, backtest_json, artifact_path, `is_active` (exactly one) |
| **refresh_runs** | Background-job status | kind, status (running/succeeded/failed), timestamps, detail |
| **saved_screens** | User's named screens | name (unique), query (URL query string), created_at |
| **pick_log** | Model track record | as_of_date, symbol, prob, rank, horizon_days, realized_return?, spy_return?, `source` (`backtest` seeded / `live`) |
| **wf_predictions** | Full out-of-sample scores (for the AI backtest) | date, symbol, prob (311k rows; seeded by `seed_picks.py`) |

Why both `screener_snapshots` (one row/stock, "now") and `daily_bars` (full history): the screener filters 500 precomputed rows in SQL (instant), while charts, the ML pipeline, and the backtester need the full history.

---

## 7. Backend deep dive

### 7.1 Foundation
- **`config.py`** — the typed `Settings` (env-driven). Nothing configurable is hardcoded elsewhere.
- **`database.py`** — SQLAlchemy engine, `SessionLocal`, and the `get_db()` request dependency (session per request, closed after).
- **`main.py`** — app factory: `create_all` on startup, CORS middleware, and `include_router` for all 10 routers.
- **`schemas.py`** — Pydantic request/response models (the API contract). Flexible `dict` fields are used where the shape is rich/evolving (model report metrics, backtest results, track-record periods).

### 7.2 Data provider (`providers/`) — the swap point
- **`base.py`** — `DataProvider` ABC: `get_daily_bars`, `get_fundamentals`, `get_quote`. To move to a paid API later (Polygon/Tiingo), write one new file and change one env var.
- **`yfinance_provider.py`** — the only file that knows yfinance's quirks: batches of 100 tickers with sleeps (rate limits); normalizes yfinance's inconsistent output (multi-ticker MultiIndex columns vs single-ticker flat columns) into one clean per-symbol shape; always passes `auto_adjust=True` explicitly (the default flips between versions). No quirk escapes this file.

### 7.3 Services (`services/`) — the orchestration layer
- **`universe.py`** — load the S&P 500 (Wikipedia via a custom User-Agent — the default UA 403s — with a CSV fallback); normalize symbols (`BRK.B`→`BRK-B`); always include **SPY** as the benchmark.
- **`market_data.py`** — the cache orchestrator: `refresh_bars` (fetch only missing dates, SQLite upsert, deactivate tickers after repeated failures), `refresh_fundamentals` (throttled by staleness), and `load_bars` (read one symbol's history into a DataFrame — used everywhere downstream).
- **`snapshots.py`** — rebuild `screener_snapshots` after each refresh (calls `ml/features` for RSI/52-week math).
- **`screener.py`** — translate filter query params → a SQLAlchemy query on snapshots. `RANGE_FILTERS` is a table so each min/max filter is one row, not 20 if-statements; `SORTABLE_COLUMNS` is a whitelist (injection defense).
- **`portfolio.py`** — watchlist CRUD + valuation (joins each item to its snapshot for price, gain/loss, totals).
- **`prediction.py`** — serving-side ML: lazily loads the active model into a cached singleton; `predict_symbol` (one stock, with SHAP explanation) and `score_all_snapshots` (batch-fill `ai_prob_up`). Both go through the universe cross-section so a single stock's score matches the screener.
- **`refresh.py`** — the background full-refresh job (§5) with `refresh_runs` status tracking.
- **`picks.py`** — the track record: `record_live_picks` (log today's top-K, idempotent per day), `settle_open_picks` (fill realized returns once the horizon elapses), and `get_track_record` (summary + per-period rows + **cumulative equity curve** + **bootstrap significance test** on the edge).
- **`advisor.py`** — the Plan builder (§10).

### 7.4 Routers (`routers/`) — the API surface (~22 endpoints)

| Router | Endpoints |
|---|---|
| `screener` | `GET /api/screener` — validated filters → snapshot query (rows + count + as_of_date) |
| `screens` | `GET/POST /api/screens`, `DELETE /api/screens/{id}` — saved screens (POST is idempotent by name) |
| `search` | `GET /api/search?q=` — symbol/name autocomplete (excludes SPY) |
| `stocks` | `GET /api/stocks/{symbol}`, `/history?range=`, `/indicators` |
| `predictions` | `GET /api/predictions/{symbol}` (prob + SHAP), `GET /api/model/report` (metrics, folds, backtest, calibration, **PSR**) |
| `watchlist` | `GET/POST /api/watchlist`, `PUT/DELETE /api/watchlist/{id}` (GET enriched with price/P&L/AI) |
| `track_record` | `GET /api/track-record` |
| `backtest` | `GET /api/backtest/signals`, `POST /api/backtest` |
| `plan` | `POST /api/plan` (capital, num_positions) |
| `admin` | `POST /api/admin/refresh` + `GET .../status`, `GET /api/meta`, `GET /api/health` |

---

## 8. The ML system (the heart) — `app/ml/`

**The target is cross-sectional.** The model does *not* predict "will stock X go up?" (that's ~90% market noise). It predicts "will X **outperform the S&P 500 median** over the next 21 trading days?" — the standard quant formulation, which removes the market factor and is 50/50 balanced by construction.

The pipeline, in order:

1. **`features.py` — Stage-1 (per-symbol, point-in-time).** Hand-rolled RSI, MACD, ATR, moving-average ratios, volatility, volume trends, 52-week range, SPY-relative return, and momentum factors (`mom_12_1`, `mom_6_1` = 12-/6-month momentum skipping the last month; `vol_adj_mom` = risk-adjusted momentum). **24 features.** Every one uses only rolling windows / non-negative shifts, so the value at date *t* depends only on data ≤ *t* (no lookahead) — a unit test proves mutating future rows can't change past features.

2. **`cross_section.py` — Stage-2 (cross-sectional, per-date).** `add_cross_sectional_features` adds `xs_*` columns = each stock's **percentile rank within its date** for the signals that matter relatively (momentum, returns, RSI, volatility, trend, relative strength, 52-week position). **8 features.** Ranking within a date uses only same-date data (no lookahead) and gives the model relative positioning rather than absolute levels. `MODEL_FEATURE_COLUMNS` = Stage-1 + Stage-2 = **32 features**, the ordered list stored in each artifact and *asserted at load* (the skew guard). `build_latest_cross_section` reproduces the exact same transform on the current universe for inference.

3. **`labeling.py` — the target.** `compute_forward_returns` (close.shift(−H)/close − 1) and `cross_sectional_labels` (1 if a stock's forward return beats its date's universe median). `shift(-H)` means the *label* looks forward while *features* look backward; the last H rows per stock are unlabeled (the newest is what live inference scores).

4. **`dataset.py` — the pooled panel.** Per-symbol Stage-1 features + forward returns → pool (~600k rows) → Stage-2 ranks → cross-sectional labels. Keeps `fwd_ret` and `close` so the backtester reuses them.

5. **`train.py` — training + honest evaluation.** XGBoost `XGBClassifier`. **Walk-forward validation**: 5 folds, each training on all data *before* a 6-month test window (time-ordered, never random — random splits leak the future). **Embargo**: drop the H trading days before each test window (those labels peek into the test period — the leak most people miss). Metrics: accuracy, ROC-AUC, and the headline **rank IC** (`_rank_ic`: mean daily Spearman correlation between prediction and realized forward return — ~0.02–0.05 is a real edge), always shown next to the base rate. `fit_calibration` fits isotonic regression on the out-of-fold predictions.

6. **`backtest.py` (ML backtest, distinct from the Backtest lab).** Over the walk-forward test windows: long-only top-20 *and* market-neutral long-short (top-20 minus bottom-20), with ~10 bps/side costs → Sharpe, drawdown, rank IC, equity curves. Defines the `CAVEATS` shown on `/model`. The **long-short** curve is the honest measure of stock-picking skill; long-only mostly rides market beta + survivorship bias.

7. **`artifacts.py` — versioned storage.** Each model is a folder `artifacts/vYYYYMMDD_HHMM/` with `model.json` (XGBoost native format, not pickle), `feature_columns.json`, `calibration.json`, `metadata.json`, `backtest.json`; registered in `model_versions` with `is_active` flipped. Load-time check: stored feature list must equal current `MODEL_FEATURE_COLUMNS` or it refuses to load.

8. **`inference.py` — scoring + explanation.** `score_row` scores one already-cross-sectional feature row, applies calibration, and explains it with XGBoost's built-in **TreeSHAP** (`pred_contribs=True`) — the top-5 signed contributions become the "why" bars in the UI.

9. **`stats.py` — significance.** `bootstrap_mean_ci` (period-level bootstrap CI + p-value on an edge series) and `probabilistic_sharpe_ratio` (prob. the true Sharpe > 0, adjusting for sample length, skew, kurtosis — Bailey & López de Prado). Used by the track record and the model report.

**Current honest result:** rank IC ≈ +0.03, market-neutral long-short Sharpe ≈ 0.5 — a small but real edge (AUC ≈ 0.51, *not* suspiciously high = no leakage). The track record's per-period edge over SPY is statistically significant (bootstrap p ≈ 0.02) but modest.

---

## 9. The Backtest lab (`app/backtest/`) — test any strategy honestly

Separate from the ML backtest: an **interactive, point-in-time, event-driven engine** so you can backtest *any* strategy over history.

- **`spec.py` — `StrategySpec`:** signal (a rule like `mom_12_1`/`rsi_14`/`vol_21d`, or `ai_walkforward`), direction (top/bottom), **weighting (equal / inverse_vol)**, top_k, rebalance_days, costs_bps, capital, date range. `SIGNAL_CHOICES` is the whitelist the UI dropdown reads.
- **`engine.py` — the core.** `simulate()` is a **pure, testable function**: rank the universe by the signal on each rebalance date → select top-K → weight (equal or risk-based) → hold to the next rebalance → charge costs on turnover → mark daily → metrics + equity curve + holdings. Convention: positions entered at the rebalance date's close (standard for the slow signals offered). `_load_universe` (cached price/bar panels keyed by latest date) and `_signal_panel` (cached per-feature point-in-time panel) make the first run ~4s and the rest instant. `_ai_signal_panel` pivots `wf_predictions` so the **AI model itself** can be the ranking signal — ranked by its leak-free out-of-sample score; the result is flagged `out_of_sample`.
- **`metrics.py`** — CAGR, annual vol, Sharpe, Sortino, max drawdown, Calmar, information ratio, win rate, turnover, plus a bootstrap significance test on the per-period excess return.
- **`weighting.py`** — `target_weights(symbols, vols, scheme)`: `equal` (1/N) or `inverse_vol` (weight ∝ 1/volatility, so each holding contributes similar risk — a risk-parity-lite; neutral fill for missing vols, equal-weight fallback). Shared by the engine AND the Plan.

**Honesty guards:** implausibly strong results (Sharpe > 2.5 or CAGR > 0.4) auto-attach a survivorship-bias warning; the AI path carries an "out-of-sample (leak-free)" badge; rule signals are point-in-time. Four **known-answer tests** pin the engine (buy-and-hold == price return, equal-weight == average, costs reduce return, selection picks the top signal) — because a buggy backtester is worse than none. The AI backtest **reconciles** with the `/model` long-only backtest and the track record.

---

## 10. The Plan builder (`services/advisor.py`) — the capstone

Turns a dollar amount into a dated buy list that accounts for the current market. `POST /api/plan` → `build_plan`:

1. **`assess_market`** reads the regime from SPY — trend (price vs 200-day avg), realized volatility vs its own history, and **breadth** (% of stocks above their 200-day average, via the backtester's cached `close_sma200_ratio` panel) → a label + stance: `risk_on`, `cautious`, or `defensive`.
2. **Stance → strategy** (`_stance_params`): how many positions, what fraction invested (vs cash), whether to require each pick be in its own uptrend, and the weighting scheme — **equal weight in calm `risk_on` regimes, risk-based (inverse-vol) in volatile/defensive regimes**, where it also holds fewer names and more cash.
3. **Selection**: top-K by `ai_prob_up` from snapshots, with an uptrend filter (defensive regimes) and a per-sector cap (diversification).
4. **Sizing**: `target_weights` (equal or inverse-vol, using the point-in-time `vol_21d` panel) → whole-share allocations within the invested budget; leftover is cash.
5. **Expectation**: attaches the model's out-of-sample track record (avg edge, hit rate, significance) and a review date (horizon from the active model).
6. **Caveats**: prominent "illustrative, not investment advice" + modest-edge + survivorship disclosures.

The Plan page links to **"Backtest this strategy →"** (`/backtest?signal=ai_walkforward`), which auto-runs the AI backtest — closing the loop from "what to buy" to "the evidence it has worked."

---

## 11. Frontend deep dive (`frontend/src/`)

- **`main.jsx`** — mounts `<App>` in a `BrowserRouter`; applies the saved/system theme before first paint (`utils/theme.js`, persisted to localStorage).
- **`App.jsx`** — the layout (Navbar + routed page area) and the 8 routes.
- **`api.js`** — every backend call as a named function around one axios instance (`baseURL: '/api'`). Vite's dev proxy forwards `/api` → `:8000`.
- **`utils/format.js`** — money/percent/compact-number formatters + `downloadCsv` (screener export) + the green/red class helper. **`utils/theme.js`** — light/dark theme.
- **`index.css`** — the whole design system as CSS variables (dark + light themes), panels, tables, forms, chips, modal, chart tokens. No CSS framework.

**Pages (`pages/`):**

| Page | Route | What it does |
|---|---|---|
| Screener | `/` | FilterPanel (URL-synced) + ScreenerPresets + SavedScreens + ResultsTable (server-side sort) + CSV export |
| **Plan** | `/plan` | The capstone: amount → market card + strategy + buy list + backtested expectation + "Backtest this strategy →" |
| StockDetail | `/stocks/:symbol` | PriceChart (ranges) + StatsGrid + IndicatorPanel + PredictionCard (prob + SHAP bars) + add-to-watchlist |
| Watchlist | `/watchlist` | Holdings with P&L, totals, add/edit modal |
| Compare | `/compare` | Overlay up to 4 stocks' prices indexed to 100 |
| Backtest | `/backtest` | Strategy form → equity curve vs SPY + metrics + significance + holdings; AI/out-of-sample badge; deep-linkable |
| TrackRecord | `/track-record` | Cumulative curve + bootstrap significance + per-rebalance picks & outcomes |
| ModelReport | `/model` | Rank IC, AUC vs base rate, Sharpe, **PSR**, fold table, equity curves, calibration curve, caveats |

**Key frontend patterns:** screener filters live in the URL (shareable, bookmarkable); "derived loading" state (a result is stale when its params-key ≠ the current one) avoids setting state in effects; the Refresh button polls `refresh_runs` and fires a `data-refreshed` window event open pages listen for.

---

## 12. Testing (`backend/tests/`, 42 tests)

| File | Covers |
|---|---|
| `test_features.py` | Indicator math vs hand-computed values; RSI bounds; momentum math; **the no-lookahead property test** |
| `test_labeling.py` | Forward-return label alignment + the unlabeled tail |
| `test_cross_section.py` | Cross-sectional label balance (~50%); within-date rank no-leakage; rank IC on a synthetic signal; calibration monotonicity; bootstrap CI + PSR |
| `test_screener.py` | Filter/sort/pagination against an in-memory DB |
| `test_api.py` | `TestClient` over an in-memory DB (StaticPool): health, screener, meta, search, saved-screens CRUD, track-record, 404 |
| `test_backtest.py` | Known-answer engine tests; inverse-vol weighting; AI signal panel pivot |
| `test_advisor.py` | Plan sector cap, whole-share sizing, weights sum to 1, model-required |

Run: `cd backend && .venv/bin/python -m pytest tests/`. Frontend: `cd frontend && npm run lint`. CI runs both on every push.

---

## 13. Concepts glossary (the ideas the code depends on)

- **Adjusted close** — price corrected for splits/dividends; the only sane series for returns.
- **RSI / MACD / ATR / SMA** — classic technical indicators (momentum oscillator, moving-average momentum, average true range, simple moving average).
- **Cross-sectional prediction** — predict relative performance (beat the universe median) instead of absolute direction; removes the market factor.
- **Train/serve skew** — features computed differently in training vs serving. Prevented by the single shared feature module + an artifact-time feature-list assertion.
- **Lookahead / leakage** — letting future info into training. Prevented by rolling-window-only features, date-ordered splits, and the H-day embargo.
- **Walk-forward validation** — evaluate on chronologically later data than training, repeatedly.
- **Rank IC (information coefficient)** — correlation between the model's ranking and reality; the cleanest "is the signal real?" number.
- **Probabilistic / deflated Sharpe** — probability the true Sharpe beats a benchmark, adjusting for sample length and non-normality.
- **TreeSHAP** — exact per-feature attribution of a tree model's prediction (built into XGBoost).
- **Survivorship bias** — using today's index members inflates historical backtests (past losers that were removed are missing). Disclosed everywhere.
- **Inverse-volatility weighting** — size positions ∝ 1/volatility so each contributes similar risk (risk-parity-lite).
- **Upsert** — insert-or-update in one statement; makes data refreshes idempotent.

---

## 14. How to extend it (where things plug in)

- **New screener filter** — add a column to `screener_snapshots` + a row to `RANGE_FILTERS` + a field in `FilterPanel`.
- **New model feature** — add it to `features.py` (Stage-1) or `cross_section.py` (Stage-2), retrain (`train_model.py`), re-seed picks. The artifact's feature list guards consistency.
- **New backtest signal** — add to `SIGNAL_CHOICES`; rule signals need only a `compute_features` column.
- **New data source** — implement the `DataProvider` ABC in a new file, set `DATA_PROVIDER`.
- **New page** — add an `api.js` function, a `pages/` component, a route in `App.jsx`, a `Navbar` link.
- **Deploy** — deploy-ready: Alembic migrations (`backend/alembic/`), a dialect-aware upsert (SQLite + Postgres), and optional single-service static serving (set `STATIC_DIR` → FastAPI serves the built SPA). `app/main.py` auto-creates tables only on SQLite; Postgres uses `alembic upgrade head`. See **[DEPLOY.md](DEPLOY.md)** for the Railway/Render + Postgres + cron runbook.

---

## 15. The project's ethos (read this last, remember it first)

Every number in this app is designed to be *honest*: leak-free walk-forward evaluation, a shared feature module that prevents skew, metrics shown next to their base rates, statistical significance on every edge, prominent survivorship-bias warnings, and "not investment advice" throughout. The model has a small, real, statistically-significant edge — and the app says so plainly rather than dressing it up. When extending it, **never chase a bigger backtest number by weakening a leakage guard.** A sudden jump to AUC > 0.65 or Sharpe > 3 almost always means a bug, not alpha — the code warns you, and you should believe it.
