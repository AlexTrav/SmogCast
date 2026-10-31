import numpy as np
import pandas as pd
import pytest

import arima
import backtest
import prep
import weather


# синтетический архив: в колонке <переменная>_d<N> записано число N – по нему видно, какой прогноз взят
@pytest.fixture
def lead_archive(monkeypatch):
    index = pd.date_range("2024-03-01", periods=24 * 20, freq="h", tz=prep.TZ)
    frame = pd.DataFrame({f"{v}_d{n}": float(n) for v in ("temp", "wind") for n in range(5)}, index=index)
    monkeypatch.setattr(weather, "archive", lambda: frame)
    return frame


def test_lead_days_keep_publication_margin():
    assert [weather.lead_days(h) for h in (1, 18, 19, 42, 43, 66, 67, 72)] == [1, 1, 2, 2, 3, 3, 4, 4]
    # прогноз на час t+h выпущен за lead_days(h) суток до него – не позже t − 6 ч
    assert all(h - 24 * weather.lead_days(h) <= -weather.PUBLISH_HOURS for h in range(1, 73))


def test_future_uses_only_published_forecasts(lead_archive):
    origin = lead_archive.index[24 * 5]
    x = weather.future(origin, 72, ("temp", "wind"))
    assert x.shape == (72, 2)
    assert list(x[:, 0]) == [weather.lead_days(h) for h in range(1, 73)]


def test_history_uses_current_run(lead_archive):
    x = weather.history(lead_archive.index[:10], ("temp",))
    assert (x == 0).all()


def test_future_without_forecast_is_an_error(lead_archive):
    with pytest.raises(ValueError):
        weather.future(lead_archive.index[-10], 72, ("temp",))


def test_precip_is_log_transformed():
    assert np.allclose(weather.transform("precip", np.array([0.0, np.e - 1, -1.0])), [0, 1, 0])
    assert np.allclose(weather.transform("temp", np.array([-5.0])), [-5.0])


# ln PM2.5 зависит от температуры, которую модель знает из прогноза: ARIMA с погодой должна выиграть на сутках
def test_arima_with_temperature_beats_plain(monkeypatch):
    rng = np.random.default_rng(3)
    index = pd.date_range("2024-03-01", periods=24 * 70, freq="h", tz=prep.TZ)
    temp = np.cumsum(rng.normal(0, 0.6, len(index)))  # медленно блуждающая «температура»
    frame = pd.DataFrame({f"temp_d{n}": temp + rng.normal(0, 0.2 * n, len(index)) for n in range(5)}, index=index)
    monkeypatch.setattr(weather, "archive", lambda: frame)
    monkeypatch.setattr(weather, "START", index[0])
    series = pd.Series(3 - 0.05 * temp + rng.normal(0, 0.05, len(index)), index=index)
    at = backtest.origins(series, index[24 * 40], None, horizon=48)[::4]
    plain = backtest.run(arima.Arima((1, 1, 0), k=1, window_days=30), series, at, horizon=48)
    with_temp = backtest.run(arima.Arima((1, 1, 0), k=1, window_days=30, weather_vars=("temp",)), series, at,
                             horizon=48)
    assert backtest.horizon_metrics(with_temp)["mae"][24:].mean() < backtest.horizon_metrics(plain)["mae"][24:].mean()
    assert "прогноз погоды (температура)" in with_temp.name


def test_dm_test_detects_better_model():
    rng = np.random.default_rng(4)
    index = pd.date_range("2025-01-01", periods=300, freq="6h", tz=prep.TZ)
    actual = np.log(20 + rng.normal(0, 1, (300, 24)) ** 2)
    good = backtest.Result("good", index, actual + rng.normal(0, 0.05, actual.shape), actual)
    bad = backtest.Result("bad", index, actual + rng.normal(0, 0.3, actual.shape), actual)
    test = backtest.dm_test(good, bad)
    assert test["mae_diff"] < 0 and test["p_value"] < 0.01
    assert backtest.dm_test(good, good)["p_value"] == 1.0
