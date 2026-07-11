"""Model artifact save/load and the model_versions registry.

Artifacts use XGBoost's native JSON format (stable across library versions,
unlike pickle) plus sidecar JSON files for feature columns and metadata.
"""

import json
from datetime import datetime
from pathlib import Path

import xgboost as xgb
from sqlalchemy.orm import Session

from app.config import settings
from app.ml.features import FEATURE_COLUMNS
from app.models import ModelVersion


def save_artifact(
    db: Session,
    model: xgb.XGBClassifier,
    horizon: int,
    metrics: dict,
    folds: list[dict],
    backtest: dict,
    train_start,
    train_end,
) -> ModelVersion:
    version = datetime.now().strftime("v%Y%m%d_%H%M")
    artifact_dir = Path(settings.artifacts_dir) / version
    artifact_dir.mkdir(parents=True, exist_ok=True)

    model.save_model(artifact_dir / "model.json")
    (artifact_dir / "feature_columns.json").write_text(json.dumps(FEATURE_COLUMNS))
    fold_metrics = [
        {k: v for k, v in f.items() if k != "test_predictions"} for f in folds
    ]
    metadata = {
        "version": version,
        "horizon_days": horizon,
        "trained_at": datetime.now().isoformat(),
        "train_start": str(train_start),
        "train_end": str(train_end),
        "aggregate_metrics": metrics,
        "folds": fold_metrics,
    }
    (artifact_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
    (artifact_dir / "backtest.json").write_text(json.dumps(backtest, indent=2))

    db.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).update(
        {"is_active": False}
    )
    record = ModelVersion(
        version=version,
        horizon_days=horizon,
        train_start=train_start,
        train_end=train_end,
        feature_count=len(FEATURE_COLUMNS),
        metrics_json=json.dumps({"aggregate": metrics, "folds": fold_metrics}),
        backtest_json=json.dumps(backtest),
        artifact_path=str(artifact_dir),
        is_active=True,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def load_active_booster(db: Session) -> tuple[xgb.Booster, ModelVersion] | None:
    record = db.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).first()
    if record is None:
        return None
    artifact_dir = Path(record.artifact_path)
    model_path = artifact_dir / "model.json"
    if not model_path.exists():
        return None
    stored_columns = json.loads((artifact_dir / "feature_columns.json").read_text())
    if stored_columns != FEATURE_COLUMNS:
        raise RuntimeError(
            f"Feature mismatch: artifact {record.version} was trained on different "
            "features than the current code. Retrain with scripts/train_model.py."
        )
    booster = xgb.Booster()
    booster.load_model(str(model_path))
    return booster, record
