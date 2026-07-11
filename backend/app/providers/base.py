from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

import pandas as pd


@dataclass
class Fundamentals:
    symbol: str
    name: str | None = None
    sector: str | None = None
    industry: str | None = None
    market_cap: float | None = None
    pe_ratio: float | None = None


@dataclass
class Quote:
    symbol: str
    price: float | None = None


class DataProvider(ABC):
    """Market data source. Implementations must return per-symbol DataFrames
    indexed by date with columns open/high/low/close/volume, where close is
    the adjusted close. Symbols that returned no data are absent from the dict.
    """

    @abstractmethod
    def get_daily_bars(
        self, symbols: list[str], start: date, end: date
    ) -> dict[str, pd.DataFrame]: ...

    @abstractmethod
    def get_fundamentals(self, symbol: str) -> Fundamentals: ...

    @abstractmethod
    def get_quote(self, symbol: str) -> Quote: ...
