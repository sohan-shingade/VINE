"""Feature engineering tests — rolling stats, lags, growing degree-days."""

import pandas as pd

from vine.d1_pipeline import features


def test_rolling_features_appends_mean_std():
    idx = pd.date_range("2025-08-01", periods=4, freq="1h")
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0]}, index=idx)
    out = features.rolling_features(df, "x", ("2h",))
    assert "x_mean_2h" in out.columns and "x_std_2h" in out.columns
    assert out["x_mean_2h"].iloc[1] == 1.5  # mean(1, 2)


def test_lag_features_shift():
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0]})
    out = features.lag_features(df, "x", (1,))
    assert pd.isna(out["x_lag_1"].iloc[0])  # no history yet -> unknown, not zero
    assert out["x_lag_1"].iloc[1] == 1.0


def test_growing_degree_days_cumulative():
    idx = pd.date_range("2025-08-01", periods=3, freq="1D")
    temp = pd.Series([12.0, 20.0, 8.0], index=idx)  # contributions 2, 10, 0
    gdd = features.growing_degree_days(temp, base=10.0)
    assert list(gdd) == [2.0, 12.0, 12.0]  # cumulative, base-10 clipped at 0
