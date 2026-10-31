import numpy as np
import pandas as pd
import pytest

import backtest
import baselines
import prep


def hourly(values, start="2024-01-01") -> pd.Series:
    index = pd.date_range(start, periods=len(values), freq="h", tz=prep.TZ)
    return pd.Series(np.asarray(values, dtype=float), index=index)


# модель-шпион: запоминает, какую историю ей дали, и прогнозирует последнее значение
class Spy:
    name = "spy"

    def __init__(self):
        self.fits, self.seen = [], []

    def fit(self, history):
        self.fits.append(history.index[-1])

    def predict(self, history, horizon):
        self.seen.append(history.index[-1])
        return np.full(horizon, history.iloc[-1])


def test_origins_only_report_hours_with_full_horizon():
    series = hourly(np.zeros(24 * 10))
    at = backtest.origins(series, series.index[0], None, horizon=72)
    assert set(at.hour) == {0, 6, 12, 18}
    assert at[-1] + pd.Timedelta(hours=72) <= series.index[-1]
    end = series.index[0] + pd.Timedelta(days=2)
    assert (backtest.origins(series, series.index[0], end) < end).all()


def test_model_never_sees_the_future_and_actuals_align():
    series = hourly(np.arange(24 * 20))
    at = backtest.origins(series, series.index[24 * 8], None, horizon=24)
    spy = Spy()
    result = backtest.run(spy, series, at, horizon=24)
    assert list(spy.seen) == list(at)  # история заканчивается ровно в момент прогноза
    first = int(np.where(series.index == at[0])[0][0])
    assert np.array_equal(result.actual[0], np.arange(first + 1, first + 25))


def test_refit_once_per_period():
    series = hourly(np.zeros(24 * 40))
    at = backtest.origins(series, series.index[24], None, horizon=24)
    spy = Spy()
    backtest.run(spy, series, at, horizon=24, refit_days=7)
    gaps = np.diff(pd.DatetimeIndex(spy.fits)) / pd.Timedelta(days=1)
    # прогнозы со 2 января по 8 февраля: подгонки 2, 9, 16, 23, 30 января и 6 февраля
    assert spy.fits[0] == at[0] and (gaps == 7).all() and len(spy.fits) == 6


# модель «помнит» момент подгонки: прогноз зависит от него, поэтому блоки обязаны совпасть с run()
class FitMemory:
    name = "fit-memory"

    def fit(self, history):
        self.level = history.iloc[-1]

    def predict(self, history, horizon):
        return np.full(horizon, self.level) + np.arange(horizon) * 0.01


def test_run_blocks_matches_sequential_run():
    series = hourly(np.random.default_rng(2).normal(3, 0.3, 24 * 60))
    at = backtest.origins(series, series.index[24 * 5], None, horizon=24)
    sequential = backtest.run(FitMemory(), series, at, horizon=24)
    blocks = backtest.refit_blocks(at)
    assert sum(len(b) for b in blocks) == len(at) and len(blocks) == len(set(b[0] for b in blocks))
    parallel = backtest.run_blocks(FitMemory, series, at, map, horizon=24)
    assert parallel.origins.equals(sequential.origins)
    assert np.array_equal(parallel.pred, sequential.pred) and np.array_equal(parallel.actual, sequential.actual)


def test_result_cache_roundtrip(tmp_path):
    series = hourly(np.random.default_rng(5).normal(3, 0.3, 24 * 20))
    result = backtest.run(baselines.Persistence(), series, backtest.origins(series, series.index[48], None,
                                                                           horizon=24), horizon=24)
    path = tmp_path / "cache" / "persistence.npz"
    backtest.save_result(result, path)
    loaded = backtest.load_result(path)
    assert loaded.name == result.name and loaded.origins.equals(result.origins)
    assert np.array_equal(loaded.pred, result.pred) and np.array_equal(loaded.actual, result.actual)


def test_train_start_cuts_history():
    series = hourly(np.zeros(24 * 20))
    at = backtest.origins(series, series.index[24 * 10], None, horizon=24)

    class Length(Spy):
        def predict(self, history, horizon):
            self.seen.append(len(history))
            return np.zeros(horizon)

    model = Length()
    backtest.run(model, series, at[:1], horizon=24, train_start=series.index[24 * 5])
    assert model.seen == [24 * 5 + 1]


def test_wrong_forecast_shape_is_an_error():
    class Short(Spy):
        def predict(self, history, horizon):
            return np.zeros(horizon - 1)

    series = hourly(np.zeros(24 * 10))
    with pytest.raises(ValueError):
        backtest.run(Short(), series, backtest.origins(series, series.index[24], None, horizon=24), horizon=24)


def test_metrics_on_known_values():
    y, f = np.array([[10.0, 20.0]]), np.array([[12.0, 10.0]])
    assert np.allclose(backtest.mae(y, f), [2, 10])
    assert np.allclose(backtest.rmse(np.array([[0.0], [0.0]]), np.array([[3.0], [4.0]])), [np.sqrt(12.5)])
    assert np.allclose(backtest.smape(y, f), [2 * 2 / 22 * 100, 2 * 10 / 30 * 100])


def test_persistence_error_grows_with_horizon():
    series = np.log(hourly(1 + np.arange(24 * 30)))
    at = backtest.origins(series, series.index[24 * 10], None, horizon=24)
    metrics = backtest.horizon_metrics(backtest.run(baselines.Persistence(), series, at, horizon=24))
    assert np.allclose(metrics["mae"], np.arange(1, 25))  # ряд растёт на 1 в час


@pytest.mark.parametrize("model, period", [
    (baselines.SeasonalNaive(24, "s24", "сутки"), 24),
    (baselines.SeasonalNaive(168, "s168", "неделя"), 168),
    (baselines.DailyProfile(7), 24),
])
def test_seasonal_baselines_are_exact_on_periodic_series(model, period):
    rng = np.random.default_rng(0)
    pattern = rng.uniform(1, 3, period)
    series = hourly(np.tile(pattern, 40))
    at = backtest.origins(series, series.index[24 * 14], None)
    result = backtest.run(model, series, at)
    assert np.allclose(result.pred, result.actual)


def test_intervals_coverage_and_skill():
    rng = np.random.default_rng(1)
    series = hourly(3 + rng.normal(0, 0.3, 24 * 120))
    model = baselines.Persistence()
    calib = backtest.run(model, series, backtest.origins(series, series.index[24 * 10], series.index[24 * 60]))
    result = backtest.run(model, series, backtest.origins(series, series.index[24 * 60], None))
    backtest.add_intervals(result, backtest.interval_quantiles(calib))
    metrics = backtest.horizon_metrics(result)
    assert abs(metrics["cover80"].mean() - 0.8) < 0.05 and abs(metrics["cover95"].mean() - 0.95) < 0.03
    report = backtest.summary(result, reference=result)
    assert report["buckets"]["1–24"]["skill"] == 0.0
    assert set(report["horizons"]) == {"1", "6", "12", "24", "48", "72"}
