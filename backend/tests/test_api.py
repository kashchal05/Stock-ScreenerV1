from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import ScreenerSnapshot, Ticker


@pytest.fixture()
def client():
    # StaticPool keeps one shared connection so the in-memory DB persists across
    # sessions/threads (each new connection would otherwise get an empty DB).
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    session = TestingSession()
    for sym, name, sector, price, rsi in [
        ("AAPL", "Apple Inc.", "Information Technology", 200.0, 60.0),
        ("XOM", "Exxon Mobil", "Energy", 110.0, 45.0),
    ]:
        session.add(Ticker(symbol=sym, name=name, sector=sector, is_active=True))
        session.add(
            ScreenerSnapshot(
                symbol=sym, name=name, sector=sector, as_of_date=date(2026, 7, 10),
                price=price, rsi_14=rsi, market_cap=1e12,
            )
        )
    session.commit()
    session.close()

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_screener_returns_snapshots(client):
    r = client.get("/api/screener")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert {row["symbol"] for row in body["results"]} == {"AAPL", "XOM"}


def test_screener_filter_and_sort(client):
    r = client.get("/api/screener", params={"min_rsi": 50, "sort_by": "price", "sort_dir": "asc"})
    body = r.json()
    assert [row["symbol"] for row in body["results"]] == ["AAPL"]


def test_meta_lists_sectors(client):
    r = client.get("/api/meta")
    assert r.status_code == 200
    body = r.json()
    assert body["universe_size"] == 2
    assert "Energy" in body["sectors"]


def test_search_matches_symbol_and_name(client):
    assert client.get("/api/search", params={"q": "aap"}).json()[0]["symbol"] == "AAPL"
    assert client.get("/api/search", params={"q": "exxon"}).json()[0]["symbol"] == "XOM"
    assert client.get("/api/search", params={"q": "zzzz"}).json() == []


def test_unknown_stock_404(client):
    assert client.get("/api/stocks/NOTREAL").status_code == 404
