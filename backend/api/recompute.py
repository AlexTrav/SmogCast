"""Кнопка «Пересчитать сейчас»: сервер заново считает лёгкие модели (model/light.py: LSTM и LSTM с погодой
через ONNX, сезонно-наивная, профиль за неделю) от того же последнего часа ряда, что и ежечасная задача, и
показывает, сколько это заняло. ARIMA и Prophet здесь не считаются (на бесплатном Render – десятые доли ядра),
в смесь по умолчанию ARIMA берётся из ежечасного расчёта. В базу ничего не пишется – роль API только читает.

Защита от перегрузки: с одного адреса не чаще раза в LIMIT_S секунд, одновременно идёт только один пересчёт,
а результат за час ряда запоминается – повторные нажатия получают готовый ответ (новый час – новый расчёт).
"""
import math
import threading
import time
from datetime import datetime, timezone

import numpy as np
from fastapi import APIRouter, HTTPException, Request

from . import db
from .common import DEFAULT_MODEL, iso, r1

LIMIT_S = 30
WINDOW_DAYS = 21  # моделям нужна неделя истории; запас – на очистку сбоя CAMS по соседним часам
MAX_CLIENTS = 10_000

router = APIRouter()
_lock = threading.Lock()
_last: dict[str, float] = {}  # адрес -> время последнего нажатия (time.monotonic)
_result: dict | None = None  # последний пересчёт (за последний час ряда)


def reset() -> None:
    global _result
    _last.clear()
    _result = None


# не чаще раза в LIMIT_S секунд с адреса; адрес – из X-Forwarded-For прокси Render (uvicorn --proxy-headers)
def _throttle(address: str) -> None:
    now = time.monotonic()
    wait = LIMIT_S - (now - _last.get(address, -math.inf))
    if wait > 0:
        raise HTTPException(429, {"error": "too_often", "retry_after": math.ceil(wait)},
                            headers={"Retry-After": str(math.ceil(wait))})
    if len(_last) >= MAX_CLIENTS:  # старые адреса больше не нужны – словарь не растёт без предела
        for key in [k for k, at in _last.items() if now - at >= LIMIT_S]:
            del _last[key]
    _last[address] = now


@router.post("/api/recompute")
def recompute(request: Request) -> dict:
    """Пересчитать лёгкие модели от последнего часа ряда: время каждой модели в мс и прогноз на 72 ч;
    diff – наибольшее расхождение с ежечасным расчётом того же часа (мкг/м³). Не чаще раза в 30 с с адреса
    (иначе 429 и Retry-After); повторное нажатие в тот же час получает готовый ответ (cached: true)."""
    global _result
    _throttle(request.client.host if request.client else "unknown")
    if not _lock.acquire(blocking=False):
        raise HTTPException(429, {"error": "busy", "retry_after": 5}, headers={"Retry-After": "5"})
    try:
        last = db.fetch_one("select max(time) from series")[0]
        if last is None:
            raise HTTPException(503, "ряд пуст")
        if _result is None or _result["issued_at"] != iso(last):
            _result = compute()
            return {**_result, "cached": False}
        return {**_result, "cached": True}
    finally:
        _lock.release()


def compute() -> dict:
    import light  # pandas и onnxruntime – только при первом пересчёте, чтобы сервер быстрее просыпался

    began = time.perf_counter()
    with db.pool.connection() as conn:
        frame = light.read_frame(conn, WINDOW_DAYS)
        origin = frame.index[-1]
        provider = light.weather_provider(conn, origin)
        stored: dict[str, list[float]] = {}
        for model, pred in conn.execute("select model, pred from model_forecasts where issued_at = %s "
                                        "order by model, time", (origin.to_pydatetime(),)).fetchall():
            stored.setdefault(model, []).append(pred)
    series = np.log(frame["pm2_5"])
    predictions, models = {}, []
    for key, factory in light.factories(frame, provider).items():
        started = time.perf_counter()
        try:
            model = factory()
            model.fit(series)
            predictions[key] = np.exp(np.asarray(model.predict(series, light.HORIZON), dtype=float))
            error = None
        except Exception as failure:  # noqa: BLE001 – сбой одной модели (нет прогноза погоды) не мешает остальным
            error = str(failure)[:300]
        models.append({"model": key, "ms": round((time.perf_counter() - started) * 1000, 1), "error": error})
    # смесь по умолчанию (ключ – части через «+»): средняя в логарифмах; части, которые здесь не считаются,
    # – из ежечасного расчёта того же часа
    parts = DEFAULT_MODEL.split("+")
    sources = [predictions.get(p, stored.get(p)) for p in parts]
    if len(parts) > 1 and all(s is not None and len(s) == light.HORIZON for s in sources):
        predictions[DEFAULT_MODEL] = np.exp(np.mean([np.log(np.asarray(s, dtype=float)) for s in sources], axis=0))
        models.append({"model": DEFAULT_MODEL, "ms": None, "error": None})
    for entry in models:
        pred, before = predictions.get(entry["model"]), stored.get(entry["model"])
        entry["pred"] = None if pred is None else [r1(v) for v in pred]
        entry["diff"] = (None if pred is None or before is None or len(before) != len(pred)
                         else r1(np.max(np.abs(pred - np.asarray(before, dtype=float)))))
    return {
        "issued_at": iso(origin.to_pydatetime()),
        "computed_at": iso(datetime.now(timezone.utc)),
        "total_ms": round((time.perf_counter() - began) * 1000, 1),
        "models": models,
        "reused": [p for p in parts if p not in light.factories(None, None)],
        "skipped": ["arima", "prophet"],
    }
