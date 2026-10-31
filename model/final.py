"""Итоговое сравнение (шаг 6). Модель по умолчанию (одна модель или смесь) выбирается на валидации и фиксируется
в reports/final/selection.json ДО теста; затем все модели один раз проходят отложенный тестовый год.

    make -C model select   # валидация: все модели и смеси -> reports/final/selection.json
    make -C model final    # тест (только после select): все модели -> reports/final/test.json
"""
import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd

import aqi
import arima
import backtest
import baselines
import lstm
import prep
import prophet_model

REPORTS = Path(__file__).resolve().parent / "reports" / "final"
CACHE = Path(__file__).resolve().parent / ".cache" / "final"
LEVELS = (0.8, 0.95)

# модели, выбранные на шагах 3–5 (параметры на тесте не меняются)
NAMES = {
    "persistence": "последнее значение",
    "seasonal_24": "сезонно-наивная, сутки",
    "profile_7d": "средний профиль за 7 дней",
    "arima": "ARIMA(2,1,3) + 12 гармоник суток, окно 90 дн.",
    "prophet": "Prophet, вся история",
    "lstm": "LSTM",
    "lstm_weather": "LSTM + прогноз погоды",
}
SHORT = {"arima": "ARIMA", "prophet": "Prophet", "lstm": "LSTM", "lstm_weather": "LSTM + погода"}
# смеси – среднее прогнозов в логарифмах (то есть среднее геометрическое в мкг/м³)
BLENDS = {
    "arima+lstm_weather": ("arima", "lstm_weather"),
    "arima+prophet": ("arima", "prophet"),
    "arima+lstm_weather+prophet": ("arima", "lstm_weather", "prophet"),
    "arima+lstm+lstm_weather": ("arima", "lstm", "lstm_weather"),
}
HEAVY = ("arima", "prophet")  # считаются недельными блоками параллельно
EXAMPLE_ORIGIN = {"validation": "2025-01-15 18:00", "test": "2026-01-15 18:00"}


def make(key: str):
    if key == "arima":
        return arima.Arima((2, 1, 3), k=12, window_days=90)
    return prophet_model.ProphetModel()


def light(key: str, period: str):
    if key == "persistence":
        return baselines.Persistence()
    if key == "seasonal_24":
        return baselines.SeasonalNaive(24, "seasonal_24", NAMES[key])
    if key == "profile_7d":
        return baselines.DailyProfile(7)
    return lstm.LstmModel(key, mode=period)  # LSTM, обученная до начала проверяемой части


def blend(name: str, parts: list[backtest.Result]) -> backtest.Result:
    return backtest.Result(name, parts[0].origins, np.mean([p.pred for p in parts], axis=0), parts[0].actual)


def mean_mae(result: backtest.Result) -> float:
    return float(np.mean(backtest.horizon_metrics(result)["mae"]))


# все модели и смеси на части period (прогоны – с кэшем: повторный запуск не пересчитывает)
def run_all(period: str, series: pd.Series) -> dict[str, backtest.Result]:
    start, end = backtest.PERIODS[period]
    at = backtest.origins(series, start, end)
    print(f"{period}: {len(at)} прогнозов на 72 ч", flush=True)
    results = {}
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as pool:
        for key in NAMES:
            path = CACHE / f"{period}_{key}.npz"
            if path.exists():
                results[key] = backtest.load_result(path)
                continue
            began = time.perf_counter()
            if key in HEAVY:
                results[key] = backtest.run_blocks(partial(make, key), series, at, pool.map)
            else:
                results[key] = backtest.run(light(key, period), series, at)
            results[key].name = NAMES[key]
            backtest.save_result(results[key], path)
            print(f"  {key:14} MAE 1–72 = {mean_mae(results[key]):.2f}, {time.perf_counter() - began:.0f} с", flush=True)
    for name, parts in BLENDS.items():
        results[name] = blend("смесь: " + ", ".join(SHORT[p] for p in parts), [results[p] for p in parts])
    return results


def select(series: pd.Series) -> dict:
    results = run_all("validation", series)
    candidates = [k for k in results if k not in ("persistence", "seasonal_24", "profile_7d")]
    ranking = sorted(candidates, key=lambda k: mean_mae(results[k]))
    reference = results["seasonal_24"]
    return {
        "default": ranking[0],
        "rule": "модель по умолчанию – наименьшая средняя MAE на горизонтах 1–72 ч на валидации; "
                "выбрано до запуска теста, на тесте не меняется",
        "chosen_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "ranking": [{"key": k, "name": results[k].name, "mae_1_72": round(mean_mae(results[k]), 4),
                     **{b: v["mae"] for b, v in backtest.summary(results[k], reference)["buckets"].items()}}
                    for k in ranking + ["profile_7d", "seasonal_24", "persistence"]],
    }


def final(series: pd.Series, selection: dict) -> dict:
    validation = run_all("validation", series)  # из кэша – для калибровки интервалов
    results = run_all("test", series)
    reference = results["seasonal_24"]
    default = selection["default"]
    report = {"meta": {"period": "test", "start": backtest.PERIODS["test"][0].isoformat(),
                       "default": default, "selection_chosen_at": selection["chosen_at"],
                       "intervals": "эмпирические квантили ошибок той же модели на валидации (для неё – новые данные)",
                       "aqi": {"breaks": list(aqi.BREAKS), "levels": list(aqi.LEVELS), "smog": aqi.SMOG}},
              "models": {}, "dm_vs_default": {}, "aqi": {}, "mae_by_horizon": {}}
    for key, result in results.items():
        backtest.add_intervals(result, backtest.interval_quantiles(validation[key], LEVELS))
        report["models"][key] = {"name": result.name, "mae_1_72": round(mean_mae(result), 4),
                                 **backtest.summary(result, reference)}
        report["mae_by_horizon"][key] = np.round(backtest.horizon_metrics(result)["mae"], 4).tolist()
        y, f = np.exp(result.actual), np.exp(result.pred)
        report["aqi"][key] = {b: {k: round(v, 4) if isinstance(v, float) else v
                                  for k, v in aqi.scores(y[:, a - 1:z], f[:, a - 1:z]).items()}
                              for b, (a, z) in backtest.BUCKETS.items()}
        if key != default:
            report["dm_vs_default"][key] = {b: backtest.dm_test(results[default], result, bounds)
                                            for b, bounds in backtest.BUCKETS.items()}
    best = results[default]
    report["confusion_24h"] = aqi.confusion(np.exp(best.actual[:, 23]), np.exp(best.pred[:, 23])).tolist()
    origin = pd.Timestamp(EXAMPLE_ORIGIN["test"], tz=prep.TZ)
    i = int(np.where(best.origins == origin)[0][0])
    report["example"] = {"origin": origin.isoformat(), "name": best.name,
                         "history": np.round(np.exp(series[:origin].iloc[-48:]), 2).tolist(),
                         **{k: np.round(np.exp(v), 2).tolist() for k, v in (
                             ("pred", best.pred[i]), ("actual", best.actual[i]),
                             ("lower80", best.lower[0.8][i]), ("upper80", best.upper[0.8][i]),
                             ("lower95", best.lower[0.95][i]), ("upper95", best.upper[0.95][i]))}}
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["select", "final"])
    args = parser.parse_args()
    series = backtest.log_series(prep.clean(prep.load()))
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / "selection.json"

    if args.command == "select":
        selection = select(series)
        path.write_text(json.dumps(selection, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nмодель по умолчанию: {selection['default']}")
        for row in selection["ranking"]:
            print(f"  {row['key']:28} {row['mae_1_72']:.3f}  {row['1–24']:.2f} {row['25–48']:.2f} {row['49–72']:.2f}")
        return

    if not path.exists():
        raise SystemExit("сначала выбор на валидации: make -C model select")
    report = final(series, json.loads(path.read_text(encoding="utf-8")))
    (REPORTS / "test.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{'модель':28} {'1–72':>6} {'1–24':>6} {'25–48':>6} {'49–72':>6} {'уровень 1–24':>13} {'смог пойман':>12}")
    for key, row in sorted(report["models"].items(), key=lambda kv: kv[1]["mae_1_72"]):
        b, a = row["buckets"], report["aqi"][key]["1–24"]
        print(f"{key:28} {row['mae_1_72']:6.2f} {b['1–24']['mae']:6.2f} {b['25–48']['mae']:6.2f} {b['49–72']['mae']:6.2f} "
              f"{a['level_exact']:13.2f} {a['smog_caught']:12.2f}")


if __name__ == "__main__":
    main()
