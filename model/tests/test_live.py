import numpy as np
import pandas as pd

import live
import lstm
import prep

DEFAULT = "arima+lstm+lstm_weather"


# ряд в формате базы: все колонки, местное время; суточный цикл, чтобы модели было что выучить
def frame(days: int = 40) -> pd.DataFrame:
    index = pd.date_range("2026-08-01", periods=days * 24, freq="h", tz=prep.TZ)
    rng = np.random.default_rng(0)
    hours = index.hour.to_numpy()
    data = {c: 1.0 for c in ("pm10", "so2", "dust", "rh", "dew", "wind_dir", "pressure", "cloud")}
    data |= {"no2": 30.0, "co": 500.0, "temp": 10 + rng.normal(0, 3, len(index)),
             "wind": rng.uniform(0, 8, len(index)), "precip": 0.0}
    data["pm2_5"] = np.exp(3 + 0.4 * np.sin(2 * np.pi * hours / 24) + rng.normal(0, 0.05, len(index)))
    return pd.DataFrame(data, index=index)


def quantiles() -> dict:
    keys = (*live.factories(None), DEFAULT)
    return {k: {"0.8": [[-0.2] * 72, [0.2] * 72], "0.95": [[-0.4] * 72, [0.4] * 72]} for k in keys}


def weather_zero(origin, horizon, variables):
    return np.zeros((horizon, len(variables)))


def test_all_models_forecast_72_hours_with_ordered_intervals():
    data = frame()
    rows, timings, errors, parts = live.forecasts(data, weather_zero, quantiles(), DEFAULT)
    assert errors == {}
    assert set(rows["model"]) == {*live.factories(None), DEFAULT} and len(rows) == 7 * 72
    assert (rows["issued_at"] == data.index[-1]).all()
    assert rows["time"].min() == data.index[-1] + pd.Timedelta(hours=1)
    assert ((rows["lo95"] <= rows["lo80"]) & (rows["lo80"] <= rows["pred"]) & (rows["pred"] <= rows["hi80"])
            & (rows["hi80"] <= rows["hi95"])).all()
    assert set(timings) == set(live.factories(None))
    # части Prophet в сумме дают его прогноз (ln PM2.5)
    prophet = rows[rows["model"] == "prophet"].set_index("time")["pred"]
    assert len(parts) == 72 and (parts["issued_at"] == data.index[-1]).all()
    assert np.allclose(np.exp(parts[["trend", "daily", "yearly"]].sum(axis=1).to_numpy()), prophet.to_numpy())


def test_default_is_geometric_mean_of_its_parts():
    rows, _, _, _ = live.forecasts(frame(), weather_zero, quantiles(), DEFAULT)
    pred = rows.pivot(index="time", columns="model", values="pred")
    blend = np.exp(np.log(pred[["arima", "lstm", "lstm_weather"]]).mean(axis=1))
    assert np.allclose(pred[DEFAULT], blend)


def test_failed_model_does_not_stop_others():
    def no_weather(origin, horizon, variables):
        raise ValueError("нет прогноза погоды")

    rows, _, errors, _ = live.forecasts(frame(), no_weather, quantiles(), DEFAULT)
    assert set(errors) == {"lstm_weather"} and "нет прогноза погоды" in errors["lstm_weather"]
    assert DEFAULT not in set(rows["model"]) and "arima" in set(rows["model"])  # смесь без части не строится


def test_live_artifacts_exist():
    for variant in ("lstm", "lstm_weather"):
        assert (lstm.ARTIFACTS / "live" / f"{variant}.onnx").exists()
