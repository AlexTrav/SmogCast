"""Насколько точны прогнозы и как работает система: журнал «прогноз -> факт» по живым прогнозам,
итоги честной проверки моделей из отчётов и скорость ежечасных запусков и самого API."""
import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request, Response

from . import db
from .common import (DEFAULT_MODEL, REPORTS, STARTED, TZ, cached, iso, memo, percentile, r1, static,
                     timing_summary)

router = APIRouter(prefix="/api")
BUCKETS = ("1–24", "25–48", "49–72")
CAMS = "cams"  # прогноз самой CAMS – как ещё одна «модель» для сравнения


@router.get("/verify")
def verify(request: Request, days: int = Query(7, ge=1, le=30, description="за сколько последних суток")) -> Response:
    """Журнал «прогноз -> факт»: средняя абсолютная ошибка (MAE, мкг/м³) живых прогнозов каждой модели
    и самой CAMS за последние дни – всего, по горизонтам 1–24, 25–48, 49–72 ч и по суткам («гонка моделей»),
    и прогноз модели по умолчанию, выпущенный сутки назад, рядом с фактом."""
    return cached(request, f"verify:{days}", lambda: build_verify(days))


# ошибки считаются по часам, где факт уже известен; прогноз CAMS берётся тот, что был известен в момент
# выпуска нашего прогноза (последний снимок с issued_at не позже), – сравнение без заглядывания в будущее
VERIFY_SQL = f"""
with last as (select max(time) as t from series),
ours as (
    select m.model, m.issued_at, m.time, m.pred
    from model_forecasts m, last
    where m.time > last.t - %(days)s * interval '1 day' and m.time <= last.t
),
cams as (
    select '{CAMS}' as model, i.issued_at, k.time, k.pm2_5 as pred
    from (select distinct issued_at from ours) i
    cross join lateral (select max(issued_at) as at from cams_forecasts where issued_at <= i.issued_at) c
    join cams_forecasts k on k.issued_at = c.at and k.time > i.issued_at
        and k.time <= i.issued_at + interval '72 hours' and k.pm2_5 is not null, last
    where k.time > last.t - %(days)s * interval '1 day' and k.time <= last.t
),
errors as (
    select a.model, extract(epoch from a.time - a.issued_at) / 3600 as h,
           (a.time at time zone '{TZ}')::date as day, abs(a.pred - s.pm2_5) as error
    from (select * from ours union all select * from cams) a join series s on s.time = a.time
)
select model, case when h <= 24 then 0 when h <= 48 then 1 else 2 end, day, sum(error), count(*)
from errors group by 1, 2, 3
"""


def build_verify(days: int) -> dict:
    rows = db.fetch(VERIFY_SQL, {"days": days})
    dates = sorted({r[2] for r in rows})
    totals: dict[str, dict] = {}
    for model, bucket, day, error, count in rows:
        t = totals.setdefault(model, {"all": [0.0, 0], "buckets": [[0.0, 0] for _ in BUCKETS], "days": {}})
        for acc in (t["all"], t["buckets"][bucket], t["days"].setdefault(day, [0.0, 0])):
            acc[0] += float(error)
            acc[1] += count

    def mae(acc) -> float | None:
        return r1(acc[0] / acc[1]) if acc[1] else None

    models = {model: {"mae": mae(t["all"]), "hours": t["all"][1],
                      "buckets": {name: mae(acc) for name, acc in zip(BUCKETS, t["buckets"])},
                      "daily": [mae(t["days"].get(d, (0, 0))) for d in dates]}
              for model, t in sorted(totals.items())}
    return {"days": days, "default_model": DEFAULT_MODEL, "dates": [d.isoformat() for d in dates],
            "models": models, "yesterday": build_yesterday()}


# прогноз модели по умолчанию, выпущенный не позже чем за сутки до последнего часа ряда, и факт на его часы
def build_yesterday() -> dict | None:
    rows = db.fetch(
        "with last as (select max(time) as t from series), "
        "issue as (select max(issued_at) as at from model_forecasts, last "
        "          where model = %s and issued_at <= last.t - interval '24 hours') "
        "select m.issued_at, m.time, m.pred, m.lo80, m.hi80, s.pm2_5 from model_forecasts m "
        "join issue on m.issued_at = issue.at left join series s on s.time = m.time "
        "where m.model = %s order by m.time", (DEFAULT_MODEL, DEFAULT_MODEL))
    if not rows:
        return None
    columns = list(zip(*rows))
    return {"issued_at": iso(rows[0][0]), "start": iso(rows[0][1]), "step": "hour",
            **{name: [r1(v) for v in columns[i]] for i, name in ((2, "pred"), (3, "lo80"), (4, "hi80"),
                                                                 (5, "actual"))}}


@router.get("/models")
def models(request: Request) -> Response:
    """Итоги честной проверки (model/reports/final): рейтинг на валидации, по которому выбрана модель
    по умолчанию, и все метрики на отложенном тестовом годе – MAE по горизонтам, интервалы, уровни AQI,
    тест Диболда–Мариано против модели по умолчанию, пример прогноза."""
    return static(request, "models", lambda: {
        "selection": json.loads((REPORTS / "final" / "selection.json").read_text(encoding="utf-8")),
        "test": json.loads((REPORTS / "final" / "test.json").read_text(encoding="utf-8")),
    })


@router.get("/performance")
def performance(hours: int = Query(48, ge=1, le=336, description="сколько последних запусков")) -> dict:
    """Производительность системы реального времени: длительность ежечасных запусков сбора данных и моделей,
    время каждой модели, отставание данных, пропущенные запуски, размер базы и скорость ответов самого API.
    Не кэшируется по ETag: сводка API меняется с каждым запросом."""
    base = memo(f"performance:{hours}", lambda: build_performance(hours))
    now = datetime.now(timezone.utc)
    return {**base, "api": {"started_at": iso(STARTED), "uptime_s": int((now - STARTED).total_seconds()),
                            "paths": timing_summary()}}


def _stats(values: list[float]) -> dict | None:
    if not values:
        return None
    return {"p50": round(percentile(values, 0.5)), "p95": round(percentile(values, 0.95)), "max": round(max(values))}


def build_performance(hours: int) -> dict:
    runs = db.fetch("select started_at, duration_ms, status, hours_added, series_last, db_mb, cleaned_rows, "
                    "cams_rows, weather_rows from runs order by id desc limit %s", (hours,))[::-1]
    model_runs = db.fetch("select started_at, issued_at, duration_ms, model_ms, status from model_runs "
                          "order by id desc limit %s", (hours,))[::-1]
    # пропущенные часы: за последние 7 суток ожидается по запуску в час
    week = db.fetch_one("select count(distinct date_trunc('hour', started_at)) from runs "
                        "where started_at > now() - interval '7 days'")[0]
    first = db.fetch_one("select min(started_at) from runs")[0]
    expected = 0 if first is None else min(168, int((datetime.now(timezone.utc) - first).total_seconds() // 3600))
    model_names = sorted({k for r in model_runs for k in (r[3] or {})})
    return {
        "data_runs": [{"at": iso(r[0]), "duration_ms": r[1], "status": r[2], "hours_added": r[3],
                       # насколько свежий час ряда был на момент запуска – задержка самого источника (CAMS)
                       "lag_min": None if r[4] is None else round((r[0] - r[4]).total_seconds() / 60),
                       "db_mb": r1(r[5]), "cleaned_rows": r[6], "snapshot_rows": (r[7] or 0) + (r[8] or 0)}
                      for r in runs],
        "model_runs": [{"at": iso(r[0]), "issued_at": iso(r[1]), "duration_ms": r[2], "model_ms": r[3] or {},
                        "status": r[4]} for r in model_runs],
        "summary": {
            "data_ms": _stats([r[1] for r in runs]),
            "models_ms": _stats([r[2] for r in model_runs]),
            "model_ms": {m: _stats([r[3][m] for r in model_runs if r[3] and m in r[3]]) for m in model_names},
            "success": r1(100 * sum(r[2] == "ok" for r in runs) / len(runs)) if runs else None,
            "hours_with_run_7d": week, "hours_expected_7d": expected,
            "db_mb": r1(runs[-1][5]) if runs else None,
        },
    }


@router.get("/explain")
def explain(request: Request) -> Response:
    """«Почему такой прогноз»: последний прогноз Prophet, разложенный на множители – уровень (тренд, мкг/м³),
    суточный и годовой ход (во сколько раз они поднимают или опускают уровень); из каких моделей сложена
    смесь по умолчанию; во сколько раз прогноз погоды сдвигает LSTM (LSTM с погодой / LSTM без неё)."""
    return cached(request, "explain", build_explain)


def _ratio(a: list, b: list) -> list:
    return [None if x is None or not y else round(x / y, 3) for x, y in zip(a, b)]


def build_explain() -> dict:
    issued = db.fetch_one("select max(issued_at) from model_forecasts")[0]
    if issued is None:
        raise HTTPException(503, "прогнозов ещё нет")
    rows = db.fetch("select model, time, pred from model_forecasts where issued_at = %s order by model, time",
                    (issued,))
    preds: dict[str, list] = {}
    for model, _, pred in rows:
        preds.setdefault(model, []).append(pred)
    start = min(r[1] for r in rows)
    parts = db.fetch(f"select time, (time at time zone '{TZ}')::time, exp(trend), exp(daily), exp(yearly) "
                     "from prophet_parts where issued_at = %s order by time", (issued,))
    prophet = None
    if parts:
        columns = list(zip(*parts))
        daily = list(zip(columns[1], columns[3]))[:24]  # сутки суточного хода: (местное время, множитель)
        low, high = min(daily, key=lambda d: d[1]), max(daily, key=lambda d: d[1])
        prophet = {
            "level": [r1(v) for v in columns[2]],
            "daily": [round(v, 3) for v in columns[3]], "yearly": [round(v, 3) for v in columns[4]],
            "summary": {"level": r1(sum(columns[2]) / len(parts)),
                        "yearly": round(sum(columns[4]) / len(parts), 3),
                        "daily_low": {"hour": low[0].hour, "factor": round(low[1], 3)},
                        "daily_high": {"hour": high[0].hour, "factor": round(high[1], 3)}},
        }
    names = DEFAULT_MODEL.split("+")
    weather = None
    if "lstm" in preds and "lstm_weather" in preds:
        ratio = _ratio(preds["lstm_weather"], preds["lstm"])
        weather = {"ratio": ratio, "mean_24h": round(sum(ratio[:24]) / 24, 3)}
    return {
        "issued_at": iso(issued), "start": iso(start), "step": "hour",
        "prophet": prophet,
        "blend": {"model": DEFAULT_MODEL, "pred": [r1(v) for v in preds.get(DEFAULT_MODEL, [])],
                  "parts": {n: [r1(v) for v in preds[n]] for n in names if n in preds}},
        "weather": weather,
    }
