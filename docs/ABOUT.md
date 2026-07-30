# About This App

## What it is

A **stock screener with an AI trend model** that runs entirely on your machine. It keeps a local database of 5 years of daily prices for every S&P 500 stock, lets you filter and rank those stocks by dozens of criteria, shows detailed charts and technical indicators for each one, predicts short-term direction with a machine-learning model (and explains each prediction), and tracks a watchlist/portfolio with live profit & loss.

Think of it as a personal, self-hosted version of a Finviz/Yahoo Finance screener — plus an ML pipeline evaluated the way a quant shop would evaluate it (honestly).

## The four screens

| Page | URL | What it does |
|---|---|---|
| **Screener** | `/` | Filter all 503 S&P 500 stocks by price, volume, market cap, P/E, RSI, % change (1d/1w/1m/YTD), distance from 52-week high, sector, and AI probability. Click any column header to sort. Click a row to open the stock. Filters live in the URL, so you can bookmark or share a screen. |
| **Stock detail** | `/stocks/AAPL` | Price + volume chart (1M–5Y tabs), stat cards (market cap, P/E, RSI, returns…), a technical-indicator panel with bullish/bearish tags, and the **AI prediction card**: the model's probability the stock is higher in 10 trading days, with the top-5 signals pushing it up or down. |
| **Watchlist** | `/watchlist` | Add stocks with an optional buy price and quantity. Shows current price, market value, gain/loss in $ and %, 1-day change, and the AI score for each holding, plus portfolio totals. |
| **AI Model** | `/model` | The model's report card: ROC-AUC, accuracy vs the base rate, per-fold results, a backtest equity curve vs simply buying SPY, and an honest-limitations box. |

The navbar also has a **Refresh data** button — it fetches the latest prices, rebuilds all the screener stats, and re-scores every stock with the AI model, in the background (~30–60 seconds).

## How to use it

### First-time setup (once)

```bash
# Prerequisites: Python 3.11+, Node 20+, and on macOS: brew install libomp

cd backend
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/seed_universe.py     # loads the S&P 500 ticker list
.venv/bin/python scripts/refresh_data.py      # downloads 5 years of prices (~5-10 min)
.venv/bin/python scripts/train_model.py       # trains + evaluates the AI model (~5 min)

cd ../frontend
npm install
```

### Every time after that

```bash
./start.sh        # from the project root
```

Then open **http://localhost:5173**. The backend API runs on port 8000 (interactive API docs at http://localhost:8000/docs).

To stop: `Ctrl+C` in the terminal running `start.sh`.

### Day-to-day workflow

1. Start the app and hit **Refresh data** (or run `scripts/refresh_data.py`) to pull the latest prices.
2. Screen for candidates — e.g. "RSI under 35, within 10% of 52-week high, Technology" for oversold names in strong uptrends.
3. Open a stock, look at the chart, the indicators, and what the AI thinks (and *why* — the signal bars).
4. Add interesting names to the watchlist, with a buy price if you own them.
5. Occasionally retrain: `scripts/train_model.py` (e.g. monthly, so the model sees recent data).

## What the AI actually predicts

The model does **not** guess "will this stock go up?" — that's ~90% driven by the whole market moving and is close to a coin flip. Instead it predicts **which stocks will outperform the S&P 500 median** over the next 21 trading days (a "cross-sectional" or market-neutral target). It uses momentum factors and each stock's rank versus the rest of the universe, and its probabilities are calibrated (a shown "62%" really means ~62%).

## Important honesty notes

- Price data comes from Yahoo Finance (free) and is **~15 minutes delayed**, daily bars only.
- The model is **evaluated honestly** on the `/model` page. The headline number is the **rank information coefficient (IC ≈ 0.03)** — a small but genuine edge (0.02–0.05 is the realistic range for this kind of model). The market-neutral long-short backtest is modestly positive after costs; the flashier long-only number is inflated by overall market gains and survivorship bias, and the page says so.
- This is "small but real signal," not a money printer. Equity prediction has a low ceiling; the app's value is that it measures its own skill truthfully instead of showing fake accuracy.
- **Nothing in this app is investment advice.**
