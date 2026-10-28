import numpy as np
import pandas as pd

from collect.check import check_series, summary
from conftest import make_frame


def test_valid_series_has_no_problems(frame):
    assert check_series(frame) == []


def test_wrong_columns(frame):
    problems = check_series(frame.drop(columns="dust"))
    assert len(problems) == 1 and "колонки" in problems[0]


def test_empty_series(frame):
    assert check_series(frame.iloc[:0]) == ["ряд пуст"]


def test_wrong_start(frame):
    assert any("начинается" in p for p in check_series(frame.iloc[1:]))


def test_gap_detected(frame):
    problems = check_series(frame.drop(index=[10, 11]).reset_index(drop=True))
    assert any("разрывы шкалы (1)" in p for p in problems)


def test_duplicate_detected(frame):
    doubled = pd.concat([frame, frame.iloc[[5]]]).sort_values("time").reset_index(drop=True)
    assert any("повторяются" in p for p in check_series(doubled))


def test_missing_and_out_of_range(frame):
    frame.loc[3, "pm2_5"] = np.nan
    frame.loc[4, "rh"] = 120.0
    problems = check_series(frame)
    assert "pm2_5: пропусков 1" in problems
    assert any(p.startswith("rh: 1 значений вне") for p in problems)


def test_staleness(frame):
    last = frame["time"].iloc[-1]
    assert check_series(frame, now=last + pd.Timedelta(hours=3), max_age_hours=6) == []
    assert any("старше" in p for p in check_series(frame, now=last + pd.Timedelta(hours=7), max_age_hours=6))


def test_summary_mentions_period():
    text = summary(make_frame(24))
    assert "часов: 24" in text and "pm2_5" in text
