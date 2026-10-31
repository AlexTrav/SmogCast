"""Общее для всех точек API: кэш ответов по версии данных с ETag, формат времени и чисел, замеры скорости."""
import hashlib
import json
import os
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Request, Response

from . import db

REPORTS = Path(os.environ.get("REPORTS", Path(__file__).resolve().parents[2] / "model" / "reports"))
DEFAULT_MODEL = json.loads((REPORTS / "final" / "selection.json").read_text(encoding="utf-8"))["default"]
TZ = "Asia/Almaty"
CACHE_LIMIT = 128


def iso(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def r1(value) -> float | None:
    return None if value is None else round(float(value), 1)


def _encode(payload) -> tuple[bytes, str]:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    return body, f'"{hashlib.sha1(body).hexdigest()[:20]}"'


def _respond(request: Request, body: bytes, etag: str) -> Response:
    headers = {"ETag": etag, "Cache-Control": "no-cache"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(body, media_type="application/json", headers=headers)


# ---------- кэш ответов по версии данных ----------
_cache: dict[str, tuple] = {}  # ключ запроса -> (версия данных, данные, тело, ETag)


def _entry(key: str, build) -> tuple:
    current = db.version()
    entry = _cache.get(key)
    if entry is None or entry[0] != current:
        payload = build()
        entry = (current, payload, *_encode(payload))
        if len(_cache) >= CACHE_LIMIT:
            _cache.clear()
        _cache[key] = entry
    return entry


# данные, посчитанные один раз на версию данных
def memo(key: str, build):
    return _entry(key, build)[1]


# ответ JSON с ETag: пока данные те же, на If-None-Match – пустой 304
def cached(request: Request, key: str, build) -> Response:
    entry = _entry(key, build)
    return _respond(request, entry[2], entry[3])


# ответ, который не зависит от базы (отчёты моделей): считается один раз за время жизни сервера
_static: dict[str, tuple[bytes, str]] = {}


def static(request: Request, key: str, build) -> Response:
    if key not in _static:
        _static[key] = _encode(build())
    return _respond(request, *_static[key])


# ---------- скорость ответов API (для страницы «Производительность») ----------
STARTED = datetime.now(timezone.utc)
_timings: dict[str, deque] = {}  # путь -> последние ответы (мс, код)
TIMINGS_KEPT = 500


def record(path: str, status: int, ms: float) -> None:
    _timings.setdefault(path, deque(maxlen=TIMINGS_KEPT)).append((ms, status))


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def timing_summary() -> dict:
    out = {}
    for path, items in sorted(_timings.items()):
        ms = [m for m, _ in items]
        out[path] = {"requests": len(items), "p50_ms": round(percentile(ms, 0.5), 1),
                     "p95_ms": round(percentile(ms, 0.95), 1), "max_ms": round(max(ms), 1),
                     "not_modified": sum(s == 304 for _, s in items)}
    return out


def now_ms() -> float:
    return time.perf_counter() * 1000
