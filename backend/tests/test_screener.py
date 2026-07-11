from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import ScreenerSnapshot, Ticker
from app.services.screener import run_screen


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    rows = [
        dict(symbol="AAA", sector="Technology", price=50, rsi_14=75, change_1m=0.10,
             market_cap=5e10, ai_prob_up=0.62),
        dict(symbol="BBB", sector="Technology", price=200, rsi_14=45, change_1m=-0.05,
             market_cap=2e11, ai_prob_up=0.48),
        dict(symbol="CCC", sector="Energy", price=80, rsi_14=72, change_1m=0.03,
             market_cap=8e10, ai_prob_up=None),
    ]
    for r in rows:
        session.add(Ticker(symbol=r["symbol"], is_active=True))
        session.add(ScreenerSnapshot(as_of_date=date(2026, 7, 10), **r))
    session.commit()
    yield session
    session.close()


def test_no_filters_returns_all(db):
    rows, total = run_screen(db, {})
    assert total == 3


def test_range_and_sector_filters(db):
    rows, total = run_screen(db, {"min_rsi": 70, "sector": "Technology"})
    assert total == 1
    assert rows[0].symbol == "AAA"


def test_price_range(db):
    rows, total = run_screen(db, {"min_price": 60, "max_price": 100})
    assert [r.symbol for r in rows] == ["CCC"]


def test_sort_and_direction(db):
    rows, _ = run_screen(db, {"sort_by": "price", "sort_dir": "asc"})
    assert [r.symbol for r in rows] == ["AAA", "CCC", "BBB"]


def test_sort_whitelist_rejects_unknown_column(db):
    # unknown sort key falls back to market_cap desc instead of erroring
    rows, _ = run_screen(db, {"sort_by": "__table__"})
    assert [r.symbol for r in rows] == ["BBB", "CCC", "AAA"]


def test_ai_prob_filter_excludes_nulls(db):
    rows, total = run_screen(db, {"min_ai_prob": 0.5})
    assert [r.symbol for r in rows] == ["AAA"]


def test_pagination(db):
    rows, total = run_screen(db, {"sort_by": "price", "sort_dir": "asc", "limit": 2, "offset": 2})
    assert total == 3
    assert [r.symbol for r in rows] == ["BBB"]
