import logging
import urllib.request
from io import StringIO
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from app.models import Ticker

logger = logging.getLogger(__name__)

WIKIPEDIA_SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
FALLBACK_CSV = Path(__file__).resolve().parent.parent.parent / "data" / "sp500_fallback.csv"

# SPY is cached like any ticker: it powers the market-relative feature and the
# backtest benchmark, but is excluded from the screener universe.
BENCHMARK_SYMBOL = "SPY"


def normalize_symbol(symbol: str) -> str:
    # Wikipedia lists class shares as BRK.B; yfinance wants BRK-B
    return symbol.strip().upper().replace(".", "-")


def fetch_sp500_table() -> pd.DataFrame:
    """Returns DataFrame with columns symbol, name, sector, industry."""
    try:
        # Wikipedia 403s the default urllib user agent
        request = urllib.request.Request(
            WIKIPEDIA_SP500_URL, headers={"User-Agent": "stock-screener/1.0"}
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            html = response.read().decode("utf-8")
        tables = pd.read_html(StringIO(html))
        df = tables[0]
        df = df.rename(
            columns={
                "Symbol": "symbol",
                "Security": "name",
                "GICS Sector": "sector",
                "GICS Sub-Industry": "industry",
            }
        )[["symbol", "name", "sector", "industry"]]
        logger.info("Fetched %d tickers from Wikipedia", len(df))
        try:
            df.to_csv(FALLBACK_CSV, index=False)  # keep the offline fallback current
        except OSError:
            logger.warning("Could not update fallback CSV at %s", FALLBACK_CSV)
    except Exception:
        logger.exception("Wikipedia scrape failed, using bundled CSV fallback")
        df = pd.read_csv(FALLBACK_CSV)
    df["symbol"] = df["symbol"].map(normalize_symbol)
    return df


def seed_universe(db: Session) -> int:
    df = fetch_sp500_table()
    count = 0
    for row in df.itertuples(index=False):
        ticker = db.get(Ticker, row.symbol)
        if ticker is None:
            ticker = Ticker(symbol=row.symbol)
            db.add(ticker)
        ticker.name = row.name
        ticker.sector = row.sector
        ticker.industry = row.industry
        ticker.is_active = True
        count += 1
    if db.get(Ticker, BENCHMARK_SYMBOL) is None:
        db.add(
            Ticker(
                symbol=BENCHMARK_SYMBOL,
                name="SPDR S&P 500 ETF (benchmark)",
                sector=None,
                is_active=True,
            )
        )
    db.commit()
    return count


def active_symbols(db: Session, include_benchmark: bool = True) -> list[str]:
    query = db.query(Ticker.symbol).filter(Ticker.is_active.is_(True))
    if not include_benchmark:
        query = query.filter(Ticker.symbol != BENCHMARK_SYMBOL)
    return [row[0] for row in query.order_by(Ticker.symbol).all()]
