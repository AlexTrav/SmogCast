"""Общие функции исследования: снимок ряда, местное время, разбиение, отопительные сезоны, эпизоды смога."""
import os
from pathlib import Path

import numpy as np
import pandas as pd

SERIES = Path(os.environ.get("SERIES", "/series/almaty.csv"))
TZ = "Asia/Almaty"

# снимок ряда для исследования: цифры отчёта не меняются, когда в CSV дописываются свежие часы
SNAPSHOT_END = pd.Timestamp("2026-10-28T15:00Z")
# отложенная тестовая часть – с 01.10.2025 по местному времени (весь отопительный сезон 2025/26);
# решения о моделях (преобразование, периоды, порядки) принимаются только по часам до этой даты
TEST_START = pd.Timestamp("2025-10-01", tz=TZ).tz_convert("UTC")

WHO_24H = 15.0  # норма ВОЗ 2021 для среднесуточного PM2.5, мкг/м³
WHO_YEAR = 5.0  # норма ВОЗ 2021 для среднегодового PM2.5
SMOG_DAY = 50.0  # «смоговые» сутки: среднее выше 50 мкг/м³ – в 3,3 раза выше суточной нормы ВОЗ

# обновления модели CAMS (IFS-COMPO) внутри ряда: 47R3 работал с 12.10.2021, 48R1 – с 27.06.2023,
# 49R1 – с 12.11.2024 12 UTC (заменён кадастр антропогенных выбросов CAMS-GLOB-ANT 5.3 на 6.1),
# 50R1 – с 12.05.2026 12 UTC (вместе с погодной IFS 50r1)
CAMS_CYCLES = [
    ("47R3", pd.Timestamp("2022-09-01T00:00Z")),
    ("48R1", pd.Timestamp("2023-06-27T00:00Z")),
    ("49R1", pd.Timestamp("2024-11-12T12:00Z")),
    ("50R1", pd.Timestamp("2026-05-12T12:00Z")),
]

# отопительный сезон в Алматы – примерно с 15 октября по 15 апреля
HEATING_FROM = (10, 15)
HEATING_TO = (4, 15)


# снимок ряда с индексом в местном времени Алматы (UTC+6, с 01.03.2024 – UTC+5)
def load(path: Path = SERIES) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame["time"] = pd.to_datetime(frame["time"], format="%Y-%m-%dT%H:%MZ", utc=True)
    frame = frame[frame["time"] <= SNAPSHOT_END].set_index("time")
    frame.index = frame.index.tz_convert(TZ)
    return frame


POLLUTANTS = ["pm2_5", "pm10", "no2", "co", "so2", "dust"]


# сбой CAMS: часы без антропогенных выбросов (NO₂ около нуля и CO на фоновом уровне) – в городе так не бывает;
# в снимке один такой участок: 13.12.2022 18:00 – 16.12.2022 05:00 (60 ч), PM2.5 там около 0,7 мкг/м³
def glitches(frame: pd.DataFrame) -> pd.Series:
    return (frame["no2"] < 0.5) & (frame["co"] < 100)


# загрязнители в часы сбоя считаются пропуском и заполняются линейной интерполяцией по времени;
# исходный ряд в data/ не меняется
def clean(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out.loc[glitches(frame), POLLUTANTS] = np.nan
    out[POLLUTANTS] = out[POLLUTANTS].interpolate(method="time")
    return out


# обучающая часть (с валидацией) и отложенный тест – по времени, без перемешивания
def split(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    test = frame.index >= TEST_START
    return frame[~test], frame[test]


# метка отопительного сезона «2024/25» для часов с 15.10 по 15.04 включительно, для остальных – NaN
def heating_season(index: pd.DatetimeIndex) -> pd.Series:
    key = index.month * 100 + index.day
    after = key >= HEATING_FROM[0] * 100 + HEATING_FROM[1]
    before = key <= HEATING_TO[0] * 100 + HEATING_TO[1]
    start = np.where(after, index.year, index.year - 1)
    labels = [f"{y}/{(y + 1) % 100:02d}" for y in start]
    return pd.Series(np.where(after | before, labels, None), index=index, dtype="object")


# цикл модели CAMS, который считал каждый час ряда
def cams_cycle(index: pd.DatetimeIndex) -> pd.Series:
    labels = pd.Series(CAMS_CYCLES[0][0], index=index, dtype="object")
    for name, start in CAMS_CYCLES[1:]:
        labels[index >= start] = name
    return labels


# среднесуточные значения по местному времени; неполные сутки (меньше min_hours часов) отбрасываются
def daily_mean(series: pd.Series, min_hours: int = 18) -> pd.Series:
    days = series.resample("D").agg(["mean", "count"])
    return days.loc[days["count"] >= min_hours, "mean"]


# эпизоды: подряд идущие сутки со средним выше порога -> начало, конец, длительность, пик, среднее
def episodes(daily: pd.Series, threshold: float = SMOG_DAY) -> pd.DataFrame:
    above = daily > threshold
    # новые сутки начинают новый эпизод, если вчера порог не превышен или между сутками есть пропуск
    gap = daily.index.to_series().diff() != pd.Timedelta(days=1)
    run = (above & (~above.shift(fill_value=False) | gap)).cumsum()
    rows = []
    for _, days in daily[above].groupby(run[above]):
        rows.append({
            "start": days.index[0].date().isoformat(),
            "end": days.index[-1].date().isoformat(),
            "days": len(days),
            "peak": round(float(days.max()), 1),
            "mean": round(float(days.mean()), 1),
        })
    return pd.DataFrame(rows, columns=["start", "end", "days", "peak", "mean"])


# выбросы по устойчивой оценке: отклонение от медианы больше k масштабированных MAD
def robust_outliers(values: pd.Series, k: float = 4.0) -> pd.Series:
    median = values.median()
    mad = 1.4826 * (values - median).abs().median()
    return (values - median).abs() > k * mad


# сила тренда или сезонности по Хайндману: 1 – Var(остаток) / Var(компонента + остаток), не меньше 0
def strength(component: np.ndarray, resid: np.ndarray) -> float:
    return float(max(0.0, 1 - np.var(resid) / np.var(component + resid)))
