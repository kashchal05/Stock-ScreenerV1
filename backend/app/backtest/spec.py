from datetime import date

from pydantic import BaseModel, ConfigDict, Field

# Signals available in the Backtest lab. Rule signals map to a column produced by
# app/ml/features.compute_features (point-in-time, rolling/shift only). The special
# "ai_walkforward" signal ranks by the model's leak-free out-of-sample score (stored
# in wf_predictions), so you can backtest the actual algorithm honestly — it only
# covers the walk-forward window (roughly the last ~2.5 years).
AI_SIGNAL = "ai_walkforward"

SIGNAL_CHOICES: dict[str, dict] = {
    "ai_walkforward": {"label": "AI model (out-of-sample)", "default_direction": "top"},
    "mom_12_1": {"label": "12-1 month momentum", "default_direction": "top"},
    "ret_63d": {"label": "3-month return", "default_direction": "top"},
    "ret_21d": {"label": "1-month return", "default_direction": "top"},
    "vol_adj_mom": {"label": "Risk-adjusted momentum", "default_direction": "top"},
    "rsi_14": {"label": "RSI (14)", "default_direction": "bottom"},
    "close_sma200_ratio": {"label": "Price vs 200-day average", "default_direction": "top"},
    "vol_21d": {"label": "Low volatility (1-month)", "default_direction": "bottom"},
    "pos_52w": {"label": "52-week range position", "default_direction": "top"},
    "pct_off_52w_high": {"label": "Proximity to 52-week high", "default_direction": "top"},
}


class StrategySpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal: str = "mom_12_1"
    direction: str = Field(default="top", pattern="^(top|bottom)$")
    weighting: str = Field(default="equal", pattern="^(equal|inverse_vol)$")
    top_k: int = Field(default=20, ge=1, le=100)
    rebalance_days: int = Field(default=21, ge=5, le=252)
    costs_bps: float = Field(default=10.0, ge=0, le=100)
    capital: float = Field(default=10000.0, gt=0)
    start: date | None = None
    end: date | None = None
