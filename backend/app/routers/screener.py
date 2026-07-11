from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ScreenerSnapshot
from app.schemas import ScreenerParams, ScreenerResponse
from app.services.screener import run_screen

router = APIRouter(prefix="/api/screener", tags=["screener"])


@router.get("", response_model=ScreenerResponse)
def screen(params: ScreenerParams = Depends(), db: Session = Depends(get_db)):
    rows, total = run_screen(db, params.model_dump())
    as_of = rows[0].as_of_date if rows else (
        db.query(ScreenerSnapshot.as_of_date).order_by(ScreenerSnapshot.as_of_date.desc()).limit(1).scalar()
    )
    return ScreenerResponse(results=rows, total=total, as_of_date=as_of)
