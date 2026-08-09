# Backtester / Simulator — Design & Plan

**Goal:** let you rigorously test and validate *any* stock-selection strategy — the AI model, a screener filter, or a hand-built rule — over history, with honest, leakage-free results and real statistical significance. This turns the app from "here's a score" into "here's proof (or disproof) that the picks work."

This doc recommends the best approach, explains the one hard problem (lookahead), and lays out a phased build. It's deliberately detailed because you asked for the full plan.

---

## 1. What we already have (so we don't rebuild it)

- **Walk-forward evaluation** (`app/ml/train.py`) — leak-free out-of-sample model scoring with an embargo.
- **Model backtest** (`app/ml/backtest.py`) — long-only + market-neutral long-short, costs, Sharpe, rank IC, on `/model`.
- **Track record** (`services/picks.py`, `/track-record`) — the model's actual out-of-sample picks per rebalance, with a cumulative curve, a **bootstrap significance test** (edge = +1.6%/period, 95% CI [+0.2%, +2.9%], p=0.023), and **PSR** on `/model`.
- **Stats helpers** (`app/ml/stats.py`) — bootstrap CI, probabilistic Sharpe ratio.

The backtester **generalizes** this from "the fixed model, top-20" to "any strategy you configure," and reuses the same metrics/stats and the cached `daily_bars` data.

## 2. Recommendation (the best approach)

Build an **interactive, point-in-time, event-driven strategy backtesting engine** with three parts:

1. **A strategy spec** (JSON) the user configures in the UI: universe, ranking signal, selection rule, weighting, rebalance cadence, holding, costs, capital, benchmark.
2. **A vectorized simulation core** that walks the cached daily bars date-by-date, forms portfolios, applies costs, and produces an equity curve + trade log + metrics.
3. **A "Backtest lab" UI page** to configure, run, compare against a benchmark, and save runs.

**Why this design over alternatives:**
- *Not* a third-party engine (Zipline/backtrader/vectorbt): heavy dependencies, awkward with our SQLite cache, and overkill. A focused ~400-line engine we own is testable, transparent, and matches the project's "own the math" ethos (same reason we hand-rolled features).
- *Interactive + configurable* (not just more fixed reports) is what makes it a genuine research/validation tool and ties into **saved screens** (backtest a saved screen as a strategy).
- *Point-in-time* is the non-negotiable core — see §3.

## 3. The one hard problem: lookahead / leakage

A backtest is only honest if, on each rebalance date, it uses **only information available then**. Two strategy types, handled differently:

- **Rule-based signals** (momentum, RSI, value, 52-week position, volume): computed from `daily_bars` up to the rebalance date via the existing `compute_features` (already rolling/shift-only). **Clean and honest** — this is the rigorous core of the backtester.
- **AI-model signals:** the *active* model was trained on all history, so scoring a historical date with it is **lookahead** (in-sample). Honest options:
  - **(a) Reuse walk-forward out-of-sample scores** — each fold's model saw only prior data. This is what the track record already does; the backtester can consume the same predictions for the "backtest the AI honestly" path.
  - **(b) Point-in-time retraining** — retrain the model at each rebalance on only-prior data (a "true" walk-forward backtest). Most rigorous, most expensive (minutes→hours). A later phase.
  - **(c) In-sample, clearly labeled** — score history with the current model but stamp results "in-sample / illustrative, not a real backtest." Allowed only with a loud disclaimer.

**Rule:** the engine tags every run `out_of_sample: true|false` and the UI shows it prominently. Rule-based and walk-forward runs are out-of-sample; current-model runs are not.

Other leakage guards: use **next-day open (or same-day close with a lag)** for fills, never the signal bar's close as both signal and fill; align rebalance to actual trading days; forward returns via `shift(-h)` only.

## 4. Architecture

```
backend/app/backtest/
  spec.py         # StrategySpec pydantic model (the config) + validation
  signals.py      # signal providers: rule-based (reuse features.py), ai_walkforward, ai_current
  engine.py       # event-driven simulation: rank -> select -> weight -> hold -> cost -> equity
  metrics.py      # CAGR, vol, Sharpe, Sortino, max DD, Calmar, turnover, exposure, win rate
                  #   (reuse app/ml/stats.py for bootstrap CI / PSR / deflated Sharpe)
  runner.py       # orchestration + optional persistence of runs
backend/app/models.py         # + BacktestRun table (spec, metrics, curve, trade log, created_at)
backend/app/routers/backtest.py  # POST /api/backtest (run), GET/DELETE /api/backtest/{id} (saved)
frontend/src/pages/Backtest.jsx  # config form + equity curve + metrics + trade log + save/compare
frontend/src/components/StrategyForm.jsx, MetricsPanel.jsx, TradeLog.jsx
```

**StrategySpec** (the knobs):
- `universe`: all active | a saved screen id | an explicit ticker list
- `signal`: `rule:<feature>` (e.g. `rule:mom_12_1`, `rule:rsi_14`) | `ai_walkforward` | `ai_current`
- `direction`: top (high signal) | bottom (low signal, for mean-reversion)
- `selection`: top-K | top-percentile | threshold
- `weighting`: equal | signal-proportional | inverse-volatility | market-cap
- `rebalance_days`: e.g. 21 · `holding`: usually = rebalance
- `costs_bps`: per-side transaction cost · `slippage_bps`
- `capital`: starting $ · `benchmark`: SPY (or any ticker)
- `start` / `end`: date range

**Engine loop (vectorized where possible):**
1. Build the rebalance calendar (trading days from `daily_bars`, stepped by `rebalance_days`).
2. On each date: compute the signal for the universe as-of that date → rank → select → weight.
3. Fill at next-day open (+ slippage); charge `costs_bps` × turnover vs the prior book.
4. Hold to the next rebalance; mark-to-market daily for the equity curve.
5. Record trades (entry/exit date, price, weight, P/L) → trade log.
6. Chain into a daily equity curve; compute metrics vs the benchmark.

## 5. Metrics (the validation payload)

Per run, vs benchmark:
- **Return:** total, CAGR, per-period.
- **Risk:** annualized vol, max drawdown, Calmar (CAGR/maxDD), downside deviation.
- **Risk-adjusted:** Sharpe, Sortino, information ratio vs benchmark.
- **Selection quality:** win rate, average win/loss, turnover, average holding, exposure.
- **Significance (reuse `stats.py`):** bootstrap 95% CI on per-period excess return, **probabilistic Sharpe ratio**, and — once multiple runs exist — a **deflated Sharpe ratio** (adjusts for how many strategies you tried, the antidote to "I backtested 100 things and one looked great").
- **Rolling** 12-month Sharpe/return to expose regime dependence.

## 6. Honest realism knobs (defaults conservative)

Transaction costs (10 bps/side default) + slippage; next-day-open fills; optional cash drag; optional max-position and sector caps. Every run header restates the three standing caveats: **survivorship bias**, **costs are modeled crudely**, **delayed daily data** — plus the out-of-sample flag from §3.

## 7. Data integrity — the biggest real limitation

The universe is **today's** S&P 500 → **survivorship bias** inflates every historical result (losers that left the index are missing). The backtester will disclose this on every run. The real fix is a bigger data effort (a delisted-inclusive, point-in-time universe + point-in-time fundamentals) — tracked separately in the roadmap as the highest-value data upgrade. **Recommendation:** ship the engine now with the disclosure; treat the survivorship fix as its own project. The engine is built to accept a richer universe later with no redesign (it just reads `daily_bars`).

## 8. Phased build (each phase runnable & demoable)

- **✅ Phase 1 — Rule-based MVP (core value) — DONE.** `app/backtest/{spec,engine,metrics}.py` + `POST /api/backtest` (+ `/signals`) + the **Backtest lab** page (`/backtest`): pick a signal (momentum, RSI, trend, low-vol, 52-week…), top-K, rebalance, costs → equity curve vs SPY + metrics (CAGR/Sharpe/Sortino/maxDD/Calmar/win/IR/turnover) + bootstrap significance + latest holdings. Known-answer tests pin the engine (buy-and-hold == price return, equal-weight == average, costs reduce return, selection picks top signal); implausibly strong results auto-flag survivorship inflation.
- **Phase 2 — AI + saved-screen integration.** `signal: ai_walkforward` (consume walk-forward predictions) and `universe: saved_screen`. "Backtest this screen" button on the screener/saved-screens. Verify: `ai_walkforward` top-20 reconciles with the existing `/model` backtest and track record within rounding. *~2 days.*
- **Phase 3 — Rigor & realism.** Slippage, inverse-vol & cap weighting, turnover/exposure, Sortino/Calmar/IR, bootstrap CI + PSR + **deflated Sharpe** across saved runs, rolling metrics, trade log UI. *~2–3 days.*
- **Phase 4 — Save/compare & persistence.** `BacktestRun` table, save runs, overlay 2–3 runs' curves, parameter-sensitivity mini-grid (e.g. K ∈ {10,20,50}). *~2 days.*
- **Phase 5 (optional, advanced) — True point-in-time model backtest.** Retrain per rebalance on only-prior data. Expensive; gate behind a "rigorous (slow)" toggle and cache. *~3–5 days.*

Phases 1–3 deliver ~90% of the value. Total for a strong, honest tool: **~1.5–2 weeks**; the MVP alone (~3 days) is already genuinely useful.

## 9. Validating the backtester itself (critical)

A backtester with a bug is worse than none. Guards:
- **Known-answer tests:** buy-and-hold one stock == its raw price return; a 2-stock 50/50 equal-weight == the average; zero-cost vs costed runs differ by exactly the modeled turnover cost.
- **Reconciliation:** `ai_walkforward` top-20 must match the existing `/model` backtest and `/track-record` numbers.
- **No-lookahead property test:** shifting the fill convention must change results in the expected direction; signals on date *t* must be invariant to future bars (we already test this for features).
- **Sanity bounds:** flag implausible Sharpe (>3) or returns as likely leakage, same spirit as the AUC>0.65 training warning.

## 10. Risks & how we manage them

| Risk | Mitigation |
|---|---|
| Subtle lookahead makes results look amazing | Next-day fills, out-of-sample tagging, reconciliation tests, sanity bounds |
| Survivorship bias overstates returns | Disclosed on every run; engine ready for a richer universe later |
| Overfitting via many trials | Deflated Sharpe + save-runs count as the trial count |
| Scope creep | Ship Phases 1–3; defer per-rebalance retraining and the data upgrade |

## 11. Bottom line — my recommendation

Build the **owned, point-in-time, event-driven engine** (Phases 1–3). It's the most effective way to validate the picks because it's *interactive* (test any idea), *honest* (leak-free rule signals + walk-forward AI, out-of-sample tagged), *rigorous* (bootstrap CI, PSR, deflated Sharpe), and *integrated* (backtest a saved screen or the model with one click). Start with the rule-based MVP — it's ~3 days and immediately lets you answer "does this screen actually beat the market?" with statistics, not vibes. Treat the survivorship-bias data fix as the separate, highest-value follow-up.
