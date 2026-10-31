"""Postgres (Neon): живой ряд, снимки прогнозов CAMS и погоды, журнал ежечасных запусков."""
import pandas as pd
import psycopg

from .config import COLUMNS, WEATHER_VARS

CAMS_COLUMNS = ["pm2_5", "pm10"]
WEATHER_COLUMNS = list(WEATHER_VARS.values())

SCHEMA = f"""
create table if not exists series (
    time timestamptz primary key,
    {", ".join(f"{c} double precision not null" for c in COLUMNS[1:])}
);
-- снимок прогноза: что CAMS обещал в момент issued_at (начало часа, UTC) на час time
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


def save_forecast(conn: psycopg.Connection, table: str, issued_at: pd.Timestamp, frame: pd.DataFrame) -> int:
    columns = CAMS_COLUMNS if table == "cams_forecasts" else WEATHER_COLUMNS
    rows = frame[["time", *columns]].copy()
    rows.insert(0, "issued_at", issued_at)
    return _upsert(conn, table, ["issued_at", "time"], rows)


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
        for table in ["series", "cams_forecasts", "weather_forecasts", "runs"]:
            cur.execute(f"select count(*) from {table}")
            out[table] = cur.fetchone()[0]
    return out
