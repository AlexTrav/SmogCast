"""Живая часть: ряд в базе и ежечасный запуск (GitHub Actions) – свежие часы, снимки прогнозов, журнал."""
import time as clock
from datetime import timedelta

import pandas as pd
import psycopg

from . import db
from .api import fetch_hourly
from .config import (
    AIR_URL,
    DB_LIMIT_MB,
    FORECAST_DAYS,
    KEEP_DAYS,
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


# прогнозы CAMS и погоды IFS, известные в момент issued_at, на FORECAST_DAYS суток вперёд (только будущие часы)
def fetch_forecasts(issued_at: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    start, end = issued_at.date(), (issued_at + timedelta(days=FORECAST_DAYS)).date()
    stop = issued_at + timedelta(days=FORECAST_DAYS)
    air = fetch_hourly(AIR_URL, {"pm2_5": "pm2_5", "pm10": "pm10"}, start, end, {"domains": "cams_global"})
    weather = fetch_hourly(WEATHER_FORECAST_URL, WEATHER_VARS, start, end, {"models": WEATHER_FORECAST_MODEL})

    def ahead(frame: pd.DataFrame) -> pd.DataFrame:
        frame = frame[(frame["time"] > issued_at) & (frame["time"] <= stop)]
        return frame.dropna(how="all", subset=list(frame.columns[1:]))

    return ahead(air), ahead(weather)


# ежечасный запуск: этапы независимы – если не обновился ряд, снимки прогнозов всё равно сохраняются
# (их нельзя восстановить задним числом); затем очистка по размеру базы; итог каждого запуска пишется в runs
def hourly(conn: psycopg.Connection, now: pd.Timestamp | None = None, limit_mb: float = DB_LIMIT_MB) -> dict:
    now = now if now is not None else pd.Timestamp.now(tz="UTC")
    started = clock.perf_counter()
    issued_at = now.floor("h")
    result = {"hours_added": None, "cams_rows": None, "weather_rows": None, "cleaned_rows": None, "db_mb": None}
    errors = []
    db.init_schema(conn)

    try:
        last = db.last_time(conn)
        start = START_DATE if last is None else (last - timedelta(days=OVERLAP_DAYS)).date()
        fresh = clean(download(start, now.date()), now)
        db.upsert_series(conn, fresh)
        result["hours_added"] = int((fresh["time"] > last).sum()) if last is not None else len(fresh)
    except Exception as error:  # noqa: BLE001 – ошибку этапа записываем в журнал и идём дальше
        errors.append(f"ряд: {error}")

    try:
        air, weather = fetch_forecasts(issued_at)
        result["cams_rows"] = db.save_forecast(conn, "cams_forecasts", issued_at, air)
        result["weather_rows"] = db.save_forecast(conn, "weather_forecasts", issued_at, weather)
    except Exception as error:  # noqa: BLE001
        errors.append(f"прогнозы: {error}")

    try:
        conn.rollback()
        result["cleaned_rows"] = db.cleanup(conn, now, limit_mb, KEEP_DAYS)
        result["db_mb"] = round(db.db_size_mb(conn), 2)
    except Exception as error:  # noqa: BLE001
        errors.append(f"очистка: {error}")

    try:
        conn.rollback()  # после ошибки этапа транзакция могла остаться прерванной
        last = db.last_time(conn)
        result["series_last"] = None if last is None else last.to_pydatetime()
    except psycopg.Error:
        result["series_last"] = None
    result["status"] = "error" if errors else "ok"
    result["error"] = "; ".join(errors)[:2000] or None
    result["duration_ms"] = int((clock.perf_counter() - started) * 1000)
    db.log_run(conn, started_at=now.to_pydatetime(), **result)
    return result
