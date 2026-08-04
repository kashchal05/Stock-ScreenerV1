from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import TrackRecordOut
from app.services.picks import get_track_record

router = APIRouter(prefix="/api", tags=["track-record"])


@router.get("/track-record", response_model=TrackRecordOut)
def track_record(db: Session = Depends(get_db)):
    return get_track_record(db)
