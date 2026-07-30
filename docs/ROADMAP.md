# Roadmap & Future Planning

Ordered roughly by value-for-effort. Each item says *what*, *why*, *how* (where in the code it slots in), and a rough size (S = an evening, M = a weekend, L = a week+).

## Phase A — Deploy it (make it "real real")

### A1. Deploy backend + frontend (M)
- **Why**: use it from anywhere, share a link, and it's the difference between "project" and "product."
- **How**: the code is already 12-factor (all config via env vars, no hardcoded paths).
  1. Add **Alembic** migrations (currently tables are auto-created; migrations are needed before you can evolve a production DB safely).
  2. Swap SQLite → **Postgres** via `DATABASE_URL` (one env var; SQLAlchemy handles the rest — but re-check the one SQLite-specific upsert in `services/market_data.py` and use `sqlalchemy.dialects.postgresql.insert` when on Postgres).
  3. Host: Railway or Render — one service running `uvicorn app.main:app`, one static site from `npm run build` (set the API URL via a reverse-proxy rule or `VITE_API_URL`).
  4. **Scheduled refresh**: a daily cron (Railway cron / GitHub Actions) running `python scripts/refresh_data.py` after market close, and `scripts/train_model.py` monthly.
- **Files touched**: `backend/alembic/` (new), `services/market_data.py` (dialect-aware upsert), deploy configs.

### A2. Basic auth (S–M, only if the link is public)
- **Why**: your watchlist is personal data.
- **How**: simplest respectable option — a single shared password checked by a FastAPI dependency + an `Authorization` header the frontend stores; full option — FastAPI users + JWT. Add per-user `user_id` columns to `watchlist_items` only when multi-user actually matters.

## Phase B — Make the screener better

### B1. Candlestick chart (S–M)
- **Why**: the standard way traders read price action.
- **How**: Recharts has no native candlestick; implement a custom `shape` on a `Bar` that draws the wick+body from `open/high/low/close` (already returned by `/history`), or swap the chart to `lightweight-charts` (TradingView's free library — purpose-built for this).
- **Files**: `frontend/src/components/PriceChart.jsx`.

### B2. Saved screens / presets (S)
- **Why**: re-running "my oversold-quality screen" daily is the core loop of a screener.
- **How**: filters already live in the URL. Add a `saved_screens` table (name + query string) + CRUD endpoints + a dropdown in `FilterPanel`. Ship 3–4 built-in presets ("Oversold quality", "Momentum leaders", "Near 52w high on volume").
- **Files**: `models.py`, new router, `FilterPanel.jsx`.

### B3. More fundamental filters (M)
- **Why**: P/E alone is thin; dividend yield, revenue growth, margins, beta, and forward P/E make screens far more useful.
- **How**: extend `Fundamentals` in `providers/base.py`, pull the extra fields in `get_fundamentals()` (they're in yfinance's `.info`), add columns to `tickers` + `screener_snapshots`, add rows to `RANGE_FILTERS`, add filter fields in the UI. The pattern makes each new filter ~5 lines per layer.

### B4. Universe beyond the S&P 500 (M)
- **Why**: mid/small caps are where screeners get interesting.
- **How**: `seed_universe.py` can ingest any symbol list (e.g. Russell 1000 CSV, or all NASDAQ from a listing file). Watch yfinance rate limits — batching is already in place, but a 3,000-stock backfill will take a while. Consider making `universe` a column so you can filter by index membership.

## Phase C — Make the AI meaningfully better

> **Update (done):** C1, C3, C4, C5 shipped in the cross-sectional upgrade. The model now predicts *outperformance vs the S&P 500 median* over 21 days, using momentum factors + within-date rank features, with isotonic calibration and a costs/long-short/Sharpe backtest. Result: **rank IC ≈ +0.03, market-neutral long-short Sharpe ≈ 0.5** — a small but real edge, up from the old no-signal baseline (AUC 0.497). The remaining items below are the next frontier.

### ✅ C1. Cross-sectional ranking instead of absolute direction — DONE
Shipped: `ml/labeling.py` `cross_sectional_labels` (beat the same-day universe median), `ml/cross_section.py` (within-date rank features + skew-safe inference).

### C2. Fundamental + calendar features (M) — next highest-value
- **Why**: price-only features are the most-arbitraged information on earth. Valuation, profitability, and earnings-date proximity add orthogonal signal to the momentum factors already in place.
- **How**: extend `features.py` (Stage 1) with slow-moving per-ticker features and add their `xs_*` ranks in `cross_section.py` (P/E percentile vs sector, market-cap bucket, days-to-earnings from `yf.Ticker.calendar`). Historical fundamentals are hard to get point-in-time for free — flag as a data-quality caveat.

### ✅ C3. Longer horizons — DONE (21 days)
Horizon is `PREDICTION_HORIZON_DAYS` (default 21). Sweep `--horizon 63` vs 21 and keep the best rank IC if you want to tune further.

### ✅ C4. Probability calibration — DONE
Isotonic on out-of-fold predictions, stored as `calibration.json`, applied at inference; reliability curve on `/model`.

### ✅ C5. Backtest realism — DONE (costs + long-short + Sharpe)
Next refinement if desired: overlapping portfolios (rebalance daily with 1/N of capital) to reduce start-date luck, and per-trade turnover accounting instead of the flat round-trip cost.

### C6. Learning-to-rank objective (M) — new idea
- **Why**: the backtest cares about *ordering* stocks, so optimize ordering directly instead of binary classification.
- **How**: XGBoost `rank:pairwise` / `rank:ndcg` with per-date query groups; label by forward-return rank. Compare rank IC vs the current classifier.

## Phase D — Quality of life

- **D1. Search box** (S): symbol/name autocomplete in the navbar → detail page. One endpoint (`LIKE` on tickers) + a debounced input.
- **D2. Compare view** (M): overlay 2–4 stocks' normalized price on one chart; `/history` already returns everything needed.
- **D3. Watchlist alerts** (M): a `price_alerts` table + a check inside the daily refresh + email via Resend/SES (or just a UI badge). The refresh pipeline is the natural hook.
- **D4. Transactions instead of single lots** (M): the current watchlist stores one buy per symbol; a `transactions` table (buy/sell rows) enables real cost-basis (FIFO/average), realized vs unrealized P/L, and a portfolio time series.
- **D5. Export** (S): CSV download of screener results — a `to_csv` endpoint or client-side blob from the already-fetched JSON.
- **D6. API tests** (S): `tests/test_api.py` with FastAPI's `TestClient` (httpx is already installed) covering the routers end-to-end against a seeded in-memory DB.
- **D7. Dark/light theme toggle** (S): the design is already all CSS variables — add a `[data-theme="light"]` block and a toggle that flips an attribute.

## Suggested order

1. **A1 deploy** — everything gets more motivating once it's live.
2. **B2 saved screens + D1 search** — biggest daily-use wins, both small.
3. **C1 cross-sectional labels + C3 horizon sweep** — the highest-value ML experiment, using the harness you already have.
4. **B3 fundamentals** — improves both the screener (filters) and the model (features) at once.
5. Everything else as interest dictates.

## Things to watch out for (learned during the build)

- **yfinance breaks occasionally** (it's unofficial). All quirks are quarantined in `providers/yfinance_provider.py` — if downloads start failing, fix or swap *that file only*. Pin the version before deploying.
- **Never evaluate with random splits** on this data — you will get beautiful, fake results. Keep the walk-forward + embargo harness as the only judge.
- **If a model suddenly shows AUC > 0.7, it's a leak, not alpha.** The train script already prints a warning; believe it.
- **SQLite = one writer.** The app already serializes refresh jobs (409 if one is running). If you add more background work, keep that discipline or move to Postgres first.
- Wikipedia scraping needs the custom User-Agent (already in `services/universe.py`); if the table format changes, the CSV fallback keeps seeding working.
