import numpy as np
import pandas as pd

import arima
import backtest
import baselines
import prep


# синтетический ln-ряд: суточный цикл плюс AR(1)-шум – ARIMA должна обыгрывать «последнее значение» на сутках
def synthetic(days: int = 60, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    n = days * 24
    noise = np.zeros(n)
    for i in range(1, n):
        noise[i] = 0.8 * noise[i - 1] + rng.normal(0, 0.1)
    hours = np.arange(n) % 24
    index = pd.date_range("2024-01-01", periods=n, freq="h", tz=prep.TZ)
    return pd.Series(3 + 0.4 * np.sin(2 * np.pi * hours / 24) + noise, index=index)


def test_harmonics_shape_and_period():
    index = pd.date_range("2024-01-01", periods=48, freq="h", tz=prep.TZ)
    x = arima.harmonics(index, 3)
    assert x.shape == (48, 6) and np.allclose(x[:24], x[24:])
    assert arima.harmonics(index, 0) is None
    full = arima.harmonics(index, 12)
    assert full.shape == (48, 23) and (np.abs(full).max(axis=0) > 0.5).all()  # нет пустой колонки sin(π·час)


def test_predict_uses_new_observations_without_refit():
    series = synthetic(30)
    model = arima.Arima((1, 1, 0), k=2, window_days=14)
    model.fit(series.iloc[:500])
    first = model.predict(series.iloc[:500], 24)
    second = model.predict(series.iloc[:506], 24)  # +6 часов наблюдений
    assert model.end == series.index[505]
    assert not np.allclose(first[6:], second[:18])  # прогноз обновился по новым часам
    lower, upper = model.intervals()[0.8]
    assert lower.shape == (24,) and (lower <= second + 1e-9).all() and (upper >= second - 1e-9).all()


def test_harmonic_arima_beats_persistence_on_daily_cycle():
    series = synthetic(60)
    at = backtest.origins(series, series.index[24 * 30], None, horizon=24)
    model = arima.Arima((1, 1, 0), k=2, window_days=21)
    result = backtest.run(model, series, at, horizon=24)
    naive = backtest.run(baselines.Persistence(), series, at, horizon=24)
    assert result.native is not None and set(result.native) == {0.8, 0.95}
    assert backtest.horizon_metrics(result)["mae"][6:].mean() < backtest.horizon_metrics(naive)["mae"][6:].mean()


def test_forecast_is_clipped_to_plausible_range():
    series = synthetic(20)
    model = arima.Arima((1, 1, 0), k=1, window_days=10)
    model.fit(series)
    forecast = model.predict(series, 72)
    assert (forecast >= arima.LOW).all() and (forecast <= arima.HIGH).all()


def test_candidates_cover_both_families():
    options = arima.candidates()
    assert all(any(s) for _, s, _ in options["sarima"]) and all(k > 0 for _, _, k in options["harmonic"])
