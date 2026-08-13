"""Seed the model track record from leak-free walk-forward predictions.

For each rebalance date in the walk-forward test windows (every `horizon` trading
days, matching the backtest), log the top-K picks by predicted probability along
with their realized forward return. Because each fold's predictions come from a
model trained only on prior data, this is a genuine out-of-sample record.

Usage: .venv/bin/python scripts/seed_picks.py [--horizon 21] [--top-k 20]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.ml.dataset import build_dataset
from app.ml.train import walk_forward_evaluate
from app.models import ModelVersion, PickLog, WfPrediction
from app.services.market_data import load_bars
from app.services.universe import BENCHMARK_SYMBOL


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--horizon", type=int, default=settings.prediction_horizon_days)
    parser.add_argument("--top-k", type=int, default=20)
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        active = db.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).first()
        version = active.version if active else None

        print(f"Building dataset (horizon={args.horizon})...")
        panel = build_dataset(db, horizon=args.horizon)
        if panel.empty:
            sys.exit("No data — run scripts/refresh_data.py first")

        print("Walk-forward evaluation (leak-free out-of-sample predictions)...")
        _, folds = walk_forward_evaluate(panel, horizon=args.horizon)
        preds = pd.concat([f["test_predictions"] for f in folds], ignore_index=True)
        preds = preds.dropna(subset=["fwd_ret"])

        # SPY forward return per date (same horizon), for the benchmark column.
        spy = load_bars(db, BENCHMARK_SYMBOL)
        spy_fwd = (spy["close"].shift(-args.horizon) / spy["close"] - 1) if not spy.empty else None

        # Store the FULL out-of-sample prediction panel so the backtester can rank
        # the whole universe by the model's leak-free score on any date.
        print("Storing full walk-forward prediction panel...")
        db.query(WfPrediction).delete()
        db.commit()
        wf_records = [
            {"date": pd.Timestamp(r.date).date(), "symbol": r.symbol, "prob": float(r.prob)}
            for r in preds.itertuples(index=False)
        ]
        db.bulk_insert_mappings(WfPrediction, wf_records)
        db.commit()
        print(f"  stored {len(wf_records)} predictions")

        # Replace any previously seeded backtest picks (idempotent).
        db.query(PickLog).filter(PickLog.source == "backtest").delete()
        db.commit()

        trade_dates = sorted(preds["date"].unique())
        logged = 0
        i = 0
        while i < len(trade_dates):
            day = trade_dates[i]
            top = preds[preds["date"] == day].nlargest(args.top_k, "prob")
            as_of = pd.Timestamp(day).date()
            spy_ret = None
            if spy_fwd is not None:
                prior = spy_fwd[spy_fwd.index <= as_of]
                spy_ret = float(prior.iloc[-1]) if len(prior) and pd.notna(prior.iloc[-1]) else None
            for rank, (_, row) in enumerate(top.iterrows(), start=1):
                db.add(
                    PickLog(
                        as_of_date=as_of,
                        symbol=row["symbol"],
                        prob=float(row["prob"]),
                        rank=rank,
                        horizon_days=args.horizon,
                        realized_return=float(row["fwd_ret"]),
                        spy_return=spy_ret,
                        model_version=version,
                        source="backtest",
                    )
                )
                logged += 1
            i += args.horizon
        db.commit()
        print(f"Seeded {logged} picks across {logged // max(args.top_k,1)} rebalance dates.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
