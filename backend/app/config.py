from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    database_url: str = f"sqlite:///{BACKEND_DIR / 'screener.db'}"
    artifacts_dir: str = str(BACKEND_DIR / "artifacts")
    data_provider: str = "yfinance"
    cors_origins: str = "http://localhost:5173"
    yf_batch_size: int = 100
    backfill_years: int = 5
    prediction_horizon_days: int = 10

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
