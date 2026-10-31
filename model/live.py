"""Живые прогнозы (подпункт 6б): каждый час, после обновления ряда в базе, все модели строят прогноз на 72 ч
от последнего часа ряда и пишут его в model_forecasts (Neon) вместе с интервалами 80 % и 95 %; время расчёта
каждой модели – в model_runs. Модель по умолчанию – смесь, выбранная на валидации (reports/final/selection.json).
Части прогноза Prophet (тренд, суточный и годовой ход) – в prophet_parts, для «почему такой прогноз» на сайте.

    make -C model live   # вручную; по расписанию – шаг GitHub Actions после data hourly
"""
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

import arima
import baselines
import final
import lstm
import prep
import prophet_model

REPORTS = Path(__file__).resolve().parent / "reports" / "final"
HORIZON = 72
WEATHER_SQL = ", ".join(lstm.WEATHER)


def factories(future_weather) -> dict:
    return {
        "seasonal_24": lambda: baselines.SeasonalNaive(24, "seasonal_24", final.NAMES["seasonal_24"]),
        "profile_7d": lambda: baselines.DailyProfile(7),
        "arima": lambda: arima.Arima((2, 1, 3), k=12, window_days=90),
        "prophet": lambda: prophet_model.ProphetModel(),
        "lstm": lambda: lstm.LstmModel("lstm", mode="live"),
        "lstm_weather": lambda: lstm.LstmModel("lstm_weather", mode="live", frame=FRAME, future_weather=future_weather),
    }


FRAME: pd.DataFrame | None = None  # ряд с погодой для LSTM с погодой (прошлые часы)


# прогнозы всех моделей и смеси по умолчанию от последнего часа ряда: строки для model_forecasts, время моделей,
# ошибки и части прогноза Prophet (None, если Prophet не отработал)
def forecasts(frame: pd.DataFrame, future_weather, quantiles: dict,
              default: str) -> tuple[pd.DataFrame, dict, dict, pd.DataFrame | None]:
    global FRAME
    FRAME = frame
    series = np.log(frame["pm2_5"])
    origin = series.index[-1]
    times = pd.date_range(origin + pd.Timedelta(hours=1), periods=HORIZON, freq="h")
    predictions, timings, errors, components = {}, {}, {}, None
    for key, factory in factories(future_weather).items():
        began = time.perf_counter()
        try:
            model = factory()
            model.fit(series)
            predictions[key] = np.asarray(model.predict(series, HORIZON), dtype=float)
            if key == "prophet":
                components = model.parts.rename_axis("time").reset_index().assign(issued_at=origin)
        except Exception as error:  # noqa: BLE001 – сбой одной модели не мешает остальным
            errors[key] = str(error)[:500]
        timings[key] = int((time.perf_counter() - began) * 1000)
    parts = final.BLENDS[default]
    if all(p in predictions for p in parts):
        predictions[default] = np.mean([predictions[p] for p in parts], axis=0)
    rows = []
    for key, pred in predictions.items():
        bounds = {level: (pred + np.asarray(low), pred + np.asarray(high))
                  for level, (low, high) in quantiles[key].items()}
        rows.append(pd.DataFrame({
            "issued_at": origin, "model": key, "time": times, "pred": np.exp(pred),
            "lo80": np.exp(bounds["0.8"][0]), "hi80": np.exp(bounds["0.8"][1]),
            "lo95": np.exp(bounds["0.95"][0]), "hi95": np.exp(bounds["0.95"][1]),
        }))
    return pd.concat(rows, ignore_index=True), timings, errors, components


# ---------- база ----------
def read_frame(conn) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute("select * from series order by time")
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


def write(conn, rows: pd.DataFrame) -> int:
    columns = list(rows.columns)
    values = [tuple(v.to_pydatetime() if isinstance(v, pd.Timestamp) else (v if isinstance(v, str) else float(v))
                    for v in row) for row in rows.itertuples(index=False)]
    sql = (f"insert into model_forecasts ({', '.join(columns)}) values ({', '.join(['%s'] * len(columns))}) "
           "on conflict (issued_at, model, time) do update set "
           + ", ".join(f"{c} = excluded.{c}" for c in columns[3:]))
    with conn.cursor() as cur:
        cur.executemany(sql, values)
    conn.commit()
    return len(values)


# хранится только последний прогноз Prophet: прошлый заменяется в одной транзакции
def write_parts(conn, parts: pd.DataFrame) -> int:
    columns = ["issued_at", "time", "trend", "daily", "yearly"]
    values = [(row.issued_at.to_pydatetime(), row.time.to_pydatetime(), float(row.trend), float(row.daily),
               float(row.yearly)) for row in parts[columns].itertuples(index=False)]
    with conn.cursor() as cur:
        cur.execute("delete from prophet_parts")
        cur.executemany(f"insert into prophet_parts ({', '.join(columns)}) values (%s, %s, %s, %s, %s)", values)
    conn.commit()
    return len(values)


def main() -> None:
    import psycopg

    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("нет переменной окружения DATABASE_URL")
    started = pd.Timestamp.now(tz="UTC")
    began = time.perf_counter()
    quantiles = json.loads((REPORTS / "quantiles.json").read_text(encoding="utf-8"))
    default = json.loads((REPORTS / "selection.json").read_text(encoding="utf-8"))["default"]
    with psycopg.connect(url, connect_timeout=30) as conn:
        frame = read_frame(conn)
        origin = frame.index[-1]
        rows, timings, errors, parts = forecasts(frame, weather_provider(conn, origin), quantiles, default)
        written = write(conn, rows)
        if parts is not None:
            write_parts(conn, parts)
        status = "error" if errors else "ok"
        with conn.cursor() as cur:
            cur.execute("insert into model_runs (started_at, issued_at, duration_ms, model_ms, status, error) "
                        "values (%s, %s, %s, %s, %s, %s)",
                        (started.to_pydatetime(), origin.to_pydatetime(), int((time.perf_counter() - began) * 1000),
                         json.dumps(timings), status, json.dumps(errors, ensure_ascii=False) if errors else None))
        conn.commit()
    print(f"прогноз от {origin:%d.%m.%Y %H:%M}: записано строк {written}, время моделей, мс: {timings}")
    head = rows[rows["model"] == default].head(3)
    print(head[["time", "pred", "lo80", "hi80"]].round(1).to_string(index=False))
    if errors:
        print("ошибки:", errors)
        sys.exit(1)


if __name__ == "__main__":
    main()
