"""API SmogCast: только чтение базы Neon, которую каждый час пополняет GitHub Actions (data hourly, model live).

Данные меняются раз в час, поэтому каждый ответ считается один раз на версию данных (db.version) и до
следующего обновления отдаётся из памяти; у ответа есть ETag – браузер переспрашивает с If-None-Match и,
пока данные те же, получает пустой ответ 304. Время – в UTC (ISO 8601 с Z), концентрации – мкг/м³.

    uvicorn api.main:app   # локально: make -C backend run
"""
import os
from contextlib import asynccontextmanager
from functools import cache
from datetime import date, timedelta
from typing import Literal

import psycopg
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from . import db, insight, levels, recompute, weather
from .common import DEFAULT_MODEL, TZ, cached, iso, now_ms, r1, record

SCHEDULE_MINUTE = 17  # ежечасная задача стартует в xx:17 UTC и идёт около 3 минут
FIELDS = ("pm2_5", "pm10", "no2", "co", "so2", "dust", "temp", "rh", "dew", "wind", "wind_dir", "pressure",
          "precip", "cloud")
MAX_FIELDS = 4


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.pool.open()
    yield
    db.pool.close()


app = FastAPI(title="SmogCast API", version="1.0",
              description="PM2.5 в Алматы: ряд, прогнозы моделей на 72 ч и состояние ежечасного обновления",
              lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(CORSMiddleware, allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
                   allow_methods=["GET", "POST"], expose_headers=["ETag", "Server-Timing"])
app.include_router(insight.router)
app.include_router(weather.router)
app.include_router(recompute.router)


# пути точек API (считаются при первом запросе, когда все точки уже объявлены)
@cache
def api_paths() -> frozenset[str]:
    routes = [*app.routes, *insight.router.routes, *weather.router.routes, *recompute.router.routes]
    return frozenset(p for p in (getattr(r, "path", "") for r in routes) if p.startswith("/api/"))


# время ответа каждой точки API: заголовок Server-Timing (виден в DevTools) и сводка для /api/performance;
# считаются только известные пути, чтобы случайные адреса не раздували сводку
@app.middleware("http")
async def timing(request: Request, call_next):
    began = now_ms()
    response = await call_next(request)
    ms = now_ms() - began
    response.headers["Server-Timing"] = f"app;dur={ms:.1f}"
    if request.url.path in api_paths():
        record(request.url.path, response.status_code, ms)
    return response


@app.exception_handler(psycopg.OperationalError)
def database_down(_: Request, error: psycopg.OperationalError) -> JSONResponse:
    return JSONResponse({"detail": "база недоступна"}, status_code=503)


# ---------- точки API ----------
@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """Голый адрес сервиса ведёт на документацию API."""
    return RedirectResponse("/docs")


@app.get("/api/health")
def health() -> dict:
    """Жив ли сервер; базу не трогает, чтобы проверки не будили Neon."""
    return {"status": "ok"}


@app.get("/api/status")
def status(request: Request) -> Response:
    """PM2.5 в последний час ряда, уровень US AQI, погода того же часа (температура °C, влажность %, ветер км/ч
    и откуда дует, °) и время последних ежечасных запусков."""
    return cached(request, "status", build_status)


def build_status() -> dict:
    row = db.fetch_one("select time, pm2_5, pm10, temp, rh, wind, wind_dir from series order by time desc limit 1")
    if row is None:
        raise HTTPException(503, "ряд пуст")
    last, pm2_5, pm10, temp, rh, wind, wind_dir = row
    before = db.fetch_one("select pm2_5 from series where time = %s", (last - timedelta(hours=24),))
    run = db.fetch_one("select started_at, duration_ms, status, hours_added from runs order by id desc limit 1")
    model_run = db.fetch_one("select started_at, issued_at, duration_ms, status from model_runs "
                             "order by id desc limit 1")
    return {
        "time": iso(last), "pm2_5": r1(pm2_5), "pm10": r1(pm10),
        "aqi": levels.aqi(pm2_5), "level": levels.level(pm2_5),
        "change_24h": None if before is None else r1(pm2_5 - before[0]),
        "weather": {"temp": r1(temp), "rh": r1(rh), "wind": r1(wind), "wind_dir": r1(wind_dir)},
        "data_run": None if run is None else {
            "at": iso(run[0]), "duration_ms": run[1], "status": run[2], "hours_added": run[3]},
        "model_run": None if model_run is None else {
            "at": iso(model_run[0]), "issued_at": iso(model_run[1]), "duration_ms": model_run[2],
            "status": model_run[3]},
        "default_model": DEFAULT_MODEL, "schedule_minute": SCHEDULE_MINUTE, "timezone": TZ,
    }


@app.get("/api/forecast")
def forecast(request: Request, model: str | None = None) -> Response:
    """Последний прогноз модели на 72 ч (по умолчанию – выбранная смесь) с интервалами 80 % и 95 %
    и прогноз самой CAMS на те же часы для сравнения."""
    key = model or DEFAULT_MODEL
    return cached(request, f"forecast:{key}", lambda: build_forecast(key))


def build_forecast(model: str) -> dict:
    issued = db.fetch_one("select max(issued_at) from model_forecasts")[0]
    if issued is None:
        raise HTTPException(503, "прогнозов ещё нет")
    models = [r[0] for r in db.fetch("select distinct model from model_forecasts where issued_at = %s "
                                     "order by 1", (issued,))]
    if model not in models:
        raise HTTPException(404, {"error": f"нет прогноза модели {model}", "models": models})
    rows = db.fetch("select time, pred, lo80, hi80, lo95, hi95 from model_forecasts "
                    "where issued_at = %s and model = %s order by time", (issued, model))
    # прогноз CAMS на каждый час – из самого свежего снимка, где этот час есть
    cams = dict(db.fetch("select distinct on (time) time, pm2_5 from cams_forecasts "
                         "where time between %s and %s order by time, issued_at desc", (rows[0][0], rows[-1][0])))
    columns = list(zip(*rows))
    return {
        "issued_at": iso(issued), "model": model, "default_model": DEFAULT_MODEL, "models": models,
        "start": iso(rows[0][0]), "step": "hour",
        **{name: [r1(v) for v in values] for name, values in zip(("pred", "lo80", "hi80", "lo95", "hi95"),
                                                                    columns[1:])},
        "cams": [r1(cams.get(t)) for t in columns[0]],
    }


def parse_fields(fields: str) -> list[str]:
    names = [f.strip() for f in fields.split(",") if f.strip()]
    unknown = [f for f in names if f not in FIELDS]
    if not names or unknown or len(names) > MAX_FIELDS:
        raise HTTPException(400, f"fields: от 1 до {MAX_FIELDS} из {', '.join(FIELDS)}")
    return list(dict.fromkeys(names))


@app.get("/api/history")
def history(request: Request, step: Literal["hour", "day"] = "day",
            start: date | None = Query(None, alias="from", description="первый день (местное время Алматы)"),
            end: date | None = Query(None, alias="to", description="последний день включительно"),
            fields: str = Query("pm2_5", description=f"до {MAX_FIELDS} колонок ряда через запятую")) -> Response:
    """Ряд за выбранные дни (по умолчанию – весь, с 01.09.2022): по часам или среднее и максимум за сутки.
    Значения идут подряд от start с шагом step; пропущенный час или день – null."""
    names = parse_fields(fields)
    if start and end and start > end:
        raise HTTPException(400, "from позже to")
    key = f"history:{step}:{start}:{end}:{','.join(names)}"
    return cached(request, key, lambda: build_history(step, start, end, names))


# границы выбранных дней по местному времени Алматы -> моменты UTC; без границы – весь ряд
BOUNDS = (f"coalesce(%s::date::timestamp at time zone '{TZ}', '-infinity'::timestamptz)",
          f"coalesce((%s::date + 1)::timestamp at time zone '{TZ}', 'infinity'::timestamptz)")


def build_history(step: str, start: date | None, end: date | None, names: list[str]) -> dict:
    if step == "hour":
        # greatest и least пропускают null – на пустом ряде границы должны остаться null, а не ±infinity
        rows = db.fetch(
            f"with b as (select case when count(*) > 0 then greatest(min(time), {BOUNDS[0]}) end lo, "
            f"case when count(*) > 0 then least(max(time), {BOUNDS[1]} - interval '1 hour') end hi "
            "from series) "
            f"select g.t, {', '.join(f's.{n}' for n in names)} from b "
            "cross join generate_series(b.lo, b.hi, interval '1 hour') g(t) "
            "left join series s on s.time = g.t order by g.t", (start, end))
        columns = list(zip(*rows)) or [[]] * (len(names) + 1)
        return {"start": iso(rows[0][0]) if rows else None, "step": "hour",
                "values": {n: [r1(v) for v in columns[i + 1]] for i, n in enumerate(names)}}
    aggregates = ", ".join(f"avg({n}) {n}_mean, max({n}) {n}_max" for n in names)
    rows = db.fetch(
        f"with d as (select (time at time zone '{TZ}')::date as day, count(*) as hours, {aggregates} from series "
        f"where time >= {BOUNDS[0]} and time < {BOUNDS[1]} group by 1) "
        "select g.d::date, d.* from (select min(day) as lo, max(day) as hi from d) b "
        "cross join generate_series(b.lo, b.hi, interval '1 day') g(d) "
        "left join d on d.day = g.d::date order by 1", (start, end))
    columns = list(zip(*rows)) or [[]] * (2 * len(names) + 3)
    return {"start": rows[0][0].isoformat() if rows else None, "step": "day", "timezone": TZ,
            "hours": [h or 0 for h in columns[2]],
            "values": {n: {"mean": [r1(v) for v in columns[3 + 2 * i]], "max": [r1(v) for v in columns[4 + 2 * i]]}
                       for i, n in enumerate(names)}}
