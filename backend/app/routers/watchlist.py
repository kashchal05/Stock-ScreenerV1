from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import WatchlistItemIn, WatchlistItemOut, WatchlistItemUpdate, WatchlistResponse
from app.services import portfolio

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.get("", response_model=WatchlistResponse)
def list_items(db: Session = Depends(get_db)):
    return portfolio.list_watchlist(db)


@router.post("", response_model=WatchlistItemOut, status_code=201)
def add_item(payload: WatchlistItemIn, db: Session = Depends(get_db)):
    return portfolio.add_item(db, payload)


@router.put("/{item_id}", response_model=WatchlistItemOut)
def update_item(item_id: int, payload: WatchlistItemUpdate, db: Session = Depends(get_db)):
    return portfolio.update_item(db, item_id, payload)


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: int, db: Session = Depends(get_db)):
    portfolio.delete_item(db, item_id)
