from datetime import date

import pytest
import requests

from collect import api


def test_points_request_keeps_requested_coordinates(monkeypatch):
    seen = {}

    # Open-Meteo на несколько точек отвечает списком; координаты в ответе – узлы сетки, а не запрошенные
    def fake_get_json(url, params):
        seen.update(params)
        return [{"latitude": 43.300003, "hourly": {"time": ["2026-10-31T00:00", "2026-10-31T01:00"],
                                                   "pm2_5": [10.0, 11.0]}},
                {"latitude": 43.699997, "hourly": {"time": ["2026-10-31T00:00", "2026-10-31T01:00"],
                                                   "pm2_5": [20.0, None]}}]

    monkeypatch.setattr(api, "get_json", fake_get_json)
    frame = api.fetch_hourly_points("url", {"pm2_5": "pm2_5"}, [(43.3, 76.9), (43.7, 76.9)],
                                    date(2026, 10, 31), date(2026, 10, 31))
    assert seen["latitude"] == "43.3,43.7" and seen["longitude"] == "76.9,76.9"
    assert list(frame.columns) == ["lat", "lon", "time", "pm2_5"]
    assert frame["lat"].tolist() == [43.3, 43.3, 43.7, 43.7]
    assert frame["pm2_5"].isna().sum() == 1 and str(frame["time"].dt.tz) == "UTC"


class FakeResponse:
    def __init__(self, status: int, payload=None, headers=None):
        self.status_code, self.payload, self.headers = status, payload, headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")

    def json(self):
        return self.payload


# сценарий ответов: исключение или ответ; паузы между повторами записываются, а не выжидаются
def scripted(monkeypatch, *outcomes):
    calls, sleeps = [], []
    queue = list(outcomes)

    def fake_get(url, **kwargs):
        calls.append(url)
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(api.requests, "get", fake_get)
    monkeypatch.setattr(api.time, "sleep", sleeps.append)
    monkeypatch.setattr(api.random, "uniform", lambda a, b: 1.0)
    return calls, sleeps


def test_retries_with_growing_pauses_until_success(monkeypatch):
    calls, sleeps = scripted(monkeypatch, requests.Timeout(), requests.ConnectionError(), FakeResponse(503),
                             FakeResponse(502), FakeResponse(200, {"ok": 1}))
    assert api.get_json("url", {}) == {"ok": 1}
    assert len(calls) == 5 and sleeps == [5, 10, 20, 40]


def test_gives_up_after_five_attempts(monkeypatch):
    calls, sleeps = scripted(monkeypatch, *[requests.Timeout()] * 5)
    with pytest.raises(requests.Timeout):
        api.get_json("url", {})
    assert len(calls) == 5 and len(sleeps) == 4


def test_client_errors_are_not_retried_and_retry_after_is_respected(monkeypatch):
    calls, sleeps = scripted(monkeypatch, FakeResponse(400))
    with pytest.raises(requests.HTTPError):
        api.get_json("url", {})
    assert len(calls) == 1 and sleeps == []
    calls, sleeps = scripted(monkeypatch, FakeResponse(429, headers={"Retry-After": "30"}), FakeResponse(200, {}))
    api.get_json("url", {})
    assert sleeps == [30]


def test_retry_budget_stops_retries_so_the_hourly_run_ends_in_time(monkeypatch):
    calls, sleeps = scripted(monkeypatch, *[requests.Timeout()] * 5)
    monkeypatch.setattr(api, "_started", api.time.monotonic() - api.RETRY_BUDGET_SEC + 7)
    with pytest.raises(requests.Timeout):
        api.get_json("url", {})
    # до конца бюджета 7 с: первая пауза (5 с) ещё влезает, вторая (10 с) – уже нет
    assert len(calls) == 2 and sleeps == [5]
