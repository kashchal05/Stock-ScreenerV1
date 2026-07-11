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
from sklearn.metrics import accuracy_score, roc_auc_score

from app.ml.features import FEATURE_COLUMNS

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
        predictions = test[["symbol", "date", "label"]].copy()
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

    all_labels = np.concatenate([f["test_predictions"]["label"].to_numpy() for f in fold_results])
    all_probs = np.concatenate([f["test_predictions"]["prob"].to_numpy() for f in fold_results])
    aggregate = _fold_metrics(all_labels, all_probs)
    aggregate["n_folds"] = len(fold_results)
    return aggregate, fold_results


def train_final_model(panel: pd.DataFrame) -> xgb.XGBClassifier:
    """Retrain on all labeled data with the evaluated hyperparameters."""
    model = _make_model()
    model.fit(panel[FEATURE_COLUMNS], panel["label"])
    return model
