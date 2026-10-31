from datetime import timedelta

from api import levels
from conftest import HOURS, LAST, START, pm


def test_aqi_matches_epa_2024_breakpoints():
    assert [levels.aqi(c) for c in (0, 9.0, 9.1, 35.4, 35.5, 55.4, 125.4, 225.4, 325.4, 600)] == \
           [0, 50, 51, 100, 101, 150, 200, 300, 500, 500]
    assert levels.aqi(9.09) == 50  # концентрация усекается до 0,1, а не округляется
    assert [levels.level(c) for c in (5, 20, 40, 100, 200, 300)] == \
           ["good", "moderate", "sensitive", "unhealthy", "very_unhealthy", "hazardous"]


def test_health_does_not_need_database(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_status_reports_last_hour_and_runs(client, filled):
    body = client.get("/api/status").json()
    last = pm(HOURS - 1)
    assert body["time"] == "2026-10-10T23:00:00Z" and body["pm2_5"] == last
    assert body["aqi"] == levels.aqi(last) and body["level"] == "moderate"
    assert body["change_24h"] == 0  # час сутками раньше – то же значение суточного цикла
    assert body["data_run"]["status"] == "ok" and body["model_run"]["issued_at"] == body["time"]


def test_status_is_not_modified_until_new_data(client, filled):
    first = client.get("/api/status")
    etag = first.headers["etag"]
    again = client.get("/api/status", headers={"If-None-Match": etag})
    assert again.status_code == 304 and again.content == b""
    filled.execute("insert into series select time + interval '1 hour', pm2_5 + 1, pm10, no2, co, so2, dust, temp, "
                   "rh, dew, wind, wind_dir, pressure, precip, cloud from series where time = %s", (LAST,))
    filled.commit()
    fresh = client.get("/api/status", headers={"If-None-Match": etag})
    assert fresh.status_code == 200 and fresh.json()["time"] == "2026-10-11T00:00:00Z"


def test_status_without_series_is_unavailable(client, conn):
    assert client.get("/api/status").status_code == 503


def test_forecast_default_model_with_intervals_and_cams(client, filled):
    body = client.get("/api/forecast").json()
    assert body["model"] == body["default_model"] and body["issued_at"] == "2026-10-10T23:00:00Z"
    assert body["start"] == "2026-10-11T00:00:00Z" and len(body["pred"]) == 72
    assert set(body["models"]) == {"arima", body["default_model"]}
    assert body["pred"][0] == 20 and body["lo95"][0] < body["lo80"][0] < body["pred"][0] < body["hi80"][0]
    assert body["cams"][:24] == [7] * 24 and body["cams"][24:] == [5] * 48  # свежий снимок, где час есть


def test_forecast_other_and_unknown_model(client, filled):
    assert client.get("/api/forecast", params={"model": "arima"}).json()["pred"][0] == 30
    missing = client.get("/api/forecast", params={"model": "nope"})
    assert missing.status_code == 404 and "arima" in missing.json()["detail"]["models"]


def test_history_hours_whole_series(client, filled):
    body = client.get("/api/history", params={"step": "hour"}).json()
    assert body["start"] == "2026-10-01T00:00:00Z"
    assert body["values"]["pm2_5"] == [pm(i) for i in range(HOURS)]


def test_history_hours_of_one_local_day_with_gap(client, filled):
    filled.execute("delete from series where time = %s", (START + timedelta(hours=20),))
    filled.commit()
    # 02.10 по Алматы (UTC+5) – с 01.10 19:00 до 02.10 18:00 UTC
    body = client.get("/api/history", params={"step": "hour", "from": "2026-10-02", "to": "2026-10-02",
                                              "fields": "pm2_5,temp"}).json()
    assert body["start"] == "2026-10-01T19:00:00Z"
    assert len(body["values"]["pm2_5"]) == 24 and body["values"]["pm2_5"][1] is None  # пропуск – null
    assert body["values"]["temp"][0] == 1


def test_history_days_by_local_time(client, filled):
    body = client.get("/api/history").json()
    # ряд с 01.10 00:00 UTC = 05:00 по Алматы: первые местные сутки неполные (19 ч)
    assert body["start"] == "2026-10-01" and body["hours"][0] == 19 and body["hours"][1] == 24
    assert len(body["hours"]) == 11 and sum(body["hours"]) == HOURS
    day = [pm(i) for i in range(19, 43)]
    assert body["values"]["pm2_5"]["mean"][1] == round(sum(day) / 24, 1)
    assert body["values"]["pm2_5"]["max"][1] == max(day)


def test_history_rejects_bad_parameters(client, filled):
    assert client.get("/api/history", params={"fields": "password"}).status_code == 400
    assert client.get("/api/history", params={"fields": "pm2_5,pm10,no2,co,so2"}).status_code == 400
    assert client.get("/api/history", params={"from": "2026-10-05", "to": "2026-10-01"}).status_code == 400
    assert client.get("/api/history", params={"step": "week"}).status_code == 422


def test_responses_are_compressed(client, filled):
    response = client.get("/api/history", params={"step": "hour"}, headers={"Accept-Encoding": "gzip"})
    assert response.headers["content-encoding"] == "gzip"
