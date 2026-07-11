from functools import lru_cache

from app.config import settings
from app.providers.base import DataProvider


@lru_cache(maxsize=1)
def get_provider() -> DataProvider:
    if settings.data_provider == "yfinance":
        from app.providers.yfinance_provider import YFinanceProvider

        return YFinanceProvider()
    raise ValueError(f"Unknown data provider: {settings.data_provider}")
