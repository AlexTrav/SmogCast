"""Погода на 72 ч и факторы смога для значков на сайте, сетка CAMS вокруг Алматы для карты."""
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Request, Response

from . import db
from .common import TZ, cached, iso, r1

router = APIRouter(prefix="/api")
HORIZON = 72
WEATHER = ("temp", "rh", "dew", "wind", "wind_dir", "pressure", "precip", "cloud")
# пороги факторов смога на ближайшие сутки. Исследование (research/README.md): в отопительный сезон
# смог сильнее всего связан с холодом (смоговые сутки –3,2 °C против 2,3 °C у остальных), осадки его смывают,
# ветер в ряду слабый (в среднем 4,4 км/ч), и только почти полный штиль выделяется
COLD_C = 0.0
CALM_KMH = 3.0
DRY_MM = 0.1
HEATING_FROM, HEATING_TO = (10, 15), (4, 15)  # отопительный сезон Алматы, как в research/prep.py


def heating(day: date) -> bool:
    key = (day.month, day.day)
    return key >= HEATING_FROM or key <= HEATING_TO


@router.get("/weather")
def weather(request: Request) -> Response:
    """Прогноз погоды ECMWF IFS на 72 ч после последнего часа ряда (для каждого часа – самый свежий
    из сохранённых снимков) и факторы смога на ближайшие 24 ч: холод, штиль, без осадков, отопительный сезон.
    Ветер – км/ч, направление – откуда дует, градусы; осадки – мм за час."""
    return cached(request, "weather", build_weather)


def build_weather() -> dict:
    last = db.fetch_one("select max(time) from series")[0]
    if last is None:
        raise HTTPException(503, "ряд пуст")
    rows = db.fetch(f"select distinct on (time) time, issued_at, {', '.join(WEATHER)} from weather_forecasts "
                    "where time > %s and time <= %s order by time, issued_at desc",
                    (last, last + timedelta(hours=HORIZON)))
    by_time = {r[0]: r for r in rows}
    times = [last + timedelta(hours=h) for h in range(1, HORIZON + 1)]
    columns = {name: [r1(by_time[t][2 + i]) if t in by_time else None for t in times] for i, name in enumerate(WEATHER)}
    day = {name: [v for v in values[:24] if v is not None] for name, values in columns.items()}
    temp = sum(day["temp"]) / len(day["temp"]) if day["temp"] else None
    wind = sum(day["wind"]) / len(day["wind"]) if day["wind"] else None
    precip = sum(day["precip"]) if day["precip"] else None
    local_day = db.fetch_one(f"select (%s::timestamptz at time zone '{TZ}')::date", (times[0],))[0]
    return {
        "issued_at": iso(max((r[1] for r in rows), default=None)), "start": iso(times[0]), "step": "hour",
        "values": columns,
        "factors": [
            {"key": "cold", "active": temp is not None and temp < COLD_C, "value": r1(temp), "threshold": COLD_C},
            {"key": "calm", "active": wind is not None and wind < CALM_KMH, "value": r1(wind), "threshold": CALM_KMH},
            {"key": "dry", "active": precip is not None and precip < DRY_MM, "value": r1(precip), "threshold": DRY_MM},
            {"key": "heating", "active": heating(local_day), "value": None, "threshold": None},
        ],
    }


@router.get("/region")
def region(request: Request) -> Response:
    """Сетка 5x5 узлов CAMS (шаг 0,4°, около 200x200 км) вокруг Алматы: сутки назад и 3 суток вперёд.
    Значения – массивы [час][широта][долгота]; это оценка модели по ячейкам, а не замеры по районам."""
    return cached(request, "region", build_region)


def build_region() -> dict:
    rows = db.fetch("select lat, lon, time, issued_at, pm2_5, pm10, wind, wind_dir from region order by time, lat, lon")
    if not rows:
        raise HTTPException(503, "сетки ещё нет")
    lats = sorted({r[0] for r in rows})
    lons = sorted({r[1] for r in rows})
    first, last = rows[0][2], rows[-1][2]
    times = [first + timedelta(hours=h) for h in range(int((last - first).total_seconds() // 3600) + 1)]
    cell = {(r[2], r[0], r[1]): r for r in rows}

    def grid(index: int) -> list:
        return [[[r1(cell[(t, la, lo)][index]) if (t, la, lo) in cell else None for lo in lons] for la in lats]
                for t in times]

    return {"issued_at": iso(rows[0][3]), "lats": lats, "lons": lons, "start": iso(times[0]), "step": "hour",
            "hours": len(times), "pm2_5": grid(4), "pm10": grid(5), "wind": grid(6), "wind_dir": grid(7)}
