"""Тестовая база: таблицы создаёт служба schema в compose.test.yml, здесь – данные под каждый тест."""
import os
from datetime import datetime, timedelta, timezone

import psycopg
import pytest
from fastapi.testclient import TestClient

from api import common, db, main

START = datetime(2026, 10, 1, tzinfo=timezone.utc)
HOURS = 240  # 10 суток ряда
LAST = START + timedelta(hours=HOURS - 1)
FIELDS = main.FIELDS
TABLES = "series, cams_forecasts, weather_forecasts, runs, region, model_forecasts, model_runs"


# PM2.5 в час i – 10 + i % 24: по значению легко проверить, какой час попал в ответ
def pm(i: int) -> float:
    return 10.0 + i % 24


@pytest.fixture
def conn():
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        conn.execute(f"truncate {TABLES} restart identity")
        conn.commit()
        db.reset_version()
        common._cache.clear()
        yield conn


@pytest.fixture
def filled(conn):
    columns = ", ".join(("time", *FIELDS))
    marks = ", ".join(["%s"] * (len(FIELDS) + 1))
    with conn.cursor() as cur:
        cur.executemany(f"insert into series ({columns}) values ({marks})",
                        [(START + timedelta(hours=i), pm(i), *[1.0] * (len(FIELDS) - 1)) for i in range(HOURS)])
        cur.execute("insert into runs (started_at, duration_ms, status, hours_added) values (%s, 900, 'ok', 1)",
                    (LAST + timedelta(minutes=77),))
        cur.execute("insert into model_runs (started_at, issued_at, duration_ms, model_ms, status) "
                    "values (%s, %s, 60000, '{\"arima\": 11000, \"lstm\": 40}', 'ok')", (LAST + timedelta(minutes=79), LAST))
        times = [LAST + timedelta(hours=h) for h in range(1, 73)]
        for model, value in ((main.DEFAULT_MODEL, 20.0), ("arima", 30.0)):
            cur.executemany("insert into model_forecasts values (%s, %s, %s, %s, %s, %s, %s, %s)",
                            [(LAST, model, t, value, value - 5, value + 5, value - 8, value + 8) for t in times])
        # старый прогноз модели от прошлого часа – в ответ не попадает
        cur.execute("insert into model_forecasts values (%s, %s, %s, 99, 98, 100, 97, 101)",
                    (LAST - timedelta(hours=1), main.DEFAULT_MODEL, LAST))
        # снимки CAMS: старый на все 72 ч, новый – только на первые 24 ч
        cur.executemany("insert into cams_forecasts (issued_at, time, pm2_5) values (%s, %s, 5)",
                        [(LAST - timedelta(hours=12), t) for t in times])
        cur.executemany("insert into cams_forecasts (issued_at, time, pm2_5) values (%s, %s, 7)",
                        [(LAST, t) for t in times[:24]])
    conn.commit()
    return conn


@pytest.fixture(scope="session")
def client():
    with TestClient(main.app) as client:
        yield client
