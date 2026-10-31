"""Архив прошлых прогнозов погоды ECMWF IFS 0,25° (Open-Meteo Previous Runs API) – для моделей с погодой
без утечки будущего: прогноз на час T, выпущенный за N суток до T (колонки <переменная>_d<N>, N = 0…4;
d0 – текущий расчёт модели, для прошедших часов – почти анализ).

    make -C data prev   # -> series/weather_prev.csv
"""
from datetime import date, timedelta

import pandas as pd

from .api import fetch_hourly
from .config import DATA_DIR
from .series import TIME_FORMAT, date_chunks

PREV_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
PREV_MODEL = "ecmwf_ifs025"
PREV_START = date(2024, 2, 4)  # с этой даты архив непуст; прогнозы «за 4 суток» – примерно с 08.02.2024
PREV_PATH = DATA_DIR / "series" / "weather_prev.csv"
PREV_VARS = {
    "temperature_2m": "temp",
    "relative_humidity_2m": "rh",
    "wind_speed_10m": "wind",
    "wind_direction_10m": "wind_dir",
    "surface_pressure": "pressure",
    "precipitation": "precip",
    "cloud_cover": "cloud",
}
LEADS = range(5)


def api_name(variable: str, lead: int) -> str:
    return variable if lead == 0 else f"{variable}_previous_day{lead}"


def download(start: date, end: date) -> pd.DataFrame:
    variables = {api_name(v, d): f"{short}_d{d}" for v, short in PREV_VARS.items() for d in LEADS}
    parts = [fetch_hourly(PREV_URL, variables, a, b, {"models": PREV_MODEL}) for a, b in date_chunks(start, end, 120)]
    return pd.concat(parts, ignore_index=True).drop_duplicates("time").sort_values("time").reset_index(drop=True)


# выгрузка с PREV_START по вчерашний день (сегодняшние часы ещё не все выпущены во всех горизонтах)
def collect(today: date | None = None) -> pd.DataFrame:
    end = (today or date.today()) - timedelta(days=1)
    frame = download(PREV_START, end)
    PREV_PATH.parent.mkdir(parents=True, exist_ok=True)
    frame.assign(time=frame["time"].dt.strftime(TIME_FORMAT)).to_csv(PREV_PATH, index=False, float_format="%g",
                                                                     lineterminator="\n")
    return frame


def summary(frame: pd.DataFrame) -> str:
    filled = frame.drop(columns="time").notna()
    first = {c: frame.loc[filled[c], "time"].min() for c in filled.columns}
    lines = [f"часов: {len(frame)}, с {frame['time'].iloc[0]} по {frame['time'].iloc[-1]} (UTC)"]
    for short in PREV_VARS.values():
        cols = [f"{short}_d{d}" for d in LEADS]
        lines.append(f"{short:9} заполнено: " + ", ".join(f"d{d} {filled[c].mean():.0%}" for d, c in zip(LEADS, cols))
                     + f"; d4 – с {first[cols[-1]]:%d.%m.%Y}")
    return "\n".join(lines)
