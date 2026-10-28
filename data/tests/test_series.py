from datetime import date, timedelta

import numpy as np
import pandas as pd

from collect import series
from collect.config import OVERLAP_DAYS, START_DATE
from conftest import make_frame


def test_chunks_cover_range_without_overlap():
    chunks = series.date_chunks(date(2022, 9, 1), date(2024, 1, 10), days=366)
    assert chunks[0][0] == date(2022, 9, 1)
    assert chunks[-1][1] == date(2024, 1, 10)
    for (_, end), (start, _) in zip(chunks, chunks[1:]):
        assert start == end + timedelta(days=1)
    assert all((b - a).days < 366 for a, b in chunks)


def test_chunks_single_day():
    assert series.date_chunks(date(2026, 1, 1), date(2026, 1, 1)) == [(date(2026, 1, 1), date(2026, 1, 1))]


def test_clean_drops_future_hours(frame):
    now = frame["time"].iloc[10] + pd.Timedelta(minutes=40)
    cleaned = series.clean(frame, now)
    assert cleaned["time"].iloc[-1] == frame["time"].iloc[10]


def test_clean_clips_negative_concentrations(frame):
    frame.loc[3, "dust"] = -1.0
    frame.loc[4, "temp"] = -20.0  # отрицательная температура – не артефакт, не трогаем
    cleaned = series.clean(frame, frame["time"].iloc[-1])
    assert cleaned.loc[3, "dust"] == 0
    assert cleaned.loc[4, "temp"] == -20.0


def test_clean_drops_incomplete_tail_but_keeps_inner_gaps(frame):
    frame.loc[20, "pm2_5"] = np.nan  # пропуск внутри ряда
    frame.loc[46:, "temp"] = np.nan  # погода ещё не пришла за последние два часа
    cleaned = series.clean(frame, frame["time"].iloc[-1])
    assert len(cleaned) == 46
    assert np.isnan(cleaned.loc[20, "pm2_5"])


def test_clean_all_incomplete_gives_empty(frame):
    frame["temp"] = np.nan
    assert series.clean(frame, frame["time"].iloc[-1]).empty


def test_merge_new_values_replace_overlap():
    old = make_frame(48)
    new = make_frame(30, start=old["time"].iloc[30])
    new["pm2_5"] = 99.0
    merged = series.merge(old, new)
    assert len(merged) == 60
    assert merged["time"].is_unique and merged["time"].is_monotonic_increasing
    assert (merged.loc[:29, "pm2_5"] == 25.0).all()
    assert (merged.loc[30:, "pm2_5"] == 99.0).all()


def test_merge_with_empty_new_keeps_old(frame):
    assert series.merge(frame, frame.iloc[:0]).equals(frame)


def test_write_read_roundtrip(tmp_path, frame):
    frame.loc[5, "pm2_5"] = 12.3
    path = tmp_path / "series" / "almaty.csv"
    series.write_series(frame, path)
    assert path.read_text(encoding="utf-8").splitlines()[1].startswith("2022-09-01T00:00Z,25,")
    loaded = series.read_series(path)
    assert loaded["time"].equals(frame["time"].astype(loaded["time"].dtype))
    assert loaded.loc[5, "pm2_5"] == 12.3


def test_update_full_then_incremental(tmp_path, monkeypatch):
    calls = []
    start = pd.Timestamp(START_DATE).tz_localize("UTC")

    # вместо Open-Meteo – ряд с START_DATE до конца запрошенного дня, как отдаёт API
    def fake_download(a, b):
        calls.append((a, b))
        hours = int((pd.Timestamp(b) - pd.Timestamp(START_DATE)) / pd.Timedelta(hours=1)) + 24
        full = make_frame(hours)
        return full[full["time"] >= pd.Timestamp(a).tz_localize("UTC")]

    monkeypatch.setattr(series, "download", fake_download)
    path = tmp_path / "almaty.csv"

    first, added = series.update(path, now=start + pd.Timedelta(days=9, hours=5, minutes=30))
    assert calls[-1] == (START_DATE, START_DATE + timedelta(days=9))
    assert added == len(first) == 9 * 24 + 6

    second, added = series.update(path, now=start + pd.Timedelta(days=12, hours=2))
    last_old = first["time"].iloc[-1]
    assert calls[-1] == ((last_old - timedelta(days=OVERLAP_DAYS)).date(), START_DATE + timedelta(days=12))
    assert added == 3 * 24 - 3
    assert second["time"].is_unique and second["time"].iloc[-1] == start + pd.Timedelta(days=12, hours=2)
