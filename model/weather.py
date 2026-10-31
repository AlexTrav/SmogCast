"""Погода как внешние признаки без утечки будущего: архив прошлых прогнозов ECMWF IFS 0,25°
(data/series/weather_prev.csv, колонки <переменная>_d<N> – прогноз на час, выпущенный за N суток до него).

- Прошедшие часы (история до момента прогноза t): d0 – текущий расчёт модели, для прошлого почти анализ.
- Будущий час t+h: прогноз, выпущенный за N = ceil((h + 6) / 24) суток до него, то есть не позже t − 6 ч
  при любом h; 6 ч – запас на публикацию расчёта IFS. Так модель видит только опубликованный к t прогноз.
"""
import os
from functools import lru_cache
from math import ceil
from pathlib import Path

import numpy as np
import pandas as pd

import prep

PATH = Path(os.environ.get("WEATHER_PREV", "/series/weather_prev.csv"))
NAMES = {"temp": "температура", "wind": "ветер", "precip": "осадки", "pressure": "давление",
         "cloud": "облачность"}
PUBLISH_HOURS = 6
MAX_LEAD = 4
# с этой даты в архиве есть прогнозы всех глубин (d0…d4) – раньше модели с погодой не подгоняются
START = pd.Timestamp("2024-02-08", tz=prep.TZ)


def lead_days(h: int) -> int:
    return ceil((h + PUBLISH_HOURS) / 24)


@lru_cache(maxsize=1)
def archive() -> pd.DataFrame:
    frame = pd.read_csv(PATH)
    frame["time"] = pd.to_datetime(frame["time"], format="%Y-%m-%dT%H:%MZ", utc=True)
    frame = frame.set_index("time")
    frame.index = frame.index.tz_convert(prep.TZ)
    # редкие пропуски архива – интерполяция по времени внутри каждой колонки
    return frame.interpolate(method="time", limit_direction="both")


# преобразование признаков: осадки – log1p (длинный хвост), остальное как есть
def transform(name: str, values: np.ndarray) -> np.ndarray:
    return np.log1p(np.clip(values, 0, None)) if name == "precip" else values


# признаки прошедших часов (история до момента прогноза включительно): текущий расчёт d0
def history(index: pd.DatetimeIndex, variables: tuple[str, ...]) -> np.ndarray:
    data = archive().reindex(index)
    return np.column_stack([transform(v, data[f"{v}_d0"].to_numpy()) for v in variables])


# признаки будущих часов origin+1 … origin+horizon: прогноз, опубликованный к моменту origin
def future(origin: pd.Timestamp, horizon: int, variables: tuple[str, ...]) -> np.ndarray:
    data = archive()
    times = pd.date_range(origin + pd.Timedelta(hours=1), periods=horizon, freq="h")
    columns = []
    for v in variables:
        values = np.array([data.at[t, f"{v}_d{min(lead_days(h), MAX_LEAD)}"] if t in data.index else np.nan
                           for h, t in enumerate(times, 1)])
        columns.append(transform(v, values))
    out = np.column_stack(columns)
    if np.isnan(out).any():
        raise ValueError(f"нет прогноза погоды на {times[0]} … {times[-1]}")
    return out
