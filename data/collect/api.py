import random
import time
from datetime import date

import pandas as pd
import requests

from .config import BACKOFF_SEC, LATITUDE, LONGITUDE, RETRIES, RETRY_BUDGET_SEC, TIMEOUT_SEC, USER_AGENT

_started = time.monotonic()  # начало запуска: общий бюджет на повторы считается от него


def backoff(attempt: int) -> float:
    """Пауза перед повтором attempt (1, 2, …): 5, 10, 20, 40 с и ±20 % случайно – чтобы повторы многих
    клиентов не били в Open-Meteo одновременно."""
    return BACKOFF_SEC * 2 ** (attempt - 1) * random.uniform(0.8, 1.2)


# GET с повтором при обрыве соединения, таймауте или ответе 5xx/429 (для 429 – пауза из Retry-After, если
# сервер её назвал); ошибки запроса (4xx) не повторяются. Повторов – не больше RETRIES, а если общий бюджет
# запуска на повторы исчерпан – последняя ошибка сразу
def get_json(url: str, params: dict) -> dict:
    for attempt in range(1, RETRIES + 1):
        wait = backoff(attempt)
        try:
            resp = requests.get(url, params=params, timeout=TIMEOUT_SEC, headers={"User-Agent": USER_AGENT})
        except (requests.ConnectionError, requests.Timeout):
            if attempt == RETRIES or time.monotonic() - _started + wait > RETRY_BUDGET_SEC:
                raise
        else:
            last = attempt == RETRIES or time.monotonic() - _started + wait > RETRY_BUDGET_SEC
            if (resp.status_code < 500 and resp.status_code != 429) or last:
                resp.raise_for_status()
                return resp.json()
            if resp.status_code == 429 and resp.headers.get("Retry-After", "").isdigit():
                wait = max(wait, float(resp.headers["Retry-After"]))
        time.sleep(wait)
    raise RuntimeError("unreachable")


# почасовые переменные Open-Meteo за [start; end] в UTC -> таблица с колонкой time и короткими именами
def fetch_hourly(url: str, variables: dict[str, str], start: date, end: date, extra: dict | None = None) -> pd.DataFrame:
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "hourly": ",".join(variables),
        "timezone": "GMT",
        **(extra or {}),
    }
    return _frame(get_json(url, params)["hourly"], variables)


def _frame(hourly: dict, variables: dict[str, str]) -> pd.DataFrame:
    frame = pd.DataFrame({short: hourly[name] for name, short in variables.items()}, dtype="float64")
    frame.insert(0, "time", pd.to_datetime(hourly["time"], utc=True))
    return frame


# те же переменные сразу для многих точек одним запросом (Open-Meteo отвечает списком в порядке точек);
# колонки lat и lon – запрошенные координаты, а не узлы сетки, чтобы ключи точек не зависели от модели
def fetch_hourly_points(url: str, variables: dict[str, str], points: list[tuple[float, float]], start: date,
                        end: date, extra: dict | None = None) -> pd.DataFrame:
    params = {
        "latitude": ",".join(str(lat) for lat, _ in points),
        "longitude": ",".join(str(lon) for _, lon in points),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "hourly": ",".join(variables),
        "timezone": "GMT",
        **(extra or {}),
    }
    answers = get_json(url, params)
    answers = answers if isinstance(answers, list) else [answers]
    frames = []
    for (lat, lon), answer in zip(points, answers):
        frame = _frame(answer["hourly"], variables)
        frame.insert(0, "lon", lon)
        frame.insert(0, "lat", lat)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)
