import time
from datetime import date

import pandas as pd
import requests

from .config import LATITUDE, LONGITUDE, RETRIES, TIMEOUT_SEC, USER_AGENT


# GET с повтором при обрыве соединения или ответе 5xx/429; ошибки запроса (4xx) не повторяются
def get_json(url: str, params: dict) -> dict:
    for attempt in range(1, RETRIES + 1):
        try:
            resp = requests.get(url, params=params, timeout=TIMEOUT_SEC, headers={"User-Agent": USER_AGENT})
        except (requests.ConnectionError, requests.Timeout):
            if attempt == RETRIES:
                raise
        else:
            if (resp.status_code < 500 and resp.status_code != 429) or attempt == RETRIES:
                resp.raise_for_status()
                return resp.json()
        time.sleep(5 * attempt)
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
