"""Честная проверка моделей прогноза: скользящее начало прогноза (rolling origin) без утечки будущего.

В момент прогноза t модель получает ряд только до часа t включительно и прогнозирует часы t+1 … t+H.
Модели работают в логарифмах (ln PM2.5), метрики считаются в мкг/м³ после обратного перевода.
"""
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

import numpy as np
import pandas as pd

import prep

HORIZON = 72  # часов вперёд
ORIGIN_HOURS = (0, 6, 12, 18)  # моменты прогноза по местному времени
REPORT_HORIZONS = (1, 6, 12, 24, 48, 72)
BUCKETS = {"1–24": (1, 24), "25–48": (25, 48), "49–72": (49, 72)}

# части ряда по местному времени: обучение – до валидации, валидация – год с отопительным сезоном 2024/25,
# тест – с 01.10.2025 (prep.TEST_START) до конца снимка; тест открывается только явно, на шаге 6
VALID_START = pd.Timestamp("2024-10-01", tz=prep.TZ)
PERIODS = {
    "validation": (VALID_START, prep.TEST_START.tz_convert(prep.TZ)),
    "test": (prep.TEST_START.tz_convert(prep.TZ), None),
}


class Model(Protocol):
    name: str

    # подгонка по истории ln PM2.5 до момента прогноза (у базовых моделей – ничего не делает)
    def fit(self, history: pd.Series) -> None: ...

    # прогноз ln PM2.5 на часы t+1 … t+horizon по истории до t включительно
    def predict(self, history: pd.Series, horizon: int) -> np.ndarray: ...


@dataclass
class Result:
    name: str
    origins: pd.DatetimeIndex
    pred: np.ndarray  # ln PM2.5, форма (прогнозы, HORIZON)
    actual: np.ndarray  # ln PM2.5, та же форма
    lower: dict | None = None  # уровень интервала (0.8, 0.95) -> нижняя граница, ln
    upper: dict | None = None


def log_series(frame: pd.DataFrame) -> pd.Series:
    return np.log(frame["pm2_5"])


# моменты прогноза внутри [start; end): часы ORIGIN_HOURS по местному времени, для которых известен
# весь горизонт фактов
def origins(series: pd.Series, start: pd.Timestamp, end: pd.Timestamp | None, horizon: int = HORIZON,
            every: tuple[int, ...] = ORIGIN_HOURS) -> pd.DatetimeIndex:
    index = series.index
    last = index[-1] - timedelta(hours=horizon)
    mask = (index >= start) & (index <= last) & np.isin(index.hour, every)
    if end is not None:
        mask &= index < end
    return index[mask]


# прогон модели по моментам прогноза; подгонка – в первый момент и затем раз в refit_days по всей истории до момента
def run(model: Model, series: pd.Series, at: pd.DatetimeIndex, horizon: int = HORIZON,
        refit_days: float = 7, train_start: pd.Timestamp | None = None) -> Result:
    values = series.to_numpy()
    position = pd.Series(np.arange(len(series)), index=series.index)
    first = 0 if train_start is None else int(position[series.index >= train_start].iloc[0])
    pred, actual = [], []
    fitted_at = None
    for origin in at:
        i = int(position[origin])
        history = series.iloc[first:i + 1]  # копия до момента прогноза включительно – будущего модель не видит
        if fitted_at is None or origin - fitted_at >= timedelta(days=refit_days):
            model.fit(history)
            fitted_at = origin
        forecast = np.asarray(model.predict(history, horizon), dtype=float)
        if forecast.shape != (horizon,):
            raise ValueError(f"{model.name}: прогноз формы {forecast.shape}, ожидалось ({horizon},)")
        pred.append(forecast)
        actual.append(values[i + 1:i + 1 + horizon])
    return Result(model.name, at, np.array(pred), np.array(actual))


# эмпирические интервалы: квантили ошибок (ln) по каждому горизонту на калибровочном прогоне до проверяемой части
def interval_quantiles(calibration: Result, levels: tuple[float, ...] = (0.8, 0.95)) -> dict:
    errors = calibration.actual - calibration.pred
    return {level: (np.quantile(errors, (1 - level) / 2, axis=0), np.quantile(errors, (1 + level) / 2, axis=0))
            for level in levels}


def add_intervals(result: Result, quantiles: dict) -> Result:
    result.lower = {level: result.pred + low for level, (low, _) in quantiles.items()}
    result.upper = {level: result.pred + high for level, (_, high) in quantiles.items()}
    return result


def mae(y: np.ndarray, f: np.ndarray) -> np.ndarray:
    return np.mean(np.abs(y - f), axis=0)


def rmse(y: np.ndarray, f: np.ndarray) -> np.ndarray:
    return np.sqrt(np.mean((y - f) ** 2, axis=0))


# симметричная средняя абсолютная процентная ошибка, %: в отличие от MAPE не взрывается на малых значениях
def smape(y: np.ndarray, f: np.ndarray) -> np.ndarray:
    return np.mean(2 * np.abs(y - f) / (np.abs(y) + np.abs(f)), axis=0) * 100


# метрики по горизонтам (массивы длины HORIZON) в мкг/м³
def horizon_metrics(result: Result) -> dict[str, np.ndarray]:
    y, f = np.exp(result.actual), np.exp(result.pred)
    out = {"mae": mae(y, f), "rmse": rmse(y, f), "smape": smape(y, f)}
    for level in result.lower or {}:
        low, high = result.lower[level], result.upper[level]
        out[f"cover{int(level * 100)}"] = np.mean((result.actual >= low) & (result.actual <= high), axis=0)
        out[f"width{int(level * 100)}"] = np.mean(np.exp(high) - np.exp(low), axis=0)
    return out


# сводка: значения на отдельных горизонтах и средние по суткам горизонта; выигрыш над эталоном по MAE
def summary(result: Result, reference: Result | None = None) -> dict:
    metrics = horizon_metrics(result)
    base = horizon_metrics(reference)["mae"] if reference is not None else None
    out = {"origins": int(len(result.origins)), "horizons": {}, "buckets": {}}
    for h in REPORT_HORIZONS:
        row = {k: round(float(v[h - 1]), 4) for k, v in metrics.items()}
        if base is not None:
            row["skill"] = round(float(1 - metrics["mae"][h - 1] / base[h - 1]), 4)
        out["horizons"][str(h)] = row
    for name, (a, b) in BUCKETS.items():
        part = slice(a - 1, b)
        row = {k: round(float(np.mean(v[part])), 4) for k, v in metrics.items()}
        if base is not None:
            row["skill"] = round(float(1 - np.mean(metrics["mae"][part]) / np.mean(base[part])), 4)
        out["buckets"][name] = row
    return out
