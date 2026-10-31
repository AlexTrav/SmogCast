from datetime import timedelta

import pytest

from api import main
from conftest import LAST, START, pm

ISSUED = LAST - timedelta(hours=30)  # прогноз, у которого факт известен на первые 30 ч
DEFAULT = main.DEFAULT_MODEL


def index(t) -> int:
    return int((t - START).total_seconds() // 3600)


@pytest.fixture
def verified(filled):
    times = [ISSUED + timedelta(hours=h) for h in range(1, 73)]
    with filled.cursor() as cur:
        cur.execute("delete from model_forecasts where issued_at = %s", (LAST - timedelta(hours=1),))
        # модель по умолчанию ошибается на +2, ARIMA – на –4
        for model, shift in ((DEFAULT, 2), ("arima", -4)):
            cur.executemany("insert into model_forecasts values (%s, %s, %s, %s, 0, 99, 0, 99)",
                            [(ISSUED, model, t, pm(index(t)) + shift) for t in times])
        # CAMS: снимок до выпуска нашего прогноза ошибается на +1; более поздний снимок (+50) брать нельзя
        for issued, shift in ((ISSUED - timedelta(hours=2), 1), (ISSUED + timedelta(hours=1), 50)):
            cur.executemany("insert into cams_forecasts (issued_at, time, pm2_5) values (%s, %s, %s)",
                            [(issued, t, pm(index(t)) + shift) for t in [ISSUED - timedelta(hours=1), *times]])
    filled.commit()
    return filled


def test_verify_mae_by_model_horizon_and_day(client, verified):
    body = client.get("/api/verify").json()
    models = body["models"]
    assert set(models) == {DEFAULT, "arima", "cams"}
    assert models[DEFAULT]["mae"] == 2 and models["arima"]["mae"] == 4 and models["cams"]["mae"] == 1
    assert models[DEFAULT]["hours"] == 30
    assert models[DEFAULT]["buckets"] == {"1–24": 2, "25–48": 2, "49–72": None}
    # часы 09.10 18:00 – 10.10 23:00 UTC – это 09.10–11.10 по Алматы
    assert body["dates"] == ["2026-10-09", "2026-10-10", "2026-10-11"]
    assert models["arima"]["daily"] == [4, 4, 4]


def test_verify_yesterday_forecast_next_to_actual(client, verified):
    yesterday = client.get("/api/verify").json()["yesterday"]
    assert yesterday["issued_at"] == "2026-10-09T17:00:00Z" and len(yesterday["pred"]) == 72
    assert yesterday["actual"][:30] == [pm(index(ISSUED) + h) for h in range(1, 31)]
    assert yesterday["actual"][30:] == [None] * 42
    assert yesterday["pred"][0] == yesterday["actual"][0] + 2


def test_verify_days_are_limited(client, filled):
    assert client.get("/api/verify", params={"days": 0}).status_code == 422
    assert client.get("/api/verify", params={"days": 31}).status_code == 422
    # у прогнозов от последнего часа факта ещё нет; прогноз от прошлого часа на последний час: 99 против 33
    models = client.get("/api/verify").json()["models"]
    assert set(models) == {DEFAULT} and models[DEFAULT]["mae"] == 99 - pm(239)


def test_models_come_from_reports_and_are_static(client):
    response = client.get("/api/models")
    body = response.json()
    assert body["selection"]["default"] == DEFAULT
    assert DEFAULT in body["test"]["models"] and "1–24" in body["test"]["aqi"][DEFAULT]
    again = client.get("/api/models", headers={"If-None-Match": response.headers["etag"]})
    assert again.status_code == 304


def test_performance_runs_models_and_api(client, filled):
    client.get("/api/status")
    body = client.get("/api/performance").json()
    assert body["data_runs"][0]["duration_ms"] == 900 and body["data_runs"][0]["status"] == "ok"
    assert body["model_runs"][0]["model_ms"] == {"arima": 11000, "lstm": 40}
    assert body["summary"]["data_ms"] == {"p50": 900, "p95": 900, "max": 900}
    assert body["summary"]["model_ms"]["arima"]["p50"] == 11000 and body["summary"]["success"] == 100
    assert body["api"]["paths"]["/api/status"]["requests"] >= 1
    assert "server-timing" in client.get("/api/health").headers


@pytest.fixture
def forecasted(filled):
    times = [LAST + timedelta(hours=h) for h in range(1, 73)]
    marks = ", ".join(["%s"] * 10)
    columns = "issued_at, time, temp, rh, dew, wind, wind_dir, pressure, precip, cloud"
    with filled.cursor() as cur:
        # старый снимок – тепло; свежий – мороз, штиль и без осадков
        for issued, temp in ((LAST - timedelta(hours=6), 10.0), (LAST, -5.0)):
            cur.executemany(f"insert into weather_forecasts ({columns}) values ({marks})",
                            [(issued, t, temp, 80, -7, 2, 90, 930, 0, 100) for t in times])
    filled.commit()
    return filled


def test_weather_takes_freshest_snapshot_and_factors(client, forecasted):
    body = client.get("/api/weather").json()
    assert body["start"] == "2026-10-11T00:00:00Z" and len(body["values"]["temp"]) == 72
    assert body["values"]["temp"][0] == -5 and body["issued_at"] == "2026-10-10T23:00:00Z"
    factors = {f["key"]: f["active"] for f in body["factors"]}
    # 11.10 по Алматы – ещё до отопительного сезона (с 15.10)
    assert factors == {"cold": True, "calm": True, "dry": True, "heating": False}


def test_weather_without_forecast_is_empty_not_error(client, filled):
    body = client.get("/api/weather").json()
    assert body["values"]["temp"] == [None] * 72
    assert {f["key"]: f["active"] for f in body["factors"]}["cold"] is False


def test_heating_season_bounds():
    from api.weather import heating
    from datetime import date
    assert [heating(date(2026, m, d)) for m, d in ((10, 14), (10, 15), (1, 1), (4, 15), (4, 16))] == \
           [False, True, True, True, False]


def test_region_grid_by_hour_lat_lon(client, filled):
    rows = [(lat, lon, LAST + timedelta(hours=h), LAST, 10 * lat + lon, 1, 3, 180)
            for h in range(3) for lat in (43.3, 43.7) for lon in (76.9, 77.3)]
    with filled.cursor() as cur:
        cur.executemany("insert into region (lat, lon, time, issued_at, pm2_5, pm10, wind, wind_dir) "
                        "values (%s, %s, %s, %s, %s, %s, %s, %s)", rows[:-1])  # одной ячейки нет
    filled.commit()
    body = client.get("/api/region").json()
    assert body["lats"] == [43.3, 43.7] and body["lons"] == [76.9, 77.3] and body["hours"] == 3
    assert body["pm2_5"][0][1][0] == round(10 * 43.7 + 76.9, 1)
    assert body["pm2_5"][2][1][1] is None


def test_region_without_grid_is_unavailable(client, filled):
    assert client.get("/api/region").status_code == 503
