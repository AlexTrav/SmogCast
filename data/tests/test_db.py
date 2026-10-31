"""Тесты базы на настоящем Postgres той же версии, что в Neon (make test поднимает его в docker compose)."""
import os
from datetime import timedelta

import pandas as pd
import pytest

from collect import db, live
from collect.config import START_DATE, WEATHER_VARS
from conftest import make_frame

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="нужен TEST_DATABASE_URL – make test поднимает Postgres")
START = pd.Timestamp(START_DATE).tz_localize("UTC")


@pytest.fixture
def conn():
    with db.connect(URL) as conn:
        with conn.cursor() as cur:
            cur.execute("drop table if exists series, cams_forecasts, weather_forecasts, runs")
        conn.commit()
        db.init_schema(conn)
        yield conn


# вместо Open-Meteo: ряд с START_DATE до конца запрошенного дня, как отдаёт API
def fake_download(a, b):
    hours = int((pd.Timestamp(b) - pd.Timestamp(START_DATE)) / pd.Timedelta(hours=1)) + 24
    full = make_frame(hours)
    return full[full["time"] >= pd.Timestamp(a).tz_localize("UTC")]


# прогнозы на 5 суток вперёд от часа снимка
def fake_forecasts(issued_at):
    times = pd.date_range(issued_at + pd.Timedelta(hours=1), periods=120, freq="h")
    air = pd.DataFrame({"time": times, "pm2_5": 30.0, "pm10": 45.0})
    weather = pd.DataFrame({"time": times, **{c: 1.0 for c in WEATHER_VARS.values()}})
    return air, weather


def runs(conn) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute("select status, hours_added, cams_rows, weather_rows, error from runs order by id")
        return cur.fetchall()


def test_schema_is_idempotent(conn):
    db.init_schema(conn)
    assert db.counts(conn) == {"series": 0, "cams_forecasts": 0, "weather_forecasts": 0, "runs": 0}


def test_upsert_series_updates_overlap_without_duplicates(conn):
    old = make_frame(48)
    old.loc[5, "pm2_5"] = 12.3
    db.upsert_series(conn, old)
    new = make_frame(30, start=old["time"].iloc[30])
    new["pm2_5"] = 99.0
    db.upsert_series(conn, new)

    stored = db.read_series(conn)
    assert len(stored) == 60 and stored["time"].is_unique
    assert stored.loc[5, "pm2_5"] == 12.3  # double precision: значение возвращается без искажений float32
    assert (stored.loc[30:, "pm2_5"] == 99.0).all()
    assert db.last_time(conn) == new["time"].iloc[-1]
    assert len(db.read_series(conn, since=old["time"].iloc[40])) == 20


def test_last_time_of_empty_series(conn):
    assert db.last_time(conn) is None


def test_seed_is_repeatable(conn, monkeypatch):
    monkeypatch.setattr(live, "read_series", lambda: make_frame(100))
    assert live.seed(conn) == 100
    assert live.seed(conn) == 100
    assert db.counts(conn)["series"] == 100


def test_hourly_adds_hours_and_snapshots(conn, monkeypatch):
    monkeypatch.setattr(live, "download", fake_download)
    monkeypatch.setattr(live, "fetch_forecasts", fake_forecasts)
    now = START + timedelta(days=3, hours=5, minutes=30)

    first = live.hourly(conn, now)
    assert first["status"] == "ok" and first["hours_added"] == 3 * 24 + 6
    assert first["cams_rows"] == first["weather_rows"] == 120
    assert first["series_last"] == (START + timedelta(days=3, hours=5)).to_pydatetime()

    # повтор в тот же час (ручной запуск или задержка cron) ничего не дублирует
    again = live.hourly(conn, now + timedelta(minutes=10))
    assert again["hours_added"] == 0
    assert db.counts(conn) == {"series": 3 * 24 + 6, "cams_forecasts": 120, "weather_forecasts": 120, "runs": 2}

    later = live.hourly(conn, now + timedelta(hours=2))
    assert later["hours_added"] == 2
    assert db.counts(conn)["cams_forecasts"] == 240  # новый снимок – новый час выпуска


def test_hourly_saves_forecasts_when_series_fails(conn, monkeypatch):
    def broken(*_):
        raise RuntimeError("сеть недоступна")

    monkeypatch.setattr(live, "download", broken)
    monkeypatch.setattr(live, "fetch_forecasts", fake_forecasts)
    result = live.hourly(conn, START + timedelta(hours=5))
    assert result["status"] == "error" and "ряд: сеть недоступна" in result["error"]
    assert result["cams_rows"] == 120
    assert runs(conn) == [("error", None, 120, 120, "ряд: сеть недоступна")]
