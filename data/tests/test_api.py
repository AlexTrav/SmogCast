from datetime import date

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
