"""Честная проверка моделей прогноза: скользящее начало прогноза (rolling origin) без утечки будущего.

В момент прогноза t модель получает ряд только до часа t включительно и прогнозирует часы t+1 … t+H.
Модели работают в логарифмах (ln PM2.5), метрики считаются в мкг/м³ после обратного перевода.
"""
import math
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
    native: dict | None = None  # собственные интервалы модели, если она их строит: уровень -> (нижняя, верхняя), ln


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
        refit_days: float | None = 7, train_start: pd.Timestamp | None = None) -> Result:
    values = series.to_numpy()
    position = pd.Series(np.arange(len(series)), index=series.index)
    first = 0 if train_start is None else int(position[series.index >= train_start].iloc[0])
    pred, actual, native = [], [], []
    fitted_at = None
    for origin in at:
        i = int(position[origin])
        history = series.iloc[first:i + 1]  # копия до момента прогноза включительно – будущего модель не видит
        # refit_days=None – подгонка один раз, в первый момент (так считается каждый блок в run_blocks)
        if fitted_at is None or (refit_days is not None and origin - fitted_at >= timedelta(days=refit_days)):
            model.fit(history)
            fitted_at = origin
        forecast = np.asarray(model.predict(history, horizon), dtype=float)
        if forecast.shape != (horizon,):
            raise ValueError(f"{model.name}: прогноз формы {forecast.shape}, ожидалось ({horizon},)")
        pred.append(forecast)
        actual.append(values[i + 1:i + 1 + horizon])
        if hasattr(model, "intervals"):  # собственные интервалы последнего прогноза: уровень -> (нижняя, верхняя)
            native.append(model.intervals())
    result = Result(model.name, at, np.array(pred), np.array(actual))
    if native:
        result.native = {level: (np.array([n[level][0] for n in native]), np.array([n[level][1] for n in native]))
                         for level in native[0]}
    return result


# моменты прогноза, разбитые на блоки между переподгонками – по тому же правилу, что в run()
def refit_blocks(at: pd.DatetimeIndex, refit_days: float = 7) -> list[pd.DatetimeIndex]:
    blocks, start = [], 0
    fitted_at = at[0] if len(at) else None
    for i, origin in enumerate(at):
        if origin - fitted_at >= timedelta(days=refit_days):
            blocks.append(at[start:i])
            start, fitted_at = i, origin
    if len(at):
        blocks.append(at[start:])
    return blocks


# кэш прогонов (model/.cache, в git не попадает): повторный запуск отчёта не пересчитывает готовые конфигурации
def save_result(result: Result, path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # моменты прогноза – секунды UTC с явной единицей (pandas 3 хранит время в микросекундах, а не наносекундах)
    np.savez_compressed(path, name=result.name, origins=result.origins.tz_convert("UTC").as_unit("s").asi8,
                        pred=result.pred, actual=result.actual)


def load_result(path) -> Result:
    data = np.load(path)
    origins = pd.DatetimeIndex(pd.to_datetime(data["origins"], unit="s", utc=True)).tz_convert(prep.TZ)
    return Result(str(data["name"]), origins, data["pred"], data["actual"])


def concat(results: list[Result]) -> Result:
    out = Result(results[0].name, results[0].origins.append([r.origins for r in results[1:]]),
                 np.concatenate([r.pred for r in results]), np.concatenate([r.actual for r in results]))
    if results[0].native:
        out.native = {level: (np.concatenate([r.native[level][0] for r in results]),
                              np.concatenate([r.native[level][1] for r in results])) for level in results[0].native}
    return out


# тот же прогон, что run(), но блоки между переподгонками считаются параллельно в map (например, pool.map):
# модель внутри блока подгоняется один раз в его начале, поэтому блоки независимы и результат совпадает с run()
def run_blocks(make_model, series: pd.Series, at: pd.DatetimeIndex, map_function, horizon: int = HORIZON,
               refit_days: float = 7, train_start: pd.Timestamp | None = None) -> Result:
    blocks = refit_blocks(at, refit_days)
    tasks = [(make_model, series, block, horizon, train_start) for block in blocks]
    return concat(list(map_function(_run_block, tasks)))


def _run_block(task: tuple) -> Result:
    make_model, series, block, horizon, train_start = task
    return run(make_model(), series, block, horizon=horizon, refit_days=None, train_start=train_start)


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
    for level, (low, high) in (result.native or {}).items():
        out[f"native_cover{int(level * 100)}"] = np.mean((result.actual >= low) & (result.actual <= high), axis=0)
        out[f"native_width{int(level * 100)}"] = np.mean(np.exp(high) - np.exp(low), axis=0)
    return out


# тест Диболда–Мариано: значимо ли модель a точнее модели b на сутках горизонта bucket. Потеря – абсолютная
# ошибка в мкг/м³, усреднённая по часам горизонта в каждом прогнозе; дисперсия разности – по Ньюи–Уэсту
# с лагом lag (прогнозы каждые 6 ч на 72 ч перекрываются, соседние ошибки зависимы). Модели – на одних моментах.
def dm_test(a: Result, b: Result, bucket: tuple[int, int] = (1, 24), lag: int = 12) -> dict:
    if not a.origins.equals(b.origins):
        raise ValueError("модели проверены на разных моментах прогноза")
    part = slice(bucket[0] - 1, bucket[1])
    y = np.exp(a.actual[:, part])
    d = np.abs(y - np.exp(a.pred[:, part])).mean(axis=1) - np.abs(y - np.exp(b.pred[:, part])).mean(axis=1)
    n, centered = len(d), d - d.mean()
    variance = centered @ centered / n
    for k in range(1, lag + 1):
        variance += 2 * (1 - k / (lag + 1)) * (centered[k:] @ centered[:-k]) / n
    stat = float(d.mean() / np.sqrt(variance / n)) if variance > 0 else 0.0
    return {"mae_diff": round(float(d.mean()), 4), "dm": round(stat, 3),
            "p_value": round(float(math.erfc(abs(stat) / math.sqrt(2))), 4)}


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
