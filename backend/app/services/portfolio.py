from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import ScreenerSnapshot, Ticker, WatchlistItem
from app.schemas import WatchlistItemIn, WatchlistItemOut, WatchlistItemUpdate, WatchlistResponse
from app.services.universe import normalize_symbol


def _to_out(item: WatchlistItem, snapshot: ScreenerSnapshot | None) -> WatchlistItemOut:
    price = snapshot.price if snapshot else None
    market_value = gain_loss = gain_loss_pct = None
    if price is not None and item.quantity:
        market_value = price * item.quantity
        if item.buy_price:
            cost = item.buy_price * item.quantity
            gain_loss = market_value - cost
            gain_loss_pct = gain_loss / cost
    return WatchlistItemOut(
        id=item.id,
        symbol=item.symbol,
        name=snapshot.name if snapshot else None,
        buy_price=item.buy_price,
        quantity=item.quantity,
        notes=item.notes,
        added_at=item.added_at,
        current_price=price,
        market_value=market_value,
        gain_loss=gain_loss,
        gain_loss_pct=gain_loss_pct,
        change_1d=snapshot.change_1d if snapshot else None,
        ai_prob_up=snapshot.ai_prob_up if snapshot else None,
    )


def list_watchlist(db: Session) -> WatchlistResponse:
    items = db.query(WatchlistItem).order_by(WatchlistItem.added_at.desc()).all()
    snapshots = {
        s.symbol: s
        for s in db.query(ScreenerSnapshot)
        .filter(ScreenerSnapshot.symbol.in_([i.symbol for i in items]))
        .all()
    }
    out = [_to_out(item, snapshots.get(item.symbol)) for item in items]

    valued = [o for o in out if o.market_value is not None and o.buy_price is not None]
    total_value = sum(o.market_value for o in valued) if valued else None
    total_cost = sum(o.buy_price * o.quantity for o in valued) if valued else None
    total_gain_loss = total_value - total_cost if valued else None
    total_gain_loss_pct = total_gain_loss / total_cost if valued and total_cost else None
    return WatchlistResponse(
        items=out,
        total_value=total_value,
        total_cost=total_cost,
        total_gain_loss=total_gain_loss,
        total_gain_loss_pct=total_gain_loss_pct,
    )


def add_item(db: Session, payload: WatchlistItemIn) -> WatchlistItemOut:
    symbol = normalize_symbol(payload.symbol)
    if db.get(Ticker, symbol) is None:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")
    existing = db.query(WatchlistItem).filter(WatchlistItem.symbol == symbol).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"{symbol} is already in the watchlist")
    item = WatchlistItem(
        symbol=symbol,
        buy_price=payload.buy_price,
        quantity=payload.quantity,
        notes=payload.notes,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _to_out(item, db.get(ScreenerSnapshot, symbol))


def update_item(db: Session, item_id: int, payload: WatchlistItemUpdate) -> WatchlistItemOut:
    item = db.get(WatchlistItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    for field in ("buy_price", "quantity", "notes"):
        value = getattr(payload, field)
        if value is not None:
            setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return _to_out(item, db.get(ScreenerSnapshot, item.symbol))


def delete_item(db: Session, item_id: int) -> None:
    item = db.get(WatchlistItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    db.delete(item)
    db.commit()
