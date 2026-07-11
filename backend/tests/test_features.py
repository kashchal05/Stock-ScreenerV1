import numpy as np
import pandas as pd
import pytest

from app.ml.features import FEATURE_COLUMNS, compute_features, rsi


def make_bars(closes: list[float]) -> pd.DataFrame:
    closes = pd.Series(closes, dtype=float)
    dates = pd.bdate_range("2024-01-01", periods=len(closes)).date
    return pd.DataFrame(
        {
            "open": closes.values,
            "high": closes.values * 1.01,
            "low": closes.values * 0.99,
            "close": closes.values,
            "volume": np.full(len(closes), 1_000_000.0),
        },
        index=pd.Index(dates, name="date"),
    )


def test_feature_columns_all_computed():
    bars = make_bars(list(np.linspace(100, 130, 300)))
    features = compute_features(bars)
    assert list(features.columns) == FEATURE_COLUMNS


def test_returns_match_hand_computed():
    closes = [100, 102, 101, 105, 110, 108]
    bars = make_bars(closes)
    features = compute_features(bars)
    assert features["ret_1d"].iloc[-1] == pytest.approx(108 / 110 - 1)
    assert features["ret_5d"].iloc[-1] == pytest.approx(108 / 100 - 1)


def test_rsi_bounds_and_direction():
    rising = rsi(pd.Series(np.linspace(100, 200, 60)))
    falling = rsi(pd.Series(np.linspace(200, 100, 60)))
    assert rising.iloc[-1] == pytest.approx(100, abs=1e-6)
    assert falling.iloc[-1] == pytest.approx(0, abs=1e-6)

    rng = np.random.default_rng(7)
    noisy = rsi(pd.Series(100 + rng.normal(0, 1, 200).cumsum()))
    assert noisy.dropna().between(0, 100).all()


def test_sma_ratio_hand_computed():
    closes = list(np.full(19, 100.0)) + [120.0]
    bars = make_bars(closes)
    features = compute_features(bars)
    sma20 = (19 * 100 + 120) / 20
    assert features["close_sma20_ratio"].iloc[-1] == pytest.approx(120 / sma20 - 1)


def test_no_lookahead():
    """Mutating future rows must not change past feature values."""
    rng = np.random.default_rng(42)
    closes = list(100 + rng.normal(0, 2, 300).cumsum())
    bars = make_bars(closes)
    baseline = compute_features(bars)

    mutated_bars = bars.copy()
    mutated_bars.iloc[250:, mutated_bars.columns.get_loc("close")] = 9999.0
    mutated = compute_features(mutated_bars)

    pd.testing.assert_frame_equal(baseline.iloc[:250], mutated.iloc[:250])


def test_52w_position():
    closes = list(np.linspace(100, 200, 260))
    bars = make_bars(closes)
    features = compute_features(bars)
    # Monotonically rising: last close is the 52w high
    assert features["pos_52w"].iloc[-1] == pytest.approx(1.0)
    assert features["pct_off_52w_high"].iloc[-1] == pytest.approx(0.0)


def test_spy_relative_return():
    bars = make_bars(list(np.linspace(100, 150, 100)))
    spy = make_bars(list(np.linspace(100, 110, 100)))
    features = compute_features(bars, spy_close=spy["close"])
    expected = bars["close"].pct_change(21).iloc[-1] - spy["close"].pct_change(21).iloc[-1]
    assert features["rel_ret_21d"].iloc[-1] == pytest.approx(expected)
