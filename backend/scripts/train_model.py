"""Train the direction classifier: dataset -> walk-forward eval -> backtest -> artifact.

Usage: .venv/bin/python scripts/train_model.py [--horizon 10]

Expect aggregate AUC around 0.52-0.58. If you see 0.75+, hunt for leakage
before celebrating.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.ml.artifacts import save_artifact
from app.ml.backtest import run_backtest
from app.ml.dataset import build_dataset
from app.ml.train import train_final_model, walk_forward_evaluate
from app.services.market_data import load_bars
from app.services.universe import BENCHMARK_SYMBOL, active_symbols


def build_closes_panel(db) -> pd.DataFrame:
    frames = []
    for symbol in active_symbols(db, include_benchmark=False):
        bars = load_bars(db, symbol)
        if bars.empty:
            continue
        frame = bars[["close"]].reset_index()
        frame["symbol"] = symbol
        frames.append(frame)
    panel = pd.concat(frames, ignore_index=True)
    panel["date"] = pd.to_datetime(panel["date"])
    return panel


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--horizon", type=int, default=settings.prediction_horizon_days)
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        print(f"Building dataset (horizon={args.horizon} trading days)...")
        panel = build_dataset(db, horizon=args.horizon)
        if panel.empty:
            sys.exit("No data — run scripts/refresh_data.py first")
        print(f"  {len(panel):,} rows, {panel['symbol'].nunique()} symbols, "
              f"{panel['date'].min().date()} → {panel['date'].max().date()}")
        print(f"  positive base rate: {panel['label'].mean():.4f}")

        print("\nWalk-forward evaluation (5 folds, 6-month test windows, embargoed)...")
        aggregate, folds = walk_forward_evaluate(panel, horizon=args.horizon)

        print(f"\n{'fold':<6}{'test window':<26}{'acc':<8}{'base':<8}{'auc':<8}{'p@0.60':<8}")
        for fold in folds:
            m = fold["metrics"]
            auc = f"{m['roc_auc']:.4f}" if m["roc_auc"] else "n/a"
            p60 = f"{m['precision_at_0.6']:.4f}" if m.get("precision_at_0.6") else "n/a"
            print(f"{fold['fold']:<6}{fold['test_start']} → {fold['test_end']:<12}"
                  f"{m['accuracy']:<8.4f}{m['base_rate']:<8.4f}{auc:<8}{p60:<8}")
        auc = f"{aggregate['roc_auc']:.4f}" if aggregate["roc_auc"] else "n/a"
        print(f"\nAggregate: accuracy={aggregate['accuracy']:.4f} "
              f"(base rate {aggregate['base_rate']:.4f}), AUC={auc}")
        if aggregate["roc_auc"] and aggregate["roc_auc"] > 0.70:
            print("WARNING: AUC suspiciously high for this problem — check for leakage.")

        print("\nBacktesting top-20 strategy on walk-forward test windows...")
        closes = build_closes_panel(db)
        spy = load_bars(db, BENCHMARK_SYMBOL)
        backtest = run_backtest(folds, closes, spy["close"], horizon=args.horizon)
        if "error" not in backtest:
            print(f"  strategy total return: {backtest['total_return']:+.2%} "
                  f"vs SPY {backtest['spy_total_return']:+.2%} "
                  f"({backtest['start']} → {backtest['end']})")
            print(f"  max drawdown: {backtest['max_drawdown']:.2%}, "
                  f"hit rate: {backtest['hit_rate']:.2%} over {backtest['n_periods']} periods")

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
        )
        print(f"Saved artifact {record.version} → {record.artifact_path}")

        print("\nScoring screener snapshots with the new model...")
        from app.services.prediction import score_all_snapshots

        print(" ", score_all_snapshots(db))
    finally:
        db.close()


if __name__ == "__main__":
    main()
