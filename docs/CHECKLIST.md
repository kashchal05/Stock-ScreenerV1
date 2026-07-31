# Improvement Checklist

A living checklist of everything on the roadmap. Effort: **S** = a few hours · **M** = a day or two · **L** = ~a week · **XL** = multi-week. Value: ⭐–⭐⭐⭐. See `ROADMAP.md` for the reasoning behind each item.

---

## ✅ Already done

- [x] Cross-sectional target (predict beating the S&P 500 median, not absolute up/down)
- [x] Momentum factor features (12-1, 6-1, risk-adjusted momentum)
- [x] Within-date cross-sectional rank features (skew-safe, shared train/serve)
- [x] Probability calibration (isotonic on out-of-fold predictions)
- [x] Realistic backtest: transaction costs, long-short (market-neutral), Sharpe, rank IC
- [x] 21-day horizon
- [x] Rank IC + calibration curve + long/short equity curves on the `/model` page
- [x] **Search box** — navbar symbol/name autocomplete → detail page
- [x] **Screen presets** — one-click quick screens (oversold, momentum leaders, AI top picks, …)
- [x] **CSV export** — download current screener results
- [x] **Light/dark theme toggle** — persisted, respects system default
- [x] **API tests** — TestClient coverage for health/screener/meta/404

---

## 1. Modeling & signal

- [ ] Fundamental + calendar features (P/E vs sector, margins, days-to-earnings) — **M** ⭐⭐⭐
- [ ] Learning-to-rank objective (XGBoost `rank:ndcg`, per-date groups) — **M** ⭐⭐
- [ ] Sector-neutral ranks (rank within sector, not just whole universe) — **S** ⭐⭐
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
- [ ] Deflated Sharpe ratio + probability of backtest overfitting — **M** ⭐⭐
- [ ] Purged & combinatorial cross-validation — **L** ⭐
- [ ] Turnover-based / liquidity-tiered transaction costs + borrow cost — **M** ⭐
- [ ] Experiment tracking (MLflow / runs table for every config's IC/Sharpe) — **M** ⭐⭐

## 4. Product & UX

- [x] Search box — **S** ⭐⭐⭐
- [x] Screen presets (built-in quick screens) — **S** ⭐⭐⭐
- [x] CSV export of screener results — **S** ⭐
- [x] Light/dark theme toggle — **S** ⭐
- [ ] Saved screens (persist custom screens to a `saved_screens` table) — **S–M** ⭐⭐⭐
- [ ] Transactions instead of single lots (real FIFO/avg cost basis, realized P/L) — **M** ⭐⭐
- [ ] Watchlist alerts (price/RSI/AI-score triggers in the daily refresh) — **M** ⭐⭐
- [ ] User-facing backtester (backtest your own screen → equity curve) — **L** ⭐⭐⭐
- [ ] Compare view (overlay 2–4 stocks' normalized price) — **M** ⭐
- [ ] Candlestick charts — **M** ⭐

## 5. Engineering, infra & deployment

- [ ] Deploy (Alembic → Postgres → Railway/Render + cron refresh/retrain) — **M** ⭐⭐⭐
- [ ] Auth (shared password, or users + JWT) — **M** ⭐⭐
- [x] API tests — **S** ⭐⭐
- [ ] CI (GitHub Actions: pytest + lint on every push) — **S** ⭐⭐
- [ ] Structured logging + error tracking (Sentry) — **S** ⭐
- [ ] Incremental/parallel refresh (async or multiprocessing downloads) — **M** ⭐

## 6. Ambitious / moonshot

- [ ] Paper-trading loop (record live picks, track actual forward performance) — **M** ⭐⭐⭐
- [ ] Portfolio optimizer (mean-variance / risk-parity sizing with constraints) — **L** ⭐⭐
- [ ] LLM research assistant ("why does the model like NVDA?", filings/news summary) — **L** ⭐⭐
- [ ] Multi-asset (ETFs, crypto, intraday) — **XL** ⭐

---

## Suggested next order

1. Paper-trading loop — cheap, and the honest proof-of-edge everything is judged against.
2. Deploy + saved screens — makes it a real, usable product.
3. Fundamental features + sector-neutral ranks — most credible way to raise IC.
4. Kill survivorship bias + point-in-time fundamentals — the integrity upgrade (expect numbers to drop honestly).
5. User-facing backtester — the feature that makes this stand out.

> The highest-leverage work is **data & evaluation integrity**, not fancier models.
