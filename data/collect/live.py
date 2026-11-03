"""Живая часть: ряд в базе и ежечасный запуск (GitHub Actions) – свежие часы, снимки прогнозов, журнал."""
import contextlib
import time as clock
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pandas as pd
import psycopg

from . import db
from .api import fetch_hourly, fetch_hourly_points
from .config import (
    AIR_URL,
    DB_LIMIT_MB,
    FORECAST_DAYS,
    KEEP_DAYS,
    REGION_AHEAD_HOURS,
    REGION_LATS,
    REGION_LONS,
    REGION_PAST_HOURS,
    OVERLAP_DAYS,
    START_DATE,
    WEATHER_FORECAST_MODEL,
    WEATHER_FORECAST_URL,
    WEATHER_VARS,
)
from .series import clean, download, read_series


# первичная загрузка базы из CSV в репозитории (повторный запуск ничего не дублирует)
def seed(conn: psycopg.Connection) -> int:
    db.init_schema(conn)
    return db.upsert_series(conn, read_series())


# прогноз CAMS (table = cams_forecasts) или погоды IFS (weather_forecasts), известный в момент issued_at,
# на FORECAST_DAYS суток вперёд (только будущие часы); источники запрашиваются порознь – сбой одного не теряет другой
def fetch_forecast(table: str, issued_at: pd.Timestamp) -> pd.DataFrame:
    start, end = issued_at.date(), (issued_at + timedelta(days=FORECAST_DAYS)).date()
    if table == "cams_forecasts":
        frame = fetch_hourly(AIR_URL, {"pm2_5": "pm2_5", "pm10": "pm10"}, start, end, {"domains": "cams_global"})
    else:
        frame = fetch_hourly(WEATHER_FORECAST_URL, WEATHER_VARS, start, end, {"models": WEATHER_FORECAST_MODEL})
    frame = frame[(frame["time"] > issued_at) & (frame["time"] <= issued_at + timedelta(days=FORECAST_DAYS))]
    return frame.dropna(how="all", subset=list(frame.columns[1:]))


# сетка CAMS вокруг Алматы для карты: PM2.5 и PM10 (CAMS) и ветер (IFS) за сутки до issued_at и на 3 суток вперёд
def fetch_region(issued_at: pd.Timestamp) -> pd.DataFrame:
    points = [(lat, lon) for lat in REGION_LATS for lon in REGION_LONS]
    first = issued_at - timedelta(hours=REGION_PAST_HOURS)
    last = issued_at + timedelta(hours=REGION_AHEAD_HOURS)
    air = fetch_hourly_points(AIR_URL, {"pm2_5": "pm2_5", "pm10": "pm10"}, points, first.date(), last.date(),
                              {"domains": "cams_global"})
    wind = fetch_hourly_points(WEATHER_FORECAST_URL, {"wind_speed_10m": "wind", "wind_direction_10m": "wind_dir"},
                               points, first.date(), last.date(), {"models": WEATHER_FORECAST_MODEL})
    frame = air.merge(wind, on=["lat", "lon", "time"], how="left")
    frame = frame[(frame["time"] > first) & (frame["time"] <= last)].dropna(subset=["pm2_5"])
    return frame.assign(issued_at=issued_at)


class Session:
    """Соединение с базой, которое переживает обрыв: бесплатная Neon засыпает после 5 минут простоя и рвёт
    соединение. При OperationalError – одно переподключение и повтор действия (все этапы записи идемпотентны:
    upsert, снимок только при изменении, замена сетки в одной транзакции)."""

    def __init__(self, connect: Callable[[], psycopg.Connection]):
        self.connect = connect
        self.conn = connect()

    def run(self, action: Callable[[psycopg.Connection], Any]) -> Any:
        try:
            return self._once(action)
        except psycopg.OperationalError:
            with contextlib.suppress(Exception):
                self.conn.close()
            self.conn = self.connect()
            return self._once(action)

    def _once(self, action):
        try:
            return action(self.conn)
        except psycopg.OperationalError:
            raise
        except Exception:
            with contextlib.suppress(psycopg.Error):
                self.conn.rollback()  # прерванная транзакция не должна ломать следующий этап
            raise

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self.conn.close()


# ежечасный запуск: сначала все запросы к Open-Meteo (с повторами при сбоях они могут идти минутами) – база в это
# время не нужна; потом запись по свежему соединению. Этапы независимы: если не обновился ряд, снимки прогнозов
# всё равно сохраняются (их нельзя восстановить задним числом); итог каждого запуска пишется в runs
def hourly(connect: Callable[[], psycopg.Connection], now: pd.Timestamp | None = None,
           limit_mb: float = DB_LIMIT_MB) -> dict:
    now = now if now is not None else pd.Timestamp.now(tz="UTC")
    started = clock.perf_counter()
    issued_at = now.floor("h")
    result = {"hours_added": None, "cams_rows": None, "weather_rows": None, "region_rows": None,
              "cleaned_rows": None, "db_mb": None}
    errors = []

    session = Session(connect)
    try:
        session.run(db.init_schema)
        last = session.run(db.last_time)
    finally:
        session.close()  # дальше – только сеть: соединение не держим

    fetched = {}

    def fetch(key: str, label: str, action: Callable[[], Any]) -> None:
        try:
            fetched[key] = action()
        except Exception as error:  # noqa: BLE001 – ошибку этапа записываем в журнал и идём дальше
            errors.append(f"{label}: {error}")

    start = START_DATE if last is None else (last - timedelta(days=OVERLAP_DAYS)).date()
    fetch("series", "ряд", lambda: clean(download(start, now.date()), now))
    fetch("cams_forecasts", "прогноз CAMS", lambda: fetch_forecast("cams_forecasts", issued_at))
    fetch("weather_forecasts", "прогноз погоды", lambda: fetch_forecast("weather_forecasts", issued_at))
    fetch("region", "карта", lambda: fetch_region(issued_at))

    def write(key: str, label: str, action: Callable[[psycopg.Connection], Any]) -> None:
        try:
            result[key] = session.run(action)
        except Exception as error:  # noqa: BLE001
            errors.append(f"{label}: {error}")

    session = Session(connect)
    try:
        if "series" in fetched:
            fresh = fetched["series"]
            write("hours_added", "ряд", lambda c: db.upsert_series(c, fresh))
            if result["hours_added"] is not None:
                result["hours_added"] = int((fresh["time"] > last).sum()) if last is not None else len(fresh)
        for table, key in (("cams_forecasts", "cams_rows"), ("weather_forecasts", "weather_rows")):
            if table in fetched:
                label = "прогноз CAMS" if table == "cams_forecasts" else "прогноз погоды"
                write(key, label, lambda c, t=table: db.save_forecast(c, t, issued_at, fetched[t]))
        if "region" in fetched:
            write("region_rows", "карта", lambda c: db.replace_region(c, fetched["region"]))
        write("cleaned_rows", "очистка", lambda c: db.cleanup(c, now, limit_mb, KEEP_DAYS))
        write("db_mb", "размер базы", lambda c: round(db.db_size_mb(c), 2))
        try:
            last = session.run(db.last_time)
            result["series_last"] = None if last is None else last.to_pydatetime()
        except psycopg.Error:
            result["series_last"] = None
        result["status"] = "error" if errors else "ok"
        result["error"] = "; ".join(errors)[:2000] or None
        result["duration_ms"] = int((clock.perf_counter() - started) * 1000)
        session.run(lambda c: db.log_run(c, started_at=now.to_pydatetime(), **result))
    finally:
        session.close()
    return result
