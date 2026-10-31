"""Лёгкие модели живого прогноза (миллисекунды на расчёт, без подгонки): сезонно-наивная, средний профиль за
неделю, LSTM и LSTM с прогнозом погоды (ONNX). Общие для ежечасной задачи (live.py) и API: кнопка
«Пересчитать сейчас» на сайте пересчитывает их на сервере от того же последнего часа ряда. Здесь же – чтение
ряда и прогноза погоды из базы (одинаково для обоих).
"""
import numpy as np
import pandas as pd

import baselines
import lstm
import prep

HORIZON = 72
WEATHER_SQL = ", ".join(lstm.WEATHER)


# future_weather(origin, horizon, variables) – прогноз погоды на часы после origin (weather_provider)
def factories(frame: pd.DataFrame | None, future_weather) -> dict:
    return {
        "seasonal_24": lambda: baselines.SeasonalNaive(24, "seasonal_24", "сезонно-наивная, сутки"),
        "profile_7d": lambda: baselines.DailyProfile(7),
        "lstm": lambda: lstm.LstmModel("lstm", mode="live"),
        "lstm_weather": lambda: lstm.LstmModel("lstm_weather", mode="live", frame=frame, future_weather=future_weather),
    }


# ряд из базы в местном времени, очищенный от сбоя CAMS; days – только последние days суток (моделям нужна неделя)
def read_frame(conn, days: int | None = None) -> pd.DataFrame:
    recent = "where time > (select max(time) from series) - make_interval(days => %s::int)" if days else ""
    with conn.cursor() as cur:
        cur.execute(f"select * from series {recent} order by time", (days,) if days else ())
        columns = [c.name for c in cur.description]
        frame = pd.DataFrame(cur.fetchall(), columns=columns)
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    frame = frame.set_index("time").astype(float)
    frame.index = frame.index.tz_convert(prep.TZ)
    return prep.clean(frame)


# прогноз погоды на часы после origin: для каждого часа – самый свежий из сохранённых снимков (все они
# выпущены до момента расчёта); снимки пишутся только при изменении, поэтому берётся последний, где час есть
def weather_provider(conn, origin: pd.Timestamp):
    with conn.cursor() as cur:
        cur.execute(f"select distinct on (time) time, {WEATHER_SQL} from weather_forecasts "
                    "where time > %s and time <= %s order by time, issued_at desc",
                    (origin.to_pydatetime(), (origin + pd.Timedelta(hours=HORIZON)).to_pydatetime()))
        rows = cur.fetchall()
    table = pd.DataFrame(rows, columns=["time", *lstm.WEATHER])
    table["time"] = pd.to_datetime(table["time"], utc=True)
    table = table.set_index("time").astype(float)

    def provider(at: pd.Timestamp, horizon: int, variables: tuple[str, ...]) -> np.ndarray:
        times = pd.date_range(at + pd.Timedelta(hours=1), periods=horizon, freq="h").tz_convert("UTC")
        part = table.reindex(times)
        if part[list(variables)].isna().any().any():
            raise ValueError(f"нет прогноза погоды на часы {times[0]} … {times[-1]}")
        return np.column_stack([lstm.weather.transform(v, part[v].to_numpy()) for v in variables])

    return provider
