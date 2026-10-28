from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from .api import fetch_hourly
from .config import (
    AIR_URL,
    AIR_VARS,
    CHUNK_DAYS,
    COLUMNS,
    OVERLAP_DAYS,
    SERIES_PATH,
    START_DATE,
    WEATHER_URL,
    WEATHER_VARS,
)

TIME_FORMAT = "%Y-%m-%dT%H:%MZ"


# отрезки дат не длиннее days дней, вместе покрывающие [start; end] без пересечений
def date_chunks(start: date, end: date, days: int = CHUNK_DAYS) -> list[tuple[date, date]]:
    chunks = []
    while start <= end:
        stop = min(start + timedelta(days=days - 1), end)
        chunks.append((start, stop))
        start = stop + timedelta(days=1)
    return chunks


# качество воздуха (CAMS global) и погода за [start; end], объединённые по часу
def download(start: date, end: date) -> pd.DataFrame:
    parts = []
    for a, b in date_chunks(start, end):
        air = fetch_hourly(AIR_URL, AIR_VARS, a, b, {"domains": "cams_global"})
        weather = fetch_hourly(WEATHER_URL, WEATHER_VARS, a, b)
        parts.append(air.merge(weather, on="time", how="outer"))
    return pd.concat(parts, ignore_index=True)


def clean(frame: pd.DataFrame, now: pd.Timestamp) -> pd.DataFrame:
    # часы после текущего – это уже прогноз, а не оценка по факту
    frame = frame[frame["time"] <= now.floor("h")].sort_values("time").reset_index(drop=True)
    # отрицательные концентрации физически невозможны – артефакт модели CAMS (у пыли встречается -1)
    air = list(AIR_VARS.values())
    frame[air] = frame[air].clip(lower=0)
    # последние часы, где один из источников ещё не отдал значение, отбрасываем: их заберёт следующее обновление;
    # пропуски внутри ряда не трогаем – их найдёт проверка
    complete = frame[COLUMNS].notna().all(axis=1)
    if not complete.any():
        return frame.iloc[:0][COLUMNS]
    return frame.loc[: complete[complete].index[-1], COLUMNS]


# свежая выгрузка заменяет перекрывающиеся часы старого ряда
def merge(old: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    if new.empty:
        return old
    combined = pd.concat([old[old["time"] < new["time"].min()], new], ignore_index=True)
    return combined.sort_values("time").reset_index(drop=True)


def read_series(path: Path = SERIES_PATH) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame["time"] = pd.to_datetime(frame["time"], format=TIME_FORMAT, utc=True)
    return frame


def write_series(frame: pd.DataFrame, path: Path = SERIES_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = frame.assign(time=frame["time"].dt.strftime(TIME_FORMAT))
    out.to_csv(path, index=False, float_format="%g", lineterminator="\n")


# обновить ряд: без файла (или при full) – выгрузка с START_DATE, иначе – последние OVERLAP_DAYS дней и новые часы;
# возвращает ряд и число добавленных часов
def update(path: Path = SERIES_PATH, now: pd.Timestamp | None = None, full: bool = False) -> tuple[pd.DataFrame, int]:
    now = now if now is not None else pd.Timestamp.now(tz="UTC")
    old = None if full or not path.exists() else read_series(path)
    start = START_DATE if old is None else (old["time"].max() - timedelta(days=OVERLAP_DAYS)).date()
    new = clean(download(start, now.date()), now)
    series = new if old is None else merge(old, new)
    write_series(series, path)
    return series, len(series) - (0 if old is None else len(old))
