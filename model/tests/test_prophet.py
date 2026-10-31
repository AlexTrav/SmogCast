import numpy as np
import pandas as pd

import backtest
import baselines
import prep
import prophet_model


# ln-ряд с суточным циклом и ступенью уровня в дату обновления CAMS 49R1 (12.11.2024)
def synthetic(start: str = "2024-10-01", days: int = 75, step: float = 0.5) -> pd.Series:
    index = pd.date_range(start, periods=days * 24, freq="h", tz=prep.TZ)
    hours = index.tz_convert("UTC").hour.to_numpy()
    rng = np.random.default_rng(0)
    level = np.where(index >= prep.CAMS_CYCLES[2][1], step, 0.0)
    return pd.Series(3 + 0.4 * np.sin(2 * np.pi * hours / 24) + level + rng.normal(0, 0.05, len(index)), index=index)


def test_cams_steps_switch_on_cycle_dates():
    ds = pd.Series(pd.to_datetime(["2023-06-26 23:00", "2023-06-27 00:00", "2024-11-12 12:00"]))
    steps = prophet_model.cams_steps(ds)
    assert steps["cams_48R1"].tolist() == [0.0, 1.0, 1.0]
    assert steps["cams_49R1"].tolist() == [0.0, 0.0, 1.0]


def test_prophet_learns_daily_cycle_and_cams_step():
    series = synthetic()
    model = prophet_model.ProphetModel(steps=True)
    model.fit(series)
    assert "cams_49R1" in model.model.extra_regressors and "cams_48R1" not in model.model.extra_regressors
    forecast = model.predict(series, 48)
    truth = 3.5 + 0.4 * np.sin(2 * np.pi * (series.index[-1].tz_convert("UTC").hour + np.arange(1, 49)) / 24)
    assert forecast.shape == (48,) and np.abs(forecast - truth).mean() < 0.1


def test_prophet_beats_persistence_on_daily_cycle():
    series = synthetic(days=60, step=0.0)
    at = backtest.origins(series, series.index[24 * 40], None, horizon=24)[::4]
    result = backtest.run(prophet_model.ProphetModel(), series, at, horizon=24)
    naive = backtest.run(baselines.Persistence(), series, at, horizon=24)
    assert backtest.horizon_metrics(result)["mae"][6:].mean() < backtest.horizon_metrics(naive)["mae"][6:].mean()
