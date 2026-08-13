# Improvement Checklist

A living checklist of everything on the roadmap. Effort: **S** = a few hours · **M** = a day or two · **L** = ~a week · **XL** = multi-week. Value: ⭐–⭐⭐⭐. Status: `[x]` done · `[~]` tried but not adopted (see note) · `[ ]` planned. See `ROADMAP.md` for the reasoning behind each item.

---

## ✅ Already done

- [x] **Build-a-Plan (capstone)** — enter a dollar amount → the app reads the market regime (SPY trend, volatility, breadth), picks the strategy (position count + cash by regime), selects the top AI names with sector diversification, sizes each in whole shares, and shows the backtested expectation. The "run it with money, get a dated buy list" workflow.

- [x] Cross-sectional target (predict beating the S&P 500 median, not absolute up/down)
- [x] Momentum factor features (12-1, 6-1, risk-adjusted momentum)
- [x] Within-date cross-sectional rank features (skew-safe, shared train/serve)
- [x] Probability calibration (isotonic on out-of-fold predictions)
- [x] Realistic backtest: transaction costs, long-short (market-neutral), Sharpe, rank IC
- [x] 21-day horizon
- [x] Rank IC + calibration curve + long/short equity curves on the `/model` page
- [x] **Search box** — navbar symbol/name autocomplete → detail page
- [x] **Screen presets** — one-click quick screens (oversold, momentum leaders, AI top picks, …)
- [x] **Saved screens** — save the current filter/sort under a name, reload or delete it
- [x] **CSV export** — download current screener results
- [x] **Light/dark theme toggle** — persisted, respects system default
- [x] **API tests** — TestClient coverage for health/screener/meta/search/screens/404
- [x] **CI** — GitHub Actions runs backend pytest + frontend lint/build on every push
- [x] **Model track record ("paper trading")** — top-K picks per rebalance with realized returns; seeded from leak-free walk-forward, live picks accrue on refresh. Out-of-sample: **+3.4%/pick vs SPY +1.8%, +1.6% edge, 58.8% hit rate**
- [x] **Compare view** — overlay up to 4 stocks' normalized price
- [x] **Track record rigor** — cumulative equity curve + bootstrap significance test on the edge (95% CI, p-value, verdict)
- [x] **Probabilistic Sharpe ratio** on the AI Model report (prob. true long-short Sharpe > 0)
- [x] **Backtest lab (Phase 1)** — configure a rule-based strategy (signal, top-K, rebalance, costs), simulate over history, get equity curve + full metrics (CAGR/Sharpe/Sortino/maxDD/Calmar/turnover/IR) + bootstrap significance; auto-flags implausibly strong (survivorship-inflated) results
- [x] **Backtest lab (Phase 2) — AI signal** — backtest the actual AI algorithm honestly using leak-free walk-forward predictions ("out-of-sample" badge); reconciles with the track record and `/model` backtest. "Backtest this strategy →" deep-link from the Plan page auto-runs it.
- [~] **Sector-neutral ranks** — *tried, then reverted*: rank-within-sector features **reduced** out-of-sample rank IC (0.0303 → 0.0285) and long-short Sharpe (0.53 → 0.23), so they were not adopted. A good example of the walk-forward harness overruling intuition.

---

## 1. Modeling & signal

- [ ] Fundamental + calendar features (P/E vs sector, margins, days-to-earnings) — **M** ⭐⭐⭐
- [ ] Learning-to-rank objective (XGBoost `rank:ndcg`, per-date groups) — **M** ⭐⭐
- [~] Sector-neutral ranks (rank within sector, not just whole universe) — **S** ⭐⭐ — *tried, reverted (reduced IC 0.0303→0.0285 and long-short Sharpe 0.53→0.23)*
- [ ] Regime awareness (VIX/breadth features or per-regime models) — **M** ⭐⭐
- [ ] Ensembling (blend XGBoost with a linear factor model) — **M** ⭐
- [ ] Walk-forward hyperparameter tuning (Optuna, IC as objective) — **M** ⭐⭐
- [ ] Deep learning (LSTM/Transformer) — honest: mostly a trap on daily data — **XL** ⭐

## 2. Data & universe

- [ ] Kill survivorship bias (delisted-inclusive / point-in-time universe) — **L** ⭐⭐⭐
- [ ] Point-in-time fundamentals (as-reported, no hindsight leak) — **L** ⭐⭐⭐
- [ ] Bigger universe (Russell 1000/3000; mind rate limits) — **M** ⭐⭐
- [ ] Paid/real-time data provider via the existing adapter (Polygon/Tiingo) — **M** ⭐⭐
- [ ] Alternative data (news sentiment, analyst revisions, short interest) — **XL** ⭐⭐

## 3. Backtesting & evaluation rigor

- [ ] Overlapping portfolios (rebalance daily with 1/N capital) — **M** ⭐⭐
- [x] Probabilistic Sharpe ratio (prob. true Sharpe > 0) — on `/model` — **S** ⭐⭐ · deflated Sharpe (across trials) still TODO
- [x] Bootstrap significance test on the strategy edge — on `/track-record` — **S** ⭐⭐
- [~] Full backtester / simulator — **see `BACKTESTER_PLAN.md`** — **L** ⭐⭐⭐ — *Phase 1 (rule-based lab) + Phase 2 AI walk-forward signal shipped; remaining: saved-screen universe, deflated Sharpe across runs, save/compare, per-rebalance retraining*
- [ ] Purged & combinatorial cross-validation — **L** ⭐
- [ ] Turnover-based / liquidity-tiered transaction costs + borrow cost — **M** ⭐
- [ ] Experiment tracking (MLflow / runs table for every config's IC/Sharpe) — **M** ⭐⭐

## 4. Product & UX

- [x] Search box — **S** ⭐⭐⭐
- [x] Screen presets (built-in quick screens) — **S** ⭐⭐⭐
- [x] CSV export of screener results — **S** ⭐
- [x] Light/dark theme toggle — **S** ⭐
- [x] Saved screens (persist custom screens to a `saved_screens` table) — **S–M** ⭐⭐⭐
- [ ] Transactions instead of single lots (real FIFO/avg cost basis, realized P/L) — **M** ⭐⭐
- [ ] Watchlist alerts (price/RSI/AI-score triggers in the daily refresh) — **M** ⭐⭐
- [ ] User-facing backtester (backtest your own screen → equity curve) — **L** ⭐⭐⭐
- [x] Compare view (overlay 2–4 stocks' normalized price) — **M** ⭐
- [ ] Candlestick charts — **M** ⭐

## 5. Engineering, infra & deployment

- [ ] Deploy (Alembic → Postgres → Railway/Render + cron refresh/retrain) — **M** ⭐⭐⭐
- [ ] Auth (shared password, or users + JWT) — **M** ⭐⭐
- [x] API tests — **S** ⭐⭐
- [x] CI (GitHub Actions: pytest + lint + build on every push) — **S** ⭐⭐
- [ ] Structured logging + error tracking (Sentry) — **S** ⭐
- [ ] Incremental/parallel refresh (async or multiprocessing downloads) — **M** ⭐

## 6. Ambitious / moonshot

- [x] Paper-trading loop (record live picks, track actual forward performance) — **M** ⭐⭐⭐ — *see the Track record page; seeded from walk-forward, live picks accrue on refresh*
- [ ] Portfolio optimizer (mean-variance / risk-parity sizing with constraints) — **L** ⭐⭐
- [ ] LLM research assistant ("why does the model like NVDA?", filings/news summary) — **L** ⭐⭐
- [ ] Multi-asset (ETFs, crypto, intraday) — **XL** ⭐

---

## Suggested next order

1. ~~Paper-trading loop~~ ✅ done — the honest proof-of-edge is now on the Track record page.
2. Deploy — make it a real, usable product on a live URL.
3. Fundamental features — most credible remaining way to raise IC (momentum-orthogonal signal).
4. Kill survivorship bias + point-in-time fundamentals — the integrity upgrade (expect numbers to drop honestly).
5. User-facing backtester — the feature that makes this stand out.

> The highest-leverage work is **data & evaluation integrity**, not fancier models.
