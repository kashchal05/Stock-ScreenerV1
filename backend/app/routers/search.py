from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Ticker
from app.services.universe import BENCHMARK_SYMBOL

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search")
def search(q: str = Query(min_length=1, max_length=40), db: Session = Depends(get_db)):
    """Symbol/name autocomplete for the navbar. Excludes the SPY benchmark
    (it has no detail page). Case-insensitive prefix/substring match."""
    like = f"%{q.strip()}%"
    rows = (
        db.query(Ticker.symbol, Ticker.name)
        .filter(
            Ticker.is_active.is_(True),
            Ticker.symbol != BENCHMARK_SYMBOL,
            or_(Ticker.symbol.ilike(like), Ticker.name.ilike(like)),
        )
        .order_by(Ticker.symbol)
        .limit(10)
        .all()
    )
    return [{"symbol": s, "name": n} for s, n in rows]
