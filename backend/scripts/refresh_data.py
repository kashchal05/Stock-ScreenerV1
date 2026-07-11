"""Refresh market data from the CLI: bars, fundamentals, snapshots, AI scores.

Usage: .venv/bin/python scripts/refresh_data.py [--skip-fundamentals]

In a deployed environment this script is the cron entry point.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import Base, SessionLocal, engine
from app.services import market_data, snapshots


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-fundamentals", action="store_true")
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        print("Refreshing daily bars...")
        print(" ", market_data.refresh_bars(db))
        if not args.skip_fundamentals:
            print("Refreshing fundamentals (throttled, ~1 req/ticker when stale)...")
            print(" ", market_data.refresh_fundamentals(db))
        print("Rebuilding screener snapshots...")
        print(" ", snapshots.rebuild_snapshots(db))
        from app.services.prediction import score_all_snapshots

        print("Scoring snapshots with active model (if any)...")
        print(" ", score_all_snapshots(db))
    finally:
        db.close()


if __name__ == "__main__":
    main()
