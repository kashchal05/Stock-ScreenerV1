"""Seed the ticker universe from Wikipedia's S&P 500 list (CSV fallback).

Usage: .venv/bin/python scripts/seed_universe.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import Base, SessionLocal, engine
from app.services.universe import seed_universe


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        count = seed_universe(db)
        print(f"Seeded {count} tickers (+ SPY benchmark)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
