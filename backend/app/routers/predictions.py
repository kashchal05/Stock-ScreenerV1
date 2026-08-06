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

    backtest = json.loads(record.backtest_json) if record.backtest_json else None
    # Probabilistic Sharpe ratio on the market-neutral long-short curve: the
    # probability its true Sharpe is above 0, adjusted for sample length/skew/kurtosis.
    if backtest and backtest.get("equity_curve"):
        from app.ml.stats import probabilistic_sharpe_ratio

        ls = [pt.get("long_short") for pt in backtest["equity_curve"] if pt.get("long_short")]
        rets = [ls[i] / ls[i - 1] - 1 for i in range(1, len(ls))]
        if rets:
            backtest["long_short_psr"] = probabilistic_sharpe_ratio(rets)

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
        backtest=backtest,
        calibration=calibration,
        caveats=CAVEATS,
    )
