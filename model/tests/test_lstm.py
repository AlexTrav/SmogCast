import numpy as np
import pandas as pd

import lstm
import prep


def frame(hours: int = 24 * 20) -> pd.DataFrame:
    index = pd.date_range("2024-03-01", periods=hours, freq="h", tz=prep.TZ)
    rng = np.random.default_rng(0)
    return pd.DataFrame({"pm2_5": np.exp(3 + rng.normal(0, 0.3, hours)), "temp": rng.normal(0, 5, hours),
                         "wind": rng.uniform(0, 10, hours), "precip": rng.exponential(0.2, hours)}, index=index)


def test_calendar_shape_and_daily_period():
    index = pd.date_range("2024-03-01", periods=48, freq="h", tz=prep.TZ)
    cal = lstm.calendar(index)
    assert cal.shape == (48, 4) and np.allclose(cal[:24, :2], cal[24:, :2])


def test_train_positions_keep_targets_before_end():
    data = frame()
    end = data.index[24 * 15]
    positions = lstm.train_positions(data.index, end)
    assert positions[0] == lstm.LOOKBACK - 1
    assert data.index[positions[-1] + lstm.HORIZON] < end  # последняя цель – строго до начала проверки


def test_samples_align_history_and_future():
    data = frame()
    norm = lstm.fit_norm(data, lstm.WEATHER)
    positions = np.array([lstm.LOOKBACK - 1, lstm.LOOKBACK + 10])
    past, future, target = lstm.build_samples(data, positions, lstm.WEATHER, norm)
    assert past.shape == (2, lstm.LOOKBACK, 1 + 4 + 3) and future.shape == (2, lstm.HORIZON, 4 + 3)
    log_pm = np.log(data["pm2_5"].to_numpy())
    i = positions[1]
    # последний шаг истории – сам момент прогноза, цель – приращения к нему
    assert np.isclose(past[1, -1, 0], (log_pm[i] - norm["pm_mean"]) / norm["pm_std"], atol=1e-5)
    assert np.allclose(target[1], log_pm[i + 1:i + 1 + lstm.HORIZON] - log_pm[i], atol=1e-5)
    assert np.allclose(future[1, :, :4], lstm.calendar(data.index[i + 1:i + 1 + lstm.HORIZON]))


def test_samples_without_weather():
    data = frame()
    norm = lstm.fit_norm(data, ())
    past, future, _ = lstm.build_samples(data, np.array([lstm.LOOKBACK - 1]), (), norm)
    assert past.shape[2] == 5 and future.shape[2] == 4 and "weather_mean" not in norm
