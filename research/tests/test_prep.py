import numpy as np
import pandas as pd

import prep


def hours(start: str, periods: int) -> pd.DatetimeIndex:
    return pd.date_range(pd.Timestamp(start, tz="UTC"), periods=periods, freq="h").tz_convert(prep.TZ)


def write_csv(path, index_utc: pd.DatetimeIndex, pm: list[float]) -> None:
    pd.DataFrame({"time": index_utc.strftime("%Y-%m-%dT%H:%MZ"), "pm2_5": pm}).to_csv(path, index=False)


def test_load_cuts_snapshot_and_converts_to_local(tmp_path):
    index = pd.date_range(prep.SNAPSHOT_END - pd.Timedelta(hours=2), periods=5, freq="h")
    path = tmp_path / "s.csv"
    write_csv(path, index, [1.0, 2.0, 3.0, 4.0, 5.0])
    frame = prep.load(path)
    assert len(frame) == 3  # часы после SNAPSHOT_END не попадают в исследование
    assert str(frame.index.tz) == prep.TZ


def test_almaty_switched_to_utc5_on_1_march_2024():
    before = pd.Timestamp("2024-02-29T12:00Z").tz_convert(prep.TZ)
    after = pd.Timestamp("2024-03-02T12:00Z").tz_convert(prep.TZ)
    assert before.utcoffset() == pd.Timedelta(hours=6)
    assert after.utcoffset() == pd.Timedelta(hours=5)


def test_split_by_time_without_overlap():
    index = hours("2025-09-29T00:00", 72)
    frame = pd.DataFrame({"pm2_5": np.arange(72.0)}, index=index)
    train, test = prep.split(frame)
    assert len(train) + len(test) == 72
    assert train.index.max() < prep.TEST_START <= test.index.min()
    assert test.index.min().tz_convert(prep.TZ) == pd.Timestamp("2025-10-01", tz=prep.TZ)


def test_heating_season_labels():
    index = pd.DatetimeIndex(["2024-10-14 12:00", "2024-10-15 00:00", "2025-01-10 08:00", "2025-04-15 23:00",
                              "2025-04-16 00:00", "2025-07-01 12:00"]).tz_localize(prep.TZ)
    labels = prep.heating_season(index).tolist()
    assert labels == [None, "2024/25", "2024/25", "2024/25", None, None]


def test_clean_interpolates_cams_glitch_only():
    index = hours("2022-12-13T00:00", 6)
    frame = pd.DataFrame({column: [10.0, 20.0, 0.7, 0.7, 50.0, 60.0] for column in prep.POLLUTANTS}, index=index)
    frame["no2"] = [30.0, 30.0, 0.0, 0.0, 0.0, 30.0]  # в 4-м часе NO₂ ноль, но CO нормальный – не сбой
    frame["co"] = [900.0, 900.0, 59.0, 59.0, 900.0, 900.0]
    frame["temp"] = -5.0
    assert prep.glitches(frame).tolist() == [False, False, True, True, False, False]
    cleaned = prep.clean(frame)
    assert cleaned["pm2_5"].tolist() == [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]
    assert (cleaned["temp"] == -5.0).all() and frame.loc[index[2], "pm2_5"] == 0.7


def test_cams_cycle_boundaries():
    index = pd.DatetimeIndex(["2023-06-26T23:00Z", "2023-06-27T00:00Z", "2024-11-12T11:00Z",
                              "2024-11-12T12:00Z", "2026-05-12T12:00Z"]).tz_convert(prep.TZ)
    assert prep.cams_cycle(index).tolist() == ["47R3", "48R1", "48R1", "49R1", "50R1"]


def test_daily_mean_drops_incomplete_days():
    index = pd.date_range("2025-01-01", periods=24 + 10, freq="h", tz=prep.TZ)
    daily = prep.daily_mean(pd.Series(1.0, index=index))
    assert len(daily) == 1 and daily.iloc[0] == 1.0


def test_episodes_split_on_gaps_and_below_threshold():
    index = pd.date_range("2025-01-01", periods=8, freq="D", tz=prep.TZ)
    daily = pd.Series([10, 60, 70, 55, 52, 30, 80, 20], index=index, dtype=float)
    daily = daily.drop(index[3])  # пропуск суток разрывает эпизод, даже если до и после порог превышен
    found = prep.episodes(daily, threshold=50)
    assert found["days"].tolist() == [2, 1, 1]
    assert found.iloc[0].to_dict() == {"start": "2025-01-02", "end": "2025-01-03", "days": 2, "peak": 70.0,
                                       "mean": 65.0}


def test_episodes_empty():
    index = pd.date_range("2025-01-01", periods=3, freq="D", tz=prep.TZ)
    assert prep.episodes(pd.Series([1.0, 2.0, 3.0], index=index)).empty


def test_robust_outliers():
    values = pd.Series([0.0, 0.1, -0.1, 0.05, -0.05, 0.02, 5.0])
    assert prep.robust_outliers(values).tolist() == [False] * 6 + [True]


def test_strength():
    rng = np.random.default_rng(0)
    seasonal = np.sin(np.arange(1000) / 10)
    assert prep.strength(seasonal, rng.normal(0, 0.05, 1000)) > 0.9
    assert prep.strength(np.zeros(1000), rng.normal(0, 1, 1000)) == 0.0
