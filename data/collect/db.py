"""Postgres (Neon): живой ряд, снимки прогнозов CAMS и погоды, журнал ежечасных запусков."""
from datetime import timedelta

import numpy as np
import pandas as pd
import psycopg

from .config import COLUMNS, WEATHER_VARS

CAMS_COLUMNS = ["pm2_5", "pm10"]
WEATHER_COLUMNS = list(WEATHER_VARS.values())
SNAPSHOT_TABLES = {"cams_forecasts": CAMS_COLUMNS, "weather_forecasts": WEATHER_COLUMNS}
# таблицы, которые можно чистить по размеру базы (ряд и журналы не чистятся никогда)
CLEAN_TABLES = (*SNAPSHOT_TABLES, "model_forecasts")
REGION_COLUMNS = ["pm2_5", "pm10", "wind", "wind_dir"]

SCHEMA = f"""
create table if not exists series (
    time timestamptz primary key,
    {", ".join(f"{c} double precision not null" for c in COLUMNS[1:])}
);
-- снимок прогноза: что CAMS обещал в момент issued_at (начало часа, UTC) на час time; снимок пишется,
-- только когда прогноз изменился, поэтому прогноз, известный в момент t, – последний снимок с issued_at <= t
create table if not exists cams_forecasts (
    issued_at timestamptz not null,
    time timestamptz not null,
    {", ".join(f"{c} double precision" for c in CAMS_COLUMNS)},
    primary key (issued_at, time)
);
create table if not exists weather_forecasts (
    issued_at timestamptz not null,
    time timestamptz not null,
    {", ".join(f"{c} double precision" for c in WEATHER_COLUMNS)},
    primary key (issued_at, time)
);
-- журнал запусков для страницы «Производительность»: длительность, свежесть ряда, ошибки
create table if not exists runs (
    id bigserial primary key,
    started_at timestamptz not null,
    duration_ms integer not null,
    series_last timestamptz,
    hours_added integer,
    cams_rows integer,
    weather_rows integer,
    status text not null,
    error text
);
alter table runs add column if not exists db_mb double precision;
alter table runs add column if not exists cleaned_rows integer;
alter table runs add column if not exists region_rows integer;
-- сетка CAMS вокруг Алматы для карты на сайте: только последний снимок (сутки назад и 3 суток вперёд)
create table if not exists region (
    lat double precision not null,
    lon double precision not null,
    time timestamptz not null,
    issued_at timestamptz not null,
    {", ".join(f"{c} double precision" for c in REGION_COLUMNS)},
    primary key (lat, lon, time)
);
-- прогнозы наших моделей (пишет model/live.py): issued_at – последний час ряда, от которого строился прогноз;
-- pred и границы интервалов 80 % и 95 % – в мкг/м³; по ним сайт строит журнал «прогноз -> факт»
create table if not exists model_forecasts (
    issued_at timestamptz not null,
    model text not null,
    time timestamptz not null,
    pred double precision not null,
    lo80 double precision,
    hi80 double precision,
    lo95 double precision,
    hi95 double precision,
    primary key (issued_at, model, time)
);
-- «почему такой прогноз»: части последнего прогноза Prophet (ln PM2.5) – тренд, суточный и годовой ход;
-- хранится только последний прогноз (пишет model/live.py)
create table if not exists prophet_parts (
    issued_at timestamptz not null,
    time timestamptz not null,
    trend double precision not null,
    daily double precision not null,
    yearly double precision not null,
    primary key (issued_at, time)
);
-- журнал расчёта прогнозов: время каждой модели (мс) – для страницы «Производительность»
create table if not exists model_runs (
    id bigserial primary key,
    started_at timestamptz not null,
    issued_at timestamptz,
    duration_ms integer not null,
    model_ms jsonb,
    status text not null,
    error text
);
"""


def connect(url: str) -> psycopg.Connection:
    return psycopg.connect(url, connect_timeout=30)


def init_schema(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(SCHEMA)
    conn.commit()


# insert … on conflict do update: повторная запись тех же часов обновляет значения, а не дублирует строки
def _upsert(conn: psycopg.Connection, table: str, key: list[str], frame: pd.DataFrame) -> int:
    if frame.empty:
        return 0
    columns = list(frame.columns)
    values = [c for c in columns if c not in key]
    sql = (f"insert into {table} ({', '.join(columns)}) values ({', '.join(['%s'] * len(columns))}) "
           f"on conflict ({', '.join(key)}) do update set {', '.join(f'{c} = excluded.{c}' for c in values)}")
    rows = [tuple(None if pd.isna(v) else (v.to_pydatetime() if isinstance(v, pd.Timestamp) else float(v))
                  for v in row) for row in frame.itertuples(index=False)]
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
    conn.commit()
    return len(rows)


def upsert_series(conn: psycopg.Connection, frame: pd.DataFrame) -> int:
    return _upsert(conn, "series", ["time"], frame[COLUMNS])


# последний сохранённый снимок прогноза (без issued_at); пустая таблица – пустой кадр
def latest_forecast(conn: psycopg.Connection, table: str) -> pd.DataFrame:
    columns = ["time", *SNAPSHOT_TABLES[table]]
    with conn.cursor() as cur:
        cur.execute(f"select {', '.join(columns)} from {table} "
                    f"where issued_at = (select max(issued_at) from {table}) order by time")
        frame = pd.DataFrame(cur.fetchall(), columns=columns)
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    return frame.astype({c: "float64" for c in columns[1:]})


# прогноз не изменился, если каждый его час уже есть в прошлом снимке с теми же значениями:
# модель ещё не пересчитана, а новый снимок лишь «сдвинулся» на час вперёд
def unchanged(previous: pd.DataFrame, current: pd.DataFrame, columns: list[str]) -> bool:
    if previous.empty or current.empty:
        return False
    merged = current.merge(previous, on="time", how="left", suffixes=("", "_prev"), indicator=True)
    if (merged["_merge"] != "both").any():
        return False
    return all(np.allclose(merged[c].astype(float), merged[f"{c}_prev"].astype(float), equal_nan=True)
               for c in columns)


# снимок сохраняется, только если прогноз изменился: CAMS пересчитывается 2 раза в сутки, IFS – до 4,
# и большинство часовых снимков повторяли бы предыдущий; возвращает число записанных строк
def save_forecast(conn: psycopg.Connection, table: str, issued_at: pd.Timestamp, frame: pd.DataFrame) -> int:
    columns = SNAPSHOT_TABLES[table]
    rows = frame[["time", *columns]].reset_index(drop=True)
    if unchanged(latest_forecast(conn, table), rows, columns):
        return 0
    rows.insert(0, "issued_at", issued_at)
    return _upsert(conn, table, ["issued_at", "time"], rows)


# сетка для карты: прошлый снимок заменяется новым в одной транзакции – таблица не растёт
def replace_region(conn: psycopg.Connection, frame: pd.DataFrame) -> int:
    columns = ["lat", "lon", "time", "issued_at", *REGION_COLUMNS]
    rows = [tuple(None if pd.isna(v) else (v.to_pydatetime() if isinstance(v, pd.Timestamp) else float(v))
                  for v in row) for row in frame[columns].itertuples(index=False)]
    with conn.cursor() as cur:
        cur.execute("delete from region")
        cur.executemany(f"insert into region ({', '.join(columns)}) values ({', '.join(['%s'] * len(columns))})",
                        rows)
    conn.commit()
    return len(rows)


def db_size_mb(conn: psycopg.Connection) -> float:
    with conn.cursor() as cur:
        cur.execute("select pg_database_size(current_database())")
        return cur.fetchone()[0] / 2**20


# очистка по размеру: если база больше limit_mb, удаляются самые старые снимки прогнозов (CAMS, погоды и наших
# моделей), пока оценка размера не опустится до 80 % порога (запас, чтобы очистка не срабатывала каждый час);
# снимки моложе keep_days не удаляются никогда; возвращает число удалённых строк
def cleanup(conn: psycopg.Connection, now: pd.Timestamp, limit_mb: float, keep_days: int) -> int:
    size = db_size_mb(conn)
    if size <= limit_mb:
        return 0
    need = (size - 0.8 * limit_mb) * 2**20
    protect = (now - timedelta(days=keep_days)).to_pydatetime()
    weight: dict = {}  # issued_at -> оценка байт, которые освободит удаление этого снимка во всех таблицах
    with conn.cursor() as cur:
        for table in CLEAN_TABLES:
            cur.execute(f"select pg_total_relation_size('{table}'), count(*) from {table}")
            total, rows = cur.fetchone()
            if not rows:
                continue
            cur.execute(f"select issued_at, count(*) from {table} where issued_at < %s group by 1", (protect,))
            for issued_at, count in cur.fetchall():
                weight[issued_at] = weight.get(issued_at, 0) + count * total / rows
    cutoff, freed = None, 0.0
    for issued_at in sorted(weight):
        cutoff, freed = issued_at, freed + weight[issued_at]
        if freed >= need:
            break
    if cutoff is None:
        return 0
    deleted = 0
    with conn.cursor() as cur:
        for table in CLEAN_TABLES:
            cur.execute(f"delete from {table} where issued_at <= %s", (cutoff,))
            deleted += cur.rowcount
    conn.commit()
    # delete только помечает место свободным – сжимаем таблицы, чтобы размер базы действительно уменьшился
    # (vacuum нельзя выполнять внутри транзакции)
    conn.autocommit = True
    try:
        for table in CLEAN_TABLES:
            conn.execute(f"vacuum full {table}")
    finally:
        conn.autocommit = False
    return deleted


def last_time(conn: psycopg.Connection) -> pd.Timestamp | None:
    with conn.cursor() as cur:
        cur.execute("select max(time) from series")
        value = cur.fetchone()[0]
    return None if value is None else pd.Timestamp(value).tz_convert("UTC")


def read_series(conn: psycopg.Connection, since: pd.Timestamp | None = None) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(f"select {', '.join(COLUMNS)} from series where %s::timestamptz is null or time >= %s "
                    "order by time", (since, since))
        frame = pd.DataFrame(cur.fetchall(), columns=COLUMNS)
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    return frame.astype({c: "float64" for c in COLUMNS[1:]})


def log_run(conn: psycopg.Connection, **fields) -> None:
    with conn.cursor() as cur:
        cur.execute(f"insert into runs ({', '.join(fields)}) values ({', '.join(['%s'] * len(fields))})",
                    list(fields.values()))
    conn.commit()


# сколько строк в каждой таблице – для сводки в консоли
def counts(conn: psycopg.Connection) -> dict[str, int]:
    out = {}
    with conn.cursor() as cur:
        for table in ["series", "cams_forecasts", "weather_forecasts", "runs", "region", "model_forecasts",
                      "model_runs", "prophet_parts"]:
            cur.execute(f"select count(*) from {table}")
            out[table] = cur.fetchone()[0]
    return out
