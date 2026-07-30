"""Train the cross-sectional model: dataset -> walk-forward eval -> calibration
-> backtest -> artifact.

Usage: .venv/bin/python scripts/train_model.py [--horizon 21]

Target: predict which stocks BEAT the universe median forward return (market-neutral).
Expect cross-sectional AUC ~0.52-0.56 and rank IC ~0.02-0.05. If you see AUC 0.65+
out-of-sample, hunt for leakage before celebrating.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.ml.artifacts import save_artifact
from app.ml.backtest import run_backtest
from app.ml.dataset import build_dataset
from app.ml.train import fit_calibration, train_final_model, walk_forward_evaluate
from app.services.market_data import load_bars
from app.services.universe import BENCHMARK_SYMBOL


def _fmt(value, spec="+.2%"):
    return format(value, spec) if value is not None else "n/a"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--horizon", type=int, default=settings.prediction_horizon_days)
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        print(f"Building dataset (horizon={args.horizon} trading days, cross-sectional target)...")
        panel = build_dataset(db, horizon=args.horizon)
        if panel.empty:
            sys.exit("No data — run scripts/refresh_data.py first")
        print(f"  {len(panel):,} rows, {panel['symbol'].nunique()} symbols, "
              f"{panel['date'].min().date()} → {panel['date'].max().date()}")
        print(f"  label mean (outperform rate, ~0.50 by construction): {panel['label'].mean():.4f}")

        print("\nWalk-forward evaluation (5 folds, 6-month test windows, embargoed)...")
        aggregate, folds = walk_forward_evaluate(panel, horizon=args.horizon)

        print(f"\n{'fold':<6}{'test window':<28}{'acc':<8}{'base':<8}{'auc':<8}{'IC':<8}")
        for fold in folds:
            m = fold["metrics"]
            print(f"{fold['fold']:<6}{fold['test_start']} → {fold['test_end']:<13}"
                  f"{m['accuracy']:<8.4f}{m['base_rate']:<8.4f}"
                  f"{_fmt(m['roc_auc'], '.4f'):<8}{_fmt(m.get('rank_ic'), '+.4f'):<8}")
        print(f"\nAggregate: accuracy={aggregate['accuracy']:.4f} "
              f"(base rate {aggregate['base_rate']:.4f}), "
              f"AUC={_fmt(aggregate['roc_auc'], '.4f')}, "
              f"rank IC={_fmt(aggregate.get('rank_ic'), '+.4f')} "
              f"(mean-fold {_fmt(aggregate.get('mean_fold_rank_ic'), '+.4f')})")
        if aggregate["roc_auc"] and aggregate["roc_auc"] > 0.65:
            print("WARNING: AUC suspiciously high for this problem — check for leakage.")

        print("\nFitting probability calibration (isotonic on out-of-fold predictions)...")
        oof = pd.concat([f["test_predictions"] for f in folds], ignore_index=True)
        calibration = fit_calibration(oof["prob"].to_numpy(), oof["label"].to_numpy())

        print("Backtesting long-only and long-short (market-neutral) after costs...")
        spy = load_bars(db, BENCHMARK_SYMBOL)
        backtest = run_backtest(folds, spy["close"], horizon=args.horizon)
        if "error" not in backtest:
            lo, ls = backtest["long_only"], backtest["long_short"]
            print(f"  rank IC: {_fmt(backtest['rank_ic'], '+.4f')}  "
                  f"({backtest['start']} → {backtest['end']}, {lo['n_periods']} periods)")
            print(f"  long-only : return {_fmt(lo['total_return'])}, "
                  f"Sharpe {_fmt(lo['sharpe'], '.2f')}, maxDD {_fmt(lo['max_drawdown'])}  "
                  f"| SPY {_fmt(backtest['spy_total_return'])}")
            print(f"  long-short: return {_fmt(ls['total_return'])}, "
                  f"Sharpe {_fmt(ls['sharpe'], '.2f')}, maxDD {_fmt(ls['max_drawdown'])}")
        else:
            print(f"  backtest skipped: {backtest['error']}")

        print("\nRetraining final model on all labeled data...")
        model = train_final_model(panel)
        record = save_artifact(
            db,
            model,
            horizon=args.horizon,
            metrics=aggregate,
            folds=folds,
            backtest=backtest,
            train_start=panel["date"].min().date(),
            train_end=panel["date"].max().date(),
            calibration=calibration,
            target="cross_sectional",
        )
        print(f"Saved artifact {record.version} → {record.artifact_path}")

        print("\nScoring screener snapshots with the new model...")
        from app.services.prediction import score_all_snapshots

        print(" ", score_all_snapshots(db))
    finally:
        db.close()


if __name__ == "__main__":
    main()
