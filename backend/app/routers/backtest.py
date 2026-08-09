from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.backtest.engine import run_backtest
from app.backtest.spec import SIGNAL_CHOICES, StrategySpec
from app.database import get_db

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


@router.get("/signals")
def list_signals():
    return [
        {"value": key, "label": meta["label"], "default_direction": meta["default_direction"]}
        for key, meta in SIGNAL_CHOICES.items()
    ]


@router.post("")
def run(spec: StrategySpec, db: Session = Depends(get_db)):
    result = run_backtest(db, spec)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
