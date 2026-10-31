"""Кнопка «Пересчитать сейчас»: лёгкие модели от последнего часа ряда и защита от частых нажатий."""
from datetime import timedelta

import pytest

from api import common, recompute
from conftest import LAST

LIGHT = ["seasonal_24", "profile_7d", "lstm", "lstm_weather"]


@pytest.fixture(autouse=True)
def fresh():
    recompute.reset()
    yield
    recompute.reset()


# прогноз погоды на 72 ч после последнего часа ряда – для LSTM с погодой
def add_weather(conn) -> None:
    with conn.cursor() as cur:
        cur.executemany("insert into weather_forecasts (issued_at, time, temp, wind, precip) values (%s, %s, 2, 3, 0)",
                        [(LAST, LAST + timedelta(hours=h)) for h in range(1, 73)])
    conn.commit()


def test_recompute_light_models_from_last_hour(filled, client):
    add_weather(filled)
    body = client.post("/api/recompute").json()
    assert body["issued_at"] == common.iso(LAST) and body["cached"] is False
    assert [m["model"] for m in body["models"]] == [*LIGHT, common.DEFAULT_MODEL]
    assert all(m["error"] is None and len(m["pred"]) == 72 for m in body["models"])
    assert all(m["ms"] >= 0 for m in body["models"][:-1])
    models = {m["model"]: m for m in body["models"]}
    # ряд повторяется каждые сутки (PM2.5 = 10 + час % 24): сезонная и профиль дают тот же час прошлых суток
    expected = [10.0 + (239 + h) % 24 for h in range(1, 73)]
    assert models["seasonal_24"]["pred"] == expected and models["profile_7d"]["pred"] == expected
    # ARIMA здесь не считается – в смесь она берётся из ежечасного расчёта; расхождение – с сохранённой смесью
    assert body["reused"] == ["arima"] and body["skipped"] == ["arima", "prophet"]
    assert models[common.DEFAULT_MODEL]["diff"] is not None and models["seasonal_24"]["diff"] is None


def test_same_address_waits_30_seconds(filled, client):
    add_weather(filled)
    assert client.post("/api/recompute").status_code == 200
    response = client.post("/api/recompute")
    assert response.status_code == 429
    assert response.json()["detail"]["error"] == "too_often"
    assert 1 <= int(response.headers["Retry-After"]) <= recompute.LIMIT_S


def test_repeat_in_same_hour_returns_ready_result(filled, client):
    add_weather(filled)
    first = client.post("/api/recompute").json()
    recompute._last.clear()  # другой посетитель
    second = client.post("/api/recompute").json()
    assert second["cached"] is True and second["computed_at"] == first["computed_at"]


def test_one_recompute_at_a_time(filled, client):
    recompute._lock.acquire()
    try:
        response = client.post("/api/recompute")
    finally:
        recompute._lock.release()
    assert response.status_code == 429 and response.json()["detail"]["error"] == "busy"


def test_missing_weather_does_not_stop_other_models(filled, client):
    models = {m["model"]: m for m in client.post("/api/recompute").json()["models"]}
    assert "нет прогноза погоды" in models["lstm_weather"]["error"] and models["lstm_weather"]["pred"] is None
    assert all(models[k]["error"] is None for k in ("seasonal_24", "profile_7d", "lstm"))
    assert common.DEFAULT_MODEL not in models  # без LSTM с погодой смесь не собрать
