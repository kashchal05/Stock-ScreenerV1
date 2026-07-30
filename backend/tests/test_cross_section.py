import numpy as np
import pandas as pd
import pytest

from app.ml.cross_section import XS_FEATURE_COLUMNS, add_cross_sectional_features
from app.ml.labeling import cross_sectional_labels
from app.ml.train import _rank_ic, fit_calibration
from app.ml.inference import apply_calibration


def make_panel(n_dates=5, n_symbols=20, seed=0):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2024-01-01", periods=n_dates)
    rows = []
    for d in dates:
        for s in range(n_symbols):
            rows.append(
                {
                    "symbol": f"S{s}",
                    "date": d,
                    "mom_12_1": rng.normal(),
                    "mom_6_1": rng.normal(),
                    "ret_21d": rng.normal(),
                    "rsi_14": rng.uniform(0, 100),
                    "vol_21d": rng.uniform(0, 1),
                    "close_sma200_ratio": rng.normal(),
                    "rel_ret_21d": rng.normal(),
                    "pos_52w": rng.uniform(0, 1),
                    "fwd_ret": rng.normal(),
                }
            )
    return pd.DataFrame(rows)


def test_xs_features_are_within_date_ranks():
    panel = make_panel()
    out = add_cross_sectional_features(panel)
    for col in XS_FEATURE_COLUMNS:
        assert col in out.columns
        # ranks are in (0, 1]
        assert out[col].between(0, 1).all()
    # within each date, ranks span the full 0..1 range
    grp = out.groupby("date")["xs_ret_21d"]
    assert grp.max().min() == pytest.approx(1.0)


def test_xs_ranks_no_cross_date_leakage():
    """Mutating one date's values must not change another date's ranks."""
    panel = make_panel()
    baseline = add_cross_sectional_features(panel)
    last_date = panel["date"].max()

    mutated = panel.copy()
    mask = mutated["date"] == last_date
    mutated.loc[mask, "ret_21d"] = 999.0
    after = add_cross_sectional_features(mutated)

    earlier = baseline["date"] != last_date
    pd.testing.assert_series_equal(
        baseline.loc[earlier, "xs_ret_21d"], after.loc[earlier, "xs_ret_21d"]
    )


def test_cross_sectional_labels_balanced():
    panel = make_panel(n_dates=10, n_symbols=40)
    labels = cross_sectional_labels(panel, forward_col="fwd_ret")
    # above-median split -> ~50% ones, per date and overall
    assert labels.mean() == pytest.approx(0.5, abs=0.02)


def test_cross_sectional_labels_are_within_date():
    # one date where everything is positive should still be ~half 1s (relative)
    dates = pd.bdate_range("2024-01-01", periods=1).repeat(10)
    panel = pd.DataFrame({"date": dates, "fwd_ret": np.arange(10) + 1.0})
    labels = cross_sectional_labels(panel, forward_col="fwd_ret")
    assert labels.sum() == 5  # top 5 of 10 beat the median


def test_rank_ic_detects_signal():
    dates = pd.bdate_range("2024-01-01", periods=3).repeat(30)
    fwd = pd.Series(np.tile(np.linspace(-1, 1, 30), 3))
    perfect = fwd.to_numpy()  # prob perfectly ordered with outcome
    ic = _rank_ic(pd.Series(dates), perfect, fwd)
    assert ic > 0.99
    rng = np.random.default_rng(1)
    noise = rng.normal(size=len(fwd))
    ic_noise = _rank_ic(pd.Series(dates), noise, fwd)
    assert abs(ic_noise) < 0.5


def test_calibration_is_monotonic():
    rng = np.random.default_rng(2)
    prob = rng.uniform(0, 1, 5000)
    labels = (rng.uniform(0, 1, 5000) < prob).astype(float)  # well-correlated
    calib = fit_calibration(prob, labels)
    y = np.array(calib["y"])
    assert np.all(np.diff(y) >= -1e-9)  # non-decreasing
    # apply is monotonic and bounded
    assert apply_calibration(0.2, calib) <= apply_calibration(0.8, calib)
    assert 0 <= apply_calibration(0.5, calib) <= 1
