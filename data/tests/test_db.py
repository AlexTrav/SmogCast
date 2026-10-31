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
            cur.execute("drop table if exists series, cams_forecasts, weather_forecasts, runs, region, model_forecasts, model_runs, prophet_parts")
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


# сетка для карты: 2 точки по 3 часа
def fake_region(issued_at):
    times = pd.date_range(issued_at - pd.Timedelta(hours=1), periods=3, freq="h")
    frames = [pd.DataFrame({"lat": lat, "lon": 76.9, "time": times, "pm2_5": 20.0, "pm10": 30.0, "wind": 5.0,
                            "wind_dir": 180.0}) for lat in (43.3, 43.7)]
    return pd.concat(frames, ignore_index=True).assign(issued_at=issued_at)


def runs(conn) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute("select status, hours_added, cams_rows, weather_rows, error from runs order by id")
        return cur.fetchall()


def test_schema_is_idempotent(conn):
    db.init_schema(conn)
    assert db.counts(conn) == {"series": 0, "cams_forecasts": 0, "weather_forecasts": 0, "runs": 0, "region": 0, "model_forecasts": 0, "model_runs": 0, "prophet_parts": 0}


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
    monkeypatch.setattr(live, "fetch_region", fake_region)
    now = START + timedelta(days=3, hours=5, minutes=30)

    first = live.hourly(conn, now)
    assert first["status"] == "ok" and first["hours_added"] == 3 * 24 + 6
    assert first["cams_rows"] == first["weather_rows"] == 120
    assert first["series_last"] == (START + timedelta(days=3, hours=5)).to_pydatetime()

    assert first["cleaned_rows"] == 0 and first["db_mb"] > 0

    # повтор в тот же час (ручной запуск или задержка cron) ничего не дублирует
    again = live.hourly(conn, now + timedelta(minutes=10))
    assert again["hours_added"] == 0 and again["cams_rows"] == 0
    assert db.counts(conn) == {"series": 3 * 24 + 6, "cams_forecasts": 120, "weather_forecasts": 120, "runs": 2, "region": 6, "model_forecasts": 0, "model_runs": 0, "prophet_parts": 0}

    later = live.hourly(conn, now + timedelta(hours=2))
    assert later["hours_added"] == 2
    assert db.counts(conn)["cams_forecasts"] == 240  # новый снимок – новый час выпуска


# прогноз одного прогона модели: часы не зависят от момента снимка, сдвигается только начало
def run_forecast(issued_at, run_start, value=30.0):
    times = pd.date_range(run_start, periods=96, freq="h")
    frame = pd.DataFrame({"time": times, "pm2_5": value, "pm10": 45.0})
    return frame[frame["time"] > issued_at]


def test_region_snapshot_is_replaced_not_accumulated(conn):
    first = START + timedelta(hours=10)
    assert db.replace_region(conn, fake_region(first)) == 6
    assert db.replace_region(conn, fake_region(first + timedelta(hours=1))) == 6
    with conn.cursor() as cur:
        cur.execute("select count(*), min(issued_at) from region")
        count, issued = cur.fetchone()
    assert count == 6 and issued == (first + timedelta(hours=1)).to_pydatetime()


def test_unchanged_forecast_is_not_saved_again(conn):
    run = START + timedelta(hours=12)
    assert db.save_forecast(conn, "cams_forecasts", START + timedelta(hours=13), run_forecast(START, run)) == 96
    # через час тот же прогон: часы – подмножество прошлого снимка, значения те же
    shifted = run_forecast(START + timedelta(hours=14), run)
    assert db.save_forecast(conn, "cams_forecasts", START + timedelta(hours=14), shifted) == 0
    # новый прогон: значения изменились
    fresh = run_forecast(START + timedelta(hours=15), run, value=31.0)
    assert db.save_forecast(conn, "cams_forecasts", START + timedelta(hours=15), fresh) == len(fresh)
    latest = db.latest_forecast(conn, "cams_forecasts")
    assert (latest["pm2_5"] == 31.0).all() and len(latest) == len(fresh)


def test_cleanup_deletes_only_old_snapshots_over_limit(conn):
    now = START + timedelta(days=60)
    db.upsert_series(conn, make_frame(48))
    for days_ago in (40, 30, 1):
        issued = now - timedelta(days=days_ago)
        for table, frame in zip(db.SNAPSHOT_TABLES, fake_forecasts(issued)):
            frame = frame.copy()
            frame.iloc[:, 1:] = float(days_ago)  # разные значения – иначе снимок не сохранится
            db.save_forecast(conn, table, issued, frame)
    assert db.cleanup(conn, now, limit_mb=10_000, keep_days=14) == 0  # база меньше порога – ничего не трогаем

    # порог заведомо ниже размера пустой базы: удаляется всё, кроме снимков моложе 14 дней
    assert db.cleanup(conn, now, limit_mb=1, keep_days=14) == 2 * 2 * 120
    assert db.counts(conn) == {"series": 48, "cams_forecasts": 120, "weather_forecasts": 120, "runs": 0, "region": 0, "model_forecasts": 0, "model_runs": 0, "prophet_parts": 0}
    assert db.cleanup(conn, now, limit_mb=1, keep_days=14) == 0


def test_hourly_saves_forecasts_when_series_fails(conn, monkeypatch):
    def broken(*_):
        raise RuntimeError("сеть недоступна")

    monkeypatch.setattr(live, "download", broken)
    monkeypatch.setattr(live, "fetch_forecasts", fake_forecasts)
    monkeypatch.setattr(live, "fetch_region", fake_region)
    result = live.hourly(conn, START + timedelta(hours=5))
    assert result["status"] == "error" and "ряд: сеть недоступна" in result["error"]
    assert result["cams_rows"] == 120
    assert runs(conn) == [("error", None, 120, 120, "ряд: сеть недоступна")]
