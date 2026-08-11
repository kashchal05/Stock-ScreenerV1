from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import ModelVersion, ScreenerSnapshot, Ticker
from app.services import advisor


@pytest.fixture()
def db(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    session.add(ModelVersion(version="vTEST", horizon_days=21, artifact_path="/x", is_active=True))
    # 10 tech names (to exercise the sector cap) + a couple others
    rows = []
    for i in range(10):
        rows.append(("T%d" % i, "Information Technology", 50.0, 0.60 - i * 0.001))
    rows += [("EEE", "Energy", 80.0, 0.55), ("FFF", "Financials", 40.0, 0.54)]
    for sym, sector, price, prob in rows:
        session.add(Ticker(symbol=sym, sector=sector, is_active=True))
        session.add(ScreenerSnapshot(symbol=sym, name=sym, sector=sector, as_of_date=date(2026, 7, 10),
                                     price=price, ai_prob_up=prob))
    session.commit()

    # Stub the market + track record so the test doesn't need bar data.
    monkeypatch.setattr(advisor, "assess_market", lambda _db: {
        "available": True, "as_of": "2026-07-10", "regime": "Risk-on uptrend", "stance": "risk_on",
        "trend_up": True, "spy_vs_200d": 0.09, "volatility_annualized": 0.15,
        "volatility_vs_normal": 1.0, "high_vol": False, "breadth": 0.66,
    })
    import app.services.picks as picks
    monkeypatch.setattr(picks, "get_track_record", lambda _db: {"available": False})
    yield session
    session.close()


def test_plan_respects_sector_cap_and_sizes_positions(db):
    plan = advisor.build_plan(db, capital=10000)
    assert plan["available"]
    # sector cap: at most SECTOR_CAP tech names despite 10 being highest-ranked
    tech = [p for p in plan["picks"] if p["sector"] == "Information Technology"]
    assert len(tech) <= advisor.SECTOR_CAP
    # every pick is affordable and whole-share
    for p in plan["picks"]:
        assert p["shares"] >= 1
        assert p["allocation"] == pytest.approx(p["shares"] * p["price"])
    # weights sum to ~1 and we never overspend
    assert plan["invested"] <= 10000
    assert sum(p["weight"] for p in plan["picks"]) == pytest.approx(1.0, abs=1e-6)


def test_plan_needs_a_model(db):
    db.query(ModelVersion).update({"is_active": False})
    db.commit()
    assert advisor.build_plan(db, capital=10000) == {"available": False, "reason": "no_model"}
