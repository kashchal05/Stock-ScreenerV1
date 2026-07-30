import json
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.ml.backtest import CAVEATS
from app.models import ModelVersion
from app.schemas import ModelReportOut, PredictionOut
from app.services.prediction import predict_symbol
from app.services.universe import normalize_symbol

router = APIRouter(prefix="/api", tags=["predictions"])


@router.get("/predictions/{symbol}", response_model=PredictionOut)
def prediction(symbol: str, db: Session = Depends(get_db)):
    return predict_symbol(db, normalize_symbol(symbol))


@router.get("/model/report", response_model=ModelReportOut)
def model_report(db: Session = Depends(get_db)):
    record = db.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).first()
    if record is None:
        return ModelReportOut(model_available=False, caveats=CAVEATS)

    calibration = None
    target = None
    metadata_path = Path(record.artifact_path) / "metadata.json"
    if metadata_path.exists():
        target = json.loads(metadata_path.read_text()).get("target")
    calib_path = Path(record.artifact_path) / "calibration.json"
    if calib_path.exists():
        calibration = json.loads(calib_path.read_text()) or None

    return ModelReportOut(
        model_available=True,
        version=record.version,
        target=target,
        trained_at=record.trained_at,
        horizon_days=record.horizon_days,
        train_start=record.train_start,
        train_end=record.train_end,
        feature_count=record.feature_count,
        metrics=json.loads(record.metrics_json) if record.metrics_json else None,
        backtest=json.loads(record.backtest_json) if record.backtest_json else None,
        calibration=calibration,
        caveats=CAVEATS,
    )
