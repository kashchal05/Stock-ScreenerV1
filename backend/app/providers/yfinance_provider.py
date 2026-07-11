import logging
import time
from datetime import date, timedelta

import pandas as pd
import yfinance as yf

from app.config import settings
from app.providers.base import DataProvider, Fundamentals, Quote

logger = logging.getLogger(__name__)

BAR_COLUMNS = ["open", "high", "low", "close", "volume"]


class YFinanceProvider(DataProvider):
    def get_daily_bars(
        self, symbols: list[str], start: date, end: date
    ) -> dict[str, pd.DataFrame]:
        result: dict[str, pd.DataFrame] = {}
        batch_size = settings.yf_batch_size
        # yfinance's `end` is exclusive; add a day so today's bar is included
        end_exclusive = end + timedelta(days=1)
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i : i + batch_size]
            try:
                raw = yf.download(
                    batch,
                    start=start,
                    end=end_exclusive,
                    auto_adjust=True,
                    group_by="ticker",
                    threads=True,
                    progress=False,
                )
            except Exception:
                logger.exception("yf.download failed for batch starting %s", batch[0])
                continue
            if raw is None or raw.empty:
                continue
            for symbol in batch:
                frame = self._extract_symbol(raw, symbol, single=len(batch) == 1)
                if frame is not None and not frame.empty:
                    result[symbol] = frame
            if i + batch_size < len(symbols):
                time.sleep(1.5)
        return result

    @staticmethod
    def _extract_symbol(raw: pd.DataFrame, symbol: str, single: bool) -> pd.DataFrame | None:
        # Multi-ticker downloads come back with (ticker, field) MultiIndex columns;
        # single-ticker downloads come back flat. Normalize both here so no
        # MultiIndex ever escapes the provider.
        if isinstance(raw.columns, pd.MultiIndex):
            if symbol not in raw.columns.get_level_values(0):
                return None
            frame = raw[symbol].copy()
        elif single:
            frame = raw.copy()
        else:
            return None
        frame.columns = [str(c).lower() for c in frame.columns]
        missing = [c for c in BAR_COLUMNS if c not in frame.columns]
        if missing:
            return None
        frame = frame[BAR_COLUMNS].dropna(subset=["close"])
        frame.index = pd.to_datetime(frame.index).date
        frame.index.name = "date"
        return frame

    def get_fundamentals(self, symbol: str) -> Fundamentals:
        ticker = yf.Ticker(symbol)
        market_cap = None
        try:
            market_cap = ticker.fast_info.get("marketCap")
        except Exception:
            logger.warning("fast_info failed for %s", symbol)
        name = sector = industry = None
        pe_ratio = None
        try:
            info = ticker.info
            name = info.get("shortName") or info.get("longName")
            sector = info.get("sector")
            industry = info.get("industry")
            pe_ratio = info.get("trailingPE")
            market_cap = market_cap or info.get("marketCap")
        except Exception:
            logger.warning("info failed for %s", symbol)
        return Fundamentals(
            symbol=symbol,
            name=name,
            sector=sector,
            industry=industry,
            market_cap=market_cap,
            pe_ratio=pe_ratio,
        )

    def get_quote(self, symbol: str) -> Quote:
        try:
            price = yf.Ticker(symbol).fast_info.get("lastPrice")
        except Exception:
            price = None
        return Quote(symbol=symbol, price=price)
