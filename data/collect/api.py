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
    hourly = get_json(url, params)["hourly"]
    frame = pd.DataFrame({short: hourly[name] for name, short in variables.items()}, dtype="float64")
    frame.insert(0, "time", pd.to_datetime(hourly["time"], utc=True))
    return frame
