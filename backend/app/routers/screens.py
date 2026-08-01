from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SavedScreen
from app.schemas import SavedScreenIn, SavedScreenOut

router = APIRouter(prefix="/api/screens", tags=["screens"])


@router.get("", response_model=list[SavedScreenOut])
def list_screens(db: Session = Depends(get_db)):
    return db.query(SavedScreen).order_by(SavedScreen.created_at.desc()).all()


@router.post("", response_model=SavedScreenOut, status_code=201)
def create_screen(payload: SavedScreenIn, db: Session = Depends(get_db)):
    name = payload.name.strip()
    existing = db.query(SavedScreen).filter(SavedScreen.name == name).first()
    if existing is not None:
        # Overwrite the query for an existing name (idempotent "save").
        existing.query = payload.query
        db.commit()
        db.refresh(existing)
        return existing
    screen = SavedScreen(name=name, query=payload.query)
    db.add(screen)
    db.commit()
    db.refresh(screen)
    return screen


@router.delete("/{screen_id}", status_code=204)
def delete_screen(screen_id: int, db: Session = Depends(get_db)):
    screen = db.get(SavedScreen, screen_id)
    if screen is None:
        raise HTTPException(status_code=404, detail="Saved screen not found")
    db.delete(screen)
    db.commit()
