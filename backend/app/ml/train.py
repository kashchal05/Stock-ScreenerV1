"""Walk-forward training and evaluation.

Splits are strictly by DATE with an expanding training window and an H-day
embargo before each test window, so no training label's forward window
overlaps test data. Expect AUC around 0.52-0.58 on this problem; anything
near 0.75+ almost certainly means leakage, not skill.
"""

import logging

import numpy as np
import pandas as pd
import xgboost as xgb
from scipy.stats import spearmanr
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import accuracy_score, roc_auc_score

from app.ml.cross_section import MODEL_FEATURE_COLUMNS as FEATURE_COLUMNS

logger = logging.getLogger(__name__)

XGB_PARAMS = dict(
    n_estimators=400,
    max_depth=4,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    min_child_weight=50,
    tree_method="hist",
    eval_metric="logloss",
    n_jobs=-1,
)

N_FOLDS = 5
TEST_MONTHS = 6


def _make_model() -> xgb.XGBClassifier:
    return xgb.XGBClassifier(**XGB_PARAMS)


def _rank_ic(dates: pd.Series, prob: np.ndarray, fwd_ret: pd.Series) -> float | None:
    """Mean daily rank information coefficient: the Spearman correlation between
    predicted probability and realized forward return, computed within each date
    and averaged. The standard measure of cross-sectional signal quality; ~0.02-0.05
    is a real, usable edge.
    """
    if fwd_ret is None:
        return None
    frame = pd.DataFrame({"date": dates.to_numpy(), "prob": prob, "fwd_ret": fwd_ret.to_numpy()})
    frame = frame.dropna()
    ics = []
    for _, group in frame.groupby("date"):
        if len(group) >= 10 and group["prob"].nunique() > 1 and group["fwd_ret"].nunique() > 1:
            ic, _ = spearmanr(group["prob"], group["fwd_ret"])
            if not np.isnan(ic):
                ics.append(ic)
    return float(np.mean(ics)) if ics else None


def fit_calibration(prob: np.ndarray, labels: np.ndarray) -> dict:
    """Fit isotonic calibration on out-of-fold predictions. Serialized as x/y knots
    so inference can reproduce it with np.interp (no pickle)."""
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    iso.fit(prob, labels)
    grid = np.linspace(0.0, 1.0, 101)
    calibrated = iso.predict(grid)
    return {"x": grid.tolist(), "y": [float(v) for v in calibrated]}


def _fold_metrics(y_true: np.ndarray, prob: np.ndarray) -> dict:
    pred = (prob > 0.5).astype(int)
    metrics = {
        "n_test": int(len(y_true)),
        "base_rate": float(np.mean(y_true)),
        "accuracy": float(accuracy_score(y_true, pred)),
        "roc_auc": float(roc_auc_score(y_true, prob)) if len(np.unique(y_true)) > 1 else None,
    }
    for threshold in (0.55, 0.60):
        mask = prob > threshold
        # precision among high-confidence picks = hit rate of predicted longs
        metrics[f"precision_at_{threshold}"] = (
            float(np.mean(y_true[mask])) if mask.sum() > 0 else None
        )
        metrics[f"n_at_{threshold}"] = int(mask.sum())
    return metrics


def walk_forward_evaluate(panel: pd.DataFrame, horizon: int) -> tuple[dict, list[dict]]:
    """Returns (aggregate metrics, per-fold list of {train_end, test_start, test_end,
    metrics, test_predictions}). test_predictions is a DataFrame (symbol, date,
    label, prob) the backtester consumes.
    """
    dates = panel["date"].sort_values()
    last_date = dates.iloc[-1]
    fold_results = []

    for fold in range(N_FOLDS):
        months_back = (N_FOLDS - fold) * TEST_MONTHS
        test_start = last_date - pd.DateOffset(months=months_back)
        test_end = test_start + pd.DateOffset(months=TEST_MONTHS)
        # Embargo: drop the H trading days (~horizon*1.5 calendar days) of
        # training data before the test window so no training label's forward
        # window overlaps test data.
        embargo_start = test_start - pd.Timedelta(days=int(horizon * 1.5))

        train = panel[panel["date"] < embargo_start]
        test = panel[(panel["date"] >= test_start) & (panel["date"] < test_end)]
        if len(train) < 5000 or len(test) < 500:
            logger.warning("Fold %d skipped: train=%d test=%d", fold, len(train), len(test))
            continue

        model = _make_model()
        model.fit(train[FEATURE_COLUMNS], train["label"])
        prob = model.predict_proba(test[FEATURE_COLUMNS])[:, 1]

        metrics = _fold_metrics(test["label"].to_numpy(), prob)
        metrics["train_rows"] = int(len(train))
        metrics["rank_ic"] = _rank_ic(test["date"], prob, test["fwd_ret"])
        cols = ["symbol", "date", "label"] + (["fwd_ret"] if "fwd_ret" in test else [])
        predictions = test[cols].copy()
        predictions["prob"] = prob
        fold_results.append(
            {
                "fold": fold + 1,
                "train_end": str(embargo_start.date()),
                "test_start": str(test_start.date()),
                "test_end": str(test_end.date()),
                "metrics": metrics,
                "test_predictions": predictions,
            }
        )
        logger.info(
            "Fold %d: acc=%.4f base=%.4f auc=%s",
            fold + 1,
            metrics["accuracy"],
            metrics["base_rate"],
            f"{metrics['roc_auc']:.4f}" if metrics["roc_auc"] else "n/a",
        )

    if not fold_results:
        raise RuntimeError("No folds had enough data — is the bars cache populated?")

    oof = pd.concat([f["test_predictions"] for f in fold_results], ignore_index=True)
    aggregate = _fold_metrics(oof["label"].to_numpy(), oof["prob"].to_numpy())
    aggregate["n_folds"] = len(fold_results)
    aggregate["rank_ic"] = (
        _rank_ic(oof["date"], oof["prob"].to_numpy(), oof.get("fwd_ret"))
        if "fwd_ret" in oof
        else None
    )
    aggregate["mean_fold_rank_ic"] = float(
        np.mean([f["metrics"]["rank_ic"] for f in fold_results if f["metrics"].get("rank_ic") is not None])
    ) if any(f["metrics"].get("rank_ic") is not None for f in fold_results) else None
    return aggregate, fold_results


def train_final_model(panel: pd.DataFrame) -> xgb.XGBClassifier:
    """Retrain on all labeled data with the evaluated hyperparameters."""
    model = _make_model()
    model.fit(panel[FEATURE_COLUMNS], panel["label"])
    return model
