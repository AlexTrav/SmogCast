"""Помогает ли прогноз погоды предсказывать смог: ARIMA и Prophet с прогнозом погоды против тех же моделей
без неё на валидации (шаг 4в), плюс окна 180 и 365 суток для ARIMA с гармониками.

    make -C model weather   # -> reports/weather/validation.json
"""
import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import timedelta
from functools import partial
from pathlib import Path

import numpy as np

import arima
import backtest
import baselines
import prep
import prophet_model
import weather

REPORTS = Path(__file__).resolve().parent / "reports" / "weather"
WEATHER = ("temp", "wind", "precip")
ARIMA_BASE = {"order": (2, 1, 3), "seasonal": (0, 0, 0), "k": 12}
CONFIGS = {
    "arima_w90": ("arima", {**ARIMA_BASE, "window_days": 90}),
    "arima_w180": ("arima", {**ARIMA_BASE, "window_days": 180}),
    "arima_w365": ("arima", {**ARIMA_BASE, "window_days": 365}),
    "arima_temp_w90": ("arima", {**ARIMA_BASE, "window_days": 90, "weather_vars": ("temp",)}),
    "arima_temp_w180": ("arima", {**ARIMA_BASE, "window_days": 180, "weather_vars": ("temp",)}),
    "arima_weather_w90": ("arima", {**ARIMA_BASE, "window_days": 90, "weather_vars": WEATHER}),
    "arima_weather_w180": ("arima", {**ARIMA_BASE, "window_days": 180, "weather_vars": WEATHER}),
    "prophet": ("prophet", {}),
    # контроль: без погоды, но на той же истории, что и Prophet с погодой (архив прогнозов – с 08.02.2024)
    "prophet_feb2024": ("prophet", {"history_start": weather.START}),
    "prophet_weather": ("prophet", {"weather_vars": WEATHER}),
    "prophet_weather_noyear": ("prophet", {"weather_vars": WEATHER, "yearly": False}),
}
# с чем сравнивать лучшую модель с погодой: лучшая без погоды (практически) и такая же по истории (честный контроль)
PLAIN = {"arima": ("arima_w90", "arima_w180", "arima_w365"), "prophet": ("prophet",)}
CONTROL = {"arima": None, "prophet": "prophet_feb2024"}
CACHE = Path(__file__).resolve().parent / ".cache" / "weather"


def make(kind: str, config: dict):
    return arima.Arima(**config) if kind == "arima" else prophet_model.ProphetModel(**config)


def mean_mae(result: backtest.Result) -> float:
    return float(np.mean(backtest.horizon_metrics(result)["mae"]))


# прогон конфигурации с кэшем: готовые прогоны берутся из model/.cache/weather
def run_cached(key: str, make_model, series, at, pool, label: str) -> backtest.Result:
    path = CACHE / f"{key}.npz"
    if path.exists():
        return backtest.load_result(path)
    began = time.perf_counter()
    result = backtest.run_blocks(make_model, series, at, pool.map)
    backtest.save_result(result, path)
    print(f"  {label} – {time.perf_counter() - began:.0f} с", flush=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", choices=["arima", "prophet"], help="пересчитать только это семейство моделей, "
                        "остальное взять из готового отчёта")
    args = parser.parse_args()
    families = [args.only] if args.only else ["arima", "prophet"]
    selected = {k: v for k, v in CONFIGS.items() if k.split("_")[0] in families}

    series = backtest.log_series(prep.clean(prep.load()))
    start, end = backtest.PERIODS["validation"]
    at = backtest.origins(series, start, end)
    print(f"погода: {len(selected)} конфигураций × {len(backtest.refit_blocks(at))} недельных блоков, "
          f"процессов: {os.cpu_count()}", flush=True)

    results = {}
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as pool:
        for i, (key, (kind, config)) in enumerate(selected.items(), 1):
            results[key] = run_cached(key, partial(make, kind, config), series, at, pool, f"{i}/{len(selected)} {key}")
            print(f"  {key:24} MAE 1–72 = {mean_mae(results[key]):.2f}", flush=True)

        # интервалы для лучшей модели с погодой: калибровка на прогнозах до валидации, но не раньше, чем
        # у модели набирается окно истории с погодой (архив прогнозов – с 08.02.2024)
        best = {}
        for family in families:
            with_weather = [k for k, (_, c) in selected.items() if k.startswith(family) and c.get("weather_vars")]
            best[family] = min(with_weather, key=lambda k: mean_mae(results[k]))
            kind, config = CONFIGS[best[family]]
            warmup = timedelta(days=config.get("window_days", 90))
            calibration_at = backtest.origins(series, max(start - timedelta(days=365), weather.START + warmup), start)
            calibration = run_cached(f"{best[family]}_calibration", partial(make, kind, config), series,
                                     calibration_at, pool, f"калибровка {best[family]}: {len(calibration_at)} прогнозов")
            backtest.add_intervals(results[best[family]], backtest.interval_quantiles(calibration))

    reference = backtest.run(baselines.SeasonalNaive(24, "seasonal_24", "сезонно-наивная, сутки"), series, at)
    profile = backtest.run(baselines.DailyProfile(7), series, at)
    path = REPORTS / "validation.json"
    report = json.loads(path.read_text(encoding="utf-8")) if args.only and path.exists() else {}
    report["meta"] = {"period": "validation", "weather": list(WEATHER), "source": "ECMWF IFS 0,25°, Previous Runs",
                      "lead_rule": "горизонт h – прогноз, выпущенный за ceil((h+6)/24) суток до целевого часа",
                      "dm": "тест Диболда–Мариано по средней абсолютной ошибке на сутках горизонта, Ньюи–Уэст, лаг 12; "
                            "mae_diff < 0 – модель с погодой точнее"}
    for part in ("configs", "dm", "models", "mae_by_horizon"):
        report.setdefault(part, {})
    for key, result in results.items():
        report["configs"][key] = {"name": result.name, "mae_1_72": round(mean_mae(result), 4),
                                  **backtest.summary(result, reference)["buckets"]}

    def dm(a: str, b: str) -> dict:
        return {"with": a, "without": b, **{name: backtest.dm_test(results[a], results[b], bounds)
                                           for name, bounds in backtest.BUCKETS.items()}}

    for family in families:
        plain = min(PLAIN[family], key=lambda k: mean_mae(results[k]))
        report["dm"][family] = dm(best[family], plain)
        if CONTROL[family]:
            report["dm"][f"{family}_control"] = dm(best[family], CONTROL[family])
        with_weather = results[best[family]]
        report["models"][f"{family}_weather"] = {"name": with_weather.name,
                                                 **backtest.summary(with_weather, reference)}
        report["mae_by_horizon"][f"{family}_weather"] = np.round(backtest.horizon_metrics(with_weather)["mae"],
                                                                 4).tolist()
        report["mae_by_horizon"][f"{family}_plain"] = np.round(backtest.horizon_metrics(results[plain])["mae"],
                                                               4).tolist()
    report["mae_by_horizon"]["profile_7d"] = np.round(backtest.horizon_metrics(profile)["mae"], 4).tolist()
    REPORTS.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n{'конфигурация':24} {'1–72':>6} {'1–24':>6} {'25–48':>6} {'49–72':>6}")
    for key, row in report["configs"].items():
        print(f"{key:24} {row['mae_1_72']:6.2f} {row['1–24']['mae']:6.2f} {row['25–48']['mae']:6.2f} "
              f"{row['49–72']['mae']:6.2f}")
    for family, row in report["dm"].items():
        print(family, row)


if __name__ == "__main__":
    main()
