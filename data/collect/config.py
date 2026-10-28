from datetime import date
from pathlib import Path

# корень папки data: data/collect/config.py -> collect -> data
DATA_DIR = Path(__file__).resolve().parents[1]
SERIES_PATH = DATA_DIR / "series" / "almaty.csv"  # почасовой ряд хранится в git, обновляется скриптом

# центр Алматы; Open-Meteo сам берёт ближайший узел сетки (CAMS global – 0,4°, погода – около 25 км)
LATITUDE = 43.25
LONGITUDE = 76.92

# CAMS global в Open-Meteo начинается в августе 2022, первые полные сутки – 01.09.2022
START_DATE = date(2022, 9, 1)

AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
WEATHER_URL = "https://archive-api.open-meteo.com/v1/archive"

# переменная API -> короткое имя колонки в CSV
AIR_VARS = {
    "pm2_5": "pm2_5",
    "pm10": "pm10",
    "nitrogen_dioxide": "no2",
    "carbon_monoxide": "co",
    "sulphur_dioxide": "so2",
    "dust": "dust",
}
# высота пограничного слоя не берётся: в архиве Open-Meteo по ней дыра 01.01–31.08.2024
WEATHER_VARS = {
    "temperature_2m": "temp",
    "relative_humidity_2m": "rh",
    "dew_point_2m": "dew",
    "wind_speed_10m": "wind",
    "wind_direction_10m": "wind_dir",
    "surface_pressure": "pressure",
    "precipitation": "precip",
    "cloud_cover": "cloud",
}
COLUMNS = ["time", *AIR_VARS.values(), *WEATHER_VARS.values()]

# допустимые значения для проверки ряда: всё, что вне диапазона, – сбой источника или сборки
RANGES = {
    "pm2_5": (0, 1000),
    "pm10": (0, 3000),
    "no2": (0, 1000),
    "co": (0, 20000),
    "so2": (0, 3000),
    "dust": (0, 5000),
    "temp": (-45, 50),
    "rh": (0, 100),
    "dew": (-55, 35),
    "wind": (0, 150),
    "wind_dir": (0, 360),
    "pressure": (850, 1000),  # узел сетки на высоте около 800 м
    "precip": (0, 100),
    "cloud": (0, 100),
}

# при обновлении последние дни запрашиваются заново: ERA5 приходит с задержкой около 5 дней
# и заменяет оперативный прогноз IFS, которым архив погоды заполняет свежие часы
OVERLAP_DAYS = 7
CHUNK_DAYS = 366  # не больше года на запрос – ответы остаются небольшими

USER_AGENT = "SmogCast-collector/1.0 (student project)"
TIMEOUT_SEC = 60
RETRIES = 3
