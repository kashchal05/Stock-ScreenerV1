"""Known-answer tests for the backtest engine. A backtester with a silent bug is
worse than none, so we pin its behavior against hand-computable cases."""

import numpy as np
import pandas as pd
import pytest

from app.backtest.engine import simulate
from app.backtest.spec import StrategySpec


def _dates(n):
    return pd.bdate_range("2020-01-01", periods=n)


def test_buy_and_hold_single_stock_matches_price_return():
    # One stock, top_k=1: the strategy always holds it. With zero costs, the total
    # return should match the stock's close-to-close return over the invested window.
    n = 260
    dates = _dates(n)
    prices = pd.Series(np.linspace(100, 200, n), index=dates)
    closes = pd.DataFrame({"AAA": prices})
    signal = pd.DataFrame({"AAA": pd.Series(1.0, index=dates)})  # constant signal
    bench = pd.Series(np.linspace(100, 110, n), index=dates)

    spec = StrategySpec(signal="mom_12_1", top_k=1, rebalance_days=21, costs_bps=0)
    res = simulate(closes, signal, bench, spec)
    assert res.get("ok")

    # Entered at the first rebalance close, exited at the last rebalance close.
    start, end = pd.Timestamp(res["start"]), pd.Timestamp(res["end"])
    expected = prices.loc[end] / prices.loc[start] - 1
    assert res["metrics"]["total_return"] == pytest.approx(expected, rel=1e-6)


def test_equal_weight_two_stocks_is_average():
    n = 260
    dates = _dates(n)
    a = pd.Series(np.linspace(100, 300, n), index=dates)   # +200%
    b = pd.Series(np.linspace(100, 100, n), index=dates)   # flat
    closes = pd.DataFrame({"AAA": a, "BBB": b})
    signal = pd.DataFrame({"AAA": pd.Series(1.0, index=dates), "BBB": pd.Series(1.0, index=dates)})
    bench = pd.Series(np.linspace(100, 105, n), index=dates)

    spec = StrategySpec(top_k=2, rebalance_days=21, costs_bps=0)
    res = simulate(closes, signal, bench, spec)
    # Equal-weight daily return is the mean of the two daily returns; over the window
    # the compounded result sits between the flat stock and the strong one.
    tr = res["metrics"]["total_return"]
    assert 0.5 < tr < 2.0  # between flat (0) and +200%, closer to a blend


def test_costs_reduce_return():
    n = 300
    dates = _dates(n)
    rng = np.random.default_rng(3)
    closes = pd.DataFrame(
        {f"S{i}": pd.Series(100 * np.cumprod(1 + rng.normal(0.0005, 0.02, n)), index=dates) for i in range(10)}
    )
    signal = pd.DataFrame(
        {c: pd.Series(rng.normal(size=n), index=dates) for c in closes.columns}  # random -> churn
    )
    bench = pd.Series(np.linspace(100, 120, n), index=dates)

    free = simulate(closes, signal, bench, StrategySpec(top_k=3, rebalance_days=21, costs_bps=0))
    costly = simulate(closes, signal, bench, StrategySpec(top_k=3, rebalance_days=21, costs_bps=50))
    assert costly["metrics"]["total_return"] < free["metrics"]["total_return"]
    assert costly["metrics"]["avg_turnover"] > 0


def test_target_weights_schemes():
    from app.backtest.weighting import target_weights

    # inverse-vol: half the vol -> double the weight
    w = target_weights(["A", "B"], vols={"A": 0.01, "B": 0.02}, scheme="inverse_vol")
    assert w["A"] == pytest.approx(2 / 3)
    assert w["B"] == pytest.approx(1 / 3)
    # missing vol -> neutral (average inverse) fill
    w2 = target_weights(["A", "B", "C"], vols={"A": 0.01, "B": 0.01}, scheme="inverse_vol")
    assert w2["C"] == pytest.approx(w2["A"])
    # no usable vols -> equal weight fallback
    w3 = target_weights(["A", "B"], vols={"A": 0.0, "B": None}, scheme="inverse_vol")
    assert w3["A"] == pytest.approx(0.5)
    # equal
    assert target_weights(["A", "B", "C"])["A"] == pytest.approx(1 / 3)


def test_simulate_inverse_vol_overweights_low_vol_winner():
    n = 260
    dates = _dates(n)
    winner = pd.Series(np.linspace(100, 200, n), index=dates)   # low-vol, goes up
    flat = pd.Series(np.linspace(100, 100, n), index=dates)     # high-vol, flat
    closes = pd.DataFrame({"AAA": winner, "BBB": flat})
    signal = pd.DataFrame({"AAA": pd.Series(1.0, index=dates), "BBB": pd.Series(1.0, index=dates)})
    vol = pd.DataFrame({"AAA": pd.Series(0.01, index=dates), "BBB": pd.Series(0.02, index=dates)})
    bench = pd.Series(np.linspace(100, 105, n), index=dates)

    base = StrategySpec(top_k=2, rebalance_days=21, costs_bps=0)
    inv = StrategySpec(top_k=2, rebalance_days=21, costs_bps=0, weighting="inverse_vol")
    eq_res = simulate(closes, signal, bench, base)
    iv_res = simulate(closes, signal, bench, inv, vol_panel=vol)
    # inverse-vol overweights the low-vol winner, so it should beat equal weight here
    assert iv_res["metrics"]["total_return"] > eq_res["metrics"]["total_return"]


def test_ai_signal_panel_pivots_predictions():
    from datetime import date as _date

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.backtest.engine import _ai_signal_panel
    from app.database import Base
    from app.models import WfPrediction

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all([
        WfPrediction(date=_date(2025, 1, 2), symbol="AAA", prob=0.6),
        WfPrediction(date=_date(2025, 1, 2), symbol="BBB", prob=0.4),
        WfPrediction(date=_date(2025, 1, 3), symbol="AAA", prob=0.55),
    ])
    db.commit()

    panel = _ai_signal_panel(db, cache_key="test-key-1")
    assert list(panel.columns) == ["AAA", "BBB"]
    assert panel.loc[panel.index[0], "AAA"] == pytest.approx(0.6)

    # empty (but valid) DB -> empty panel
    empty_engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(empty_engine)
    empty = _ai_signal_panel(sessionmaker(bind=empty_engine)(), cache_key="empty-key")
    assert empty.empty
    db.close()


def test_selection_picks_top_signal():
    n = 260
    dates = _dates(n)
    # Two stocks; AAA always has the higher signal, so top-1/top direction holds AAA.
    strong = pd.Series(np.linspace(100, 400, n), index=dates)
    weak = pd.Series(np.linspace(100, 90, n), index=dates)
    closes = pd.DataFrame({"AAA": strong, "BBB": weak})
    signal = pd.DataFrame(
        {"AAA": pd.Series(2.0, index=dates), "BBB": pd.Series(1.0, index=dates)}
    )
    bench = pd.Series(np.linspace(100, 105, n), index=dates)

    res = simulate(closes, signal, bench, StrategySpec(top_k=1, direction="top", rebalance_days=21, costs_bps=0))
    assert res["latest_holdings"][0]["symbol"] == "AAA"
    assert res["metrics"]["total_return"] > 1.0  # rode the strong stock up
