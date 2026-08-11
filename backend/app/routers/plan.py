from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.advisor import build_plan

router = APIRouter(prefix="/api", tags=["plan"])


class PlanRequest(BaseModel):
    capital: float = Field(gt=0, le=1e9)
    num_positions: int | None = Field(default=None, ge=1, le=50)


@router.post("/plan")
def make_plan(req: PlanRequest, db: Session = Depends(get_db)):
    result = build_plan(db, capital=req.capital, num_positions=req.num_positions)
    if not result.get("available"):
        reason = result.get("reason")
        detail = {
            "no_model": "No trained model — run scripts/train_model.py first.",
            "no_market_data": "Not enough market data — run a data refresh first.",
        }.get(reason, "Plan unavailable.")
        raise HTTPException(status_code=400, detail=detail)
    return result
