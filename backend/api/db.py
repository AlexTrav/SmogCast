"""Подключение к базе: небольшой пул без постоянных соединений – через минуту простоя они закрываются,
и бесплатная база Neon может уснуть, пока сайт никто не открывает."""
import os
import threading
import time

from psycopg_pool import ConnectionPool

# через сколько секунд заново спрашивать базу, не появились ли новые данные
VERSION_TTL = float(os.environ.get("VERSION_TTL", 30))

pool = ConnectionPool(os.environ.get("DATABASE_URL", ""), min_size=0, max_size=4, max_idle=60, open=False,
                      kwargs={"connect_timeout": 30}, check=ConnectionPool.check_connection)


def fetch(sql: str, params: tuple = ()) -> list[tuple]:
    with pool.connection() as conn:
        return conn.execute(sql, params).fetchall()


def fetch_one(sql: str, params: tuple = ()) -> tuple | None:
    rows = fetch(sql, params)
    return rows[0] if rows else None


# версия данных: последний час ряда и номера последних ежечасных запусков; меняется раз в час,
# по ней сбрасывается кэш ответов; базу спрашиваем не чаще VERSION_TTL секунд
_version: tuple[float, str] = (0.0, "")
_lock = threading.Lock()


def version() -> str:
    global _version
    with _lock:
        if time.monotonic() < _version[0]:
            return _version[1]
        row = fetch_one("select (select max(time) from series), (select max(id) from runs), "
                        "(select max(id) from model_runs)")
        value = "|".join(str(v) for v in row)
        _version = (time.monotonic() + VERSION_TTL, value)
        return value


def reset_version() -> None:
    global _version
    with _lock:
        _version = (0.0, "")
