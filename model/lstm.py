"""LSTM: прогноз ln PM2.5 на 72 ч по последней неделе ряда, календарю и (в варианте с погодой) прогнозу погоды.

Обучение – в Google Colab на GPU (notebooks/lstm.ipynb, PyTorch), модели – ONNX в artifacts/. Здесь общие для
обучения и прогноза признаки (одинаковые по построению) и вывод через ONNX Runtime без PyTorch.

    make -C model lstm   # проверка обученных моделей на валидации -> reports/lstm/validation.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

import prep
import weather

LOOKBACK, HORIZON = 168, 72  # неделя истории -> трое суток прогноза
WEATHER = ("temp", "wind", "precip")
ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
LOW, HIGH = np.log(0.3), np.log(500)


# календарь по местному времени: час суток и день года синусом и косинусом
def calendar(index: pd.DatetimeIndex) -> np.ndarray:
    local = index.tz_convert(prep.TZ)
    hour, day = local.hour.to_numpy(), local.day_of_year.to_numpy()
    return np.column_stack([np.sin(2 * np.pi * hour / 24), np.cos(2 * np.pi * hour / 24),
                            np.sin(2 * np.pi * day / 365.25), np.cos(2 * np.pi * day / 365.25)]).astype(np.float32)


# фактическая погода из ряда (прошедшие часы; при обучении – и будущие как «идеальный прогноз»)
def actual_weather(frame: pd.DataFrame, variables: tuple[str, ...]) -> np.ndarray:
    return np.column_stack([weather.transform(v, frame[v].to_numpy()) for v in variables]).astype(np.float32)


# нормировка по обучающей части: среднее и стандартное отклонение ln PM2.5 и погоды
def fit_norm(frame: pd.DataFrame, variables: tuple[str, ...]) -> dict:
    log_pm = np.log(frame["pm2_5"].to_numpy())
    norm = {"pm_mean": float(log_pm.mean()), "pm_std": float(log_pm.std())}
    if variables:
        values = actual_weather(frame, variables)
        norm["weather_mean"] = values.mean(axis=0).tolist()
        norm["weather_std"] = values.std(axis=0).tolist()
    return norm


def _weather_norm(values: np.ndarray, norm: dict) -> np.ndarray:
    return (values - np.asarray(norm["weather_mean"], np.float32)) / np.asarray(norm["weather_std"], np.float32)


# признаки прошлого [LOOKBACK, F]: нормированный ln PM2.5, календарь, (погода)
def past_features(log_pm: np.ndarray, index: pd.DatetimeIndex, past_weather: np.ndarray | None, norm: dict) -> np.ndarray:
    parts = [((log_pm - norm["pm_mean"]) / norm["pm_std"]).astype(np.float32)[:, None], calendar(index)]
    if past_weather is not None:
        parts.append(_weather_norm(past_weather, norm))
    return np.concatenate(parts, axis=1).astype(np.float32)


# признаки будущего [HORIZON, G]: календарь, (прогноз погоды)
def future_features(times: pd.DatetimeIndex, future_weather: np.ndarray | None, norm: dict) -> np.ndarray:
    parts = [calendar(times)]
    if future_weather is not None:
        parts.append(_weather_norm(future_weather.astype(np.float32), norm))
    return np.concatenate(parts, axis=1).astype(np.float32)


# обучающие примеры для моментов positions (номера часов в frame): прошлое – неделя до момента включительно,
# будущее – календарь и фактическая погода следующих 72 ч, цель – ln PM2.5 через h часов минус ln PM2.5 сейчас
def build_samples(frame: pd.DataFrame, positions: np.ndarray, variables: tuple[str, ...],
                  norm: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    log_pm = np.log(frame["pm2_5"].to_numpy())
    past_all = past_features(log_pm, frame.index, actual_weather(frame, variables) if variables else None, norm)
    future_all = future_features(frame.index, actual_weather(frame, variables) if variables else None, norm)
    past = np.stack([past_all[i - LOOKBACK + 1:i + 1] for i in positions])
    future = np.stack([future_all[i + 1:i + 1 + HORIZON] for i in positions])
    target = np.stack([log_pm[i + 1:i + 1 + HORIZON] - log_pm[i] for i in positions]).astype(np.float32)
    return past, future, target


# номера часов, пригодные для обучения: есть неделя истории и все 72 ч цели строго до end (без заглядывания в неё)
def train_positions(index: pd.DatetimeIndex, end: pd.Timestamp) -> np.ndarray:
    last = index.searchsorted(end - pd.Timedelta(hours=HORIZON)) - 1
    return np.arange(LOOKBACK - 1, last + 1)


class LstmModel:
    """Обученная в Colab LSTM в формате ONNX. Веса фиксированы (подгонка не нужна): модель получает свежие
    наблюдения на входе. Прошлая погода – из ряда (известна до момента прогноза), будущая – прогноз,
    опубликованный к моменту прогноза (weather.future)."""

    # mode – режим обучения (папка artifacts/<mode>): validation – до 01.10.2024, test – до 01.10.2025, live – все данные
    def __init__(self, variant: str = "lstm", directory: Path | None = None, frame: pd.DataFrame | None = None,
                 mode: str = "validation") -> None:
        import onnxruntime as ort  # только там, где модель реально считает

        directory = directory or ARTIFACTS / mode
        meta = json.loads((directory / f"{variant}.json").read_text(encoding="utf-8"))
        self.name, self.norm, self.variables = meta["name"], meta["norm"], tuple(meta["weather"])
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        self.session = ort.InferenceSession(str(directory / f"{variant}.onnx"), options,
                                            providers=["CPUExecutionProvider"])
        if self.variables and frame is None:
            frame = prep.clean(prep.load())
        self.frame = frame

    def fit(self, history: pd.Series) -> None:
        pass

    def predict(self, history: pd.Series, horizon: int) -> np.ndarray:
        index = history.index[-LOOKBACK:]
        log_pm = history.to_numpy()[-LOOKBACK:]
        origin = index[-1]
        times = pd.date_range(origin + pd.Timedelta(hours=1), periods=HORIZON, freq="h")
        past_weather = actual_weather(self.frame.loc[index], self.variables) if self.variables else None
        future_weather = weather.future(origin, HORIZON, self.variables) if self.variables else None
        delta = self.session.run(None, {
            "past": past_features(log_pm, index, past_weather, self.norm)[None],
            "future": future_features(times, future_weather, self.norm)[None],
        })[0][0]
        return np.clip(log_pm[-1] + delta[:horizon], LOW, HIGH)
