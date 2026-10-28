import pandas as pd
import pytest

from collect.config import COLUMNS, START_DATE

# правдоподобные значения для каждой колонки – внутри диапазонов проверки
VALID = {
    "pm2_5": 25.0, "pm10": 40.0, "no2": 30.0, "co": 400.0, "so2": 10.0, "dust": 5.0,
    "temp": 5.0, "rh": 60.0, "dew": -2.0, "wind": 7.0, "wind_dir": 180.0,
    "pressure": 925.0, "precip": 0.0, "cloud": 50.0,
}


# почасовой ряд из hours часов, начиная с start (по умолчанию – START_DATE)
def make_frame(hours: int, start: pd.Timestamp | None = None) -> pd.DataFrame:
    start = start if start is not None else pd.Timestamp(START_DATE).tz_localize("UTC")
    frame = pd.DataFrame({column: [value] * hours for column, value in VALID.items()})
    frame.insert(0, "time", pd.date_range(start, periods=hours, freq="h"))
    return frame[COLUMNS]


@pytest.fixture
def frame() -> pd.DataFrame:
    return make_frame(48)
