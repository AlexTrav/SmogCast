"""ARIMA: два способа учесть суточный цикл – сезонная SARIMA с периодом 24 ч и ARIMA с гармониками суток.

    make -C model arima-orders   # подбор порядков по AIC на обучающей части -> reports/arima/orders.json
    make -C model arima          # окна 28/56/90 дней на валидации, интервалы -> reports/arima/validation.json
"""
import argparse
import json
import os
import time
import warnings
from concurrent.futures import ProcessPoolExecutor
from datetime import timedelta
from functools import partial
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX

import backtest
import baselines
import prep
import weather
from weather import NAMES as WEATHER_NAMES

REPORTS = Path(__file__).resolve().parent / "reports" / "arima"
LEVELS = (0.8, 0.95)
# прогноз в логарифмах ограничивается правдоподобным диапазоном 0,3–500 мкг/м³: модель без ограничений
# на стационарность изредка «разгоняется» на длинном горизонте
LOW, HIGH = np.log(0.3), np.log(500)
# окна подбора порядков – зима и лето обоих лет обучающей части (до валидации)
SELECTION_ENDS = ["2023-01-31", "2023-07-31", "2024-01-31", "2024-07-31"]
WINDOWS = (28, 56, 90)


# гармоники суток по местному часу: k пар синусов и косинусов с периодом 24 ч; при k = 12 синус
# sin(π·час) на целых часах всегда равен нулю – эту колонку не берём (12 гармоник = свой уровень у каждого часа)
def harmonics(index: pd.DatetimeIndex, k: int) -> np.ndarray | None:
    if not k:
        return None
    hour = np.asarray(index.hour, dtype=float)
    columns = [f(2 * np.pi * j * hour / 24) for j in range(1, k + 1) for f in (np.sin, np.cos)
               if not (f is np.sin and 2 * j == 24)]
    return np.column_stack(columns)


class Arima:
    """ARIMA(p,1,q) по ln PM2.5 на окне последних window_days суток; суточный цикл – сезонная часть
    (P,1,Q)24 или k гармоник суток. Между подгонками новые часы добавляются в фильтр без переподгонки."""

    def __init__(self, order: tuple, seasonal: tuple = (0, 0, 0), k: int = 0, window_days: int = 56,
                 weather_vars: tuple[str, ...] = ()) -> None:
        self.order, self.seasonal, self.k, self.window_days = order, seasonal, k, window_days
        self.weather_vars = tuple(weather_vars)
        p, d, q = order
        cycle = f"({seasonal[0]},{seasonal[1]},{seasonal[2]})₂₄" if any(seasonal) else f" + {k} гармоники суток"
        extra = f" + прогноз погоды ({', '.join(WEATHER_NAMES[v] for v in self.weather_vars)})" if weather_vars else ""
        self.name = f"ARIMA({p},{d},{q}){cycle}{extra}, окно {window_days} дн."
        self.result = None
        self.end = None

    # внешние признаки прошедших часов: гармоники суток и погода (текущий расчёт d0)
    def _exog(self, index: pd.DatetimeIndex) -> np.ndarray | None:
        parts = [x for x in (harmonics(index, self.k),
                             weather.history(index, self.weather_vars) if self.weather_vars else None) if x is not None]
        return np.column_stack(parts) if parts else None

    def fit(self, history: pd.Series) -> None:
        y = history.iloc[-self.window_days * 24:]
        if self.weather_vars:
            y = y[y.index >= weather.START]  # раньше архива прогнозов погоды нет
        seasonal = (*self.seasonal, 24) if any(self.seasonal) else (0, 0, 0, 0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # предупреждения о сходимости оптимизатора – не ошибка
            self.result = SARIMAX(y.to_numpy(), exog=self._exog(y.index), order=self.order, seasonal_order=seasonal,
                                  enforce_stationarity=False, enforce_invertibility=False).fit(disp=False, maxiter=200)
        self.end = history.index[-1]
        self._forecast = None

    def predict(self, history: pd.Series, horizon: int) -> np.ndarray:
        new = history[history.index > self.end]
        if len(new):
            self.result = self.result.extend(new.to_numpy(), exog=self._exog(new.index))
            self.end = new.index[-1]
        future = pd.date_range(self.end + timedelta(hours=1), periods=horizon, freq="h").tz_convert(prep.TZ)
        parts = [x for x in (harmonics(future, self.k),
                             weather.future(self.end, horizon, self.weather_vars) if self.weather_vars else None)
                 if x is not None]
        self._forecast = self.result.get_forecast(horizon, exog=np.column_stack(parts) if parts else None)
        return np.clip(self._forecast.predicted_mean, LOW, HIGH)

    # собственные (гауссовские) интервалы последнего прогноза
    def intervals(self) -> dict:
        out = {}
        for level in LEVELS:
            bounds = np.clip(np.asarray(self._forecast.conf_int(alpha=1 - level)), LOW, HIGH)
            out[level] = (bounds[:, 0], bounds[:, 1])
        return out


# ---------- параллельный перебор: процессы наследуют ряд при запуске (fork) ----------
SERIES: pd.Series | None = None


def _aic(task: tuple) -> dict:
    order, seasonal, k, end = task
    model = Arima(order, seasonal, k, window_days=56)
    try:
        model.fit(SERIES[:pd.Timestamp(end, tz=prep.TZ)])
        aic = float(model.result.aic)
    except Exception:  # noqa: BLE001 – неудачная подгонка кандидата не должна ронять перебор
        aic = float("inf")
    return {"order": order, "seasonal": seasonal, "k": k, "end": end, "aic": aic}


def make(config: dict) -> Arima:
    return Arima(**config)


# прогон конфигураций по очереди, а недельные блоки каждой – параллельно на всех ядрах (с выводом прогресса)
def run_configs(configs: list[dict], at: pd.DatetimeIndex, label: str) -> list[tuple[dict, backtest.Result]]:
    out = []
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as pool:
        for i, config in enumerate(configs, 1):
            began = time.perf_counter()
            result = backtest.run_blocks(partial(make, config), SERIES, at, pool.map)
            print(f"  {label} {i}/{len(configs)}: {result.name} – {time.perf_counter() - began:.0f} с", flush=True)
            out.append((config, result))
    return out


def parallel(function, tasks: list) -> list:
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as pool:
        return list(pool.map(function, tasks))


# кандидаты порядков для каждого способа учёта суточного цикла
def candidates() -> dict[str, list[tuple]]:
    return {
        "sarima": [((p, 1, q), (sp, 1, sq), 0) for p, q, sp, sq in product((1, 2, 3), (0, 1, 2), (0, 1), (0, 1))],
        # 12 гармоник – предел для периода 24 ч (больше – уже не новая информация)
        "harmonic": [((p, 1, q), (0, 0, 0), k)
                     for p, q, k in product((1, 2, 3), (0, 1, 2, 3), (2, 3, 4, 5, 6, 8, 10, 12))],
    }


# подбор порядков: сумма AIC по окнам SELECTION_ENDS (только обучающая часть); AIC сравним лишь внутри способа
def select_orders(families: list[str]) -> dict:
    out = {}
    for family, options in candidates().items():
        if family not in families:
            continue
        rows = parallel(_aic, [(o, s, k, end) for (o, s, k) in options for end in SELECTION_ENDS])
        table = {}
        for row in rows:
            key = (tuple(row["order"]), tuple(row["seasonal"]), row["k"])
            table[key] = table.get(key, 0.0) + row["aic"]
        ranked = sorted(table.items(), key=lambda item: item[1])
        out[family] = [{"order": list(o), "seasonal": list(s), "k": k, "aic": round(a, 1)} for (o, s, k), a in ranked]
    return out


def evaluate(orders: dict) -> dict:
    start, end = backtest.PERIODS["validation"]
    at = backtest.origins(SERIES, start, end)
    configs = [{"order": tuple(best["order"]), "seasonal": tuple(best["seasonal"]), "k": best["k"], "window_days": w}
               for best in (orders["sarima"][0], orders["harmonic"][0]) for w in WINDOWS]
    runs = run_configs(configs, at, "валидация")
    reference = backtest.run(baselines.SeasonalNaive(24, "seasonal_24", "сезонно-наивная, сутки"), SERIES, at)
    profile = backtest.run(baselines.DailyProfile(7), SERIES, at)

    def mean_mae(result):
        return float(np.mean(backtest.horizon_metrics(result)["mae"]))

    # лучший размер окна для каждого способа – по средней MAE на 1–72 ч; для него – эмпирические интервалы
    best = {}
    for config, result in runs:
        family = "sarima" if any(config["seasonal"]) else "harmonic"
        if family not in best or mean_mae(result) < mean_mae(best[family][1]):
            best[family] = (config, result)
    calibration_at = backtest.origins(SERIES, start - timedelta(days=365), start)
    calibrated = {c.name: c for _, c in run_configs([config for config, _ in best.values()], calibration_at,
                                                     "калибровка")}
    for _, result in best.values():
        backtest.add_intervals(result, backtest.interval_quantiles(calibrated[result.name], LEVELS))

    report = {"windows": {}, "models": {}}
    for config, result in runs:
        report["windows"][result.name] = {"config": {k: list(v) if isinstance(v, tuple) else v
                                                     for k, v in config.items()},
                                          "mae_1_72": round(mean_mae(result), 4),
                                          **backtest.summary(result, reference)["buckets"]}
    curves = {}
    for family, (config, result) in best.items():
        key = f"arima_{family}"
        report["models"][key] = {"name": result.name, **backtest.summary(result, reference)}
        curves[key] = np.round(backtest.horizon_metrics(result)["mae"], 4).tolist()
    curves["profile_7d"] = np.round(backtest.horizon_metrics(profile)["mae"], 4).tolist()
    report["mae_by_horizon"] = curves
    report["example"] = example({f"arima_{family}": result for family, (_, result) in best.items()})
    return report


# пример одного прогноза для рисунка: двое суток до момента прогноза, прогноз с интервалами и факт (мкг/м³)
EXAMPLE_ORIGIN = pd.Timestamp("2025-01-15 18:00", tz=prep.TZ)


def example(results: dict) -> dict:
    out = {"origin": EXAMPLE_ORIGIN.isoformat(),
           "history": np.round(np.exp(SERIES[:EXAMPLE_ORIGIN].iloc[-48:]), 2).tolist(), "models": {}}
    for key, result in results.items():
        i = int(np.where(result.origins == EXAMPLE_ORIGIN)[0][0])
        row = {"name": result.name, "pred": np.exp(result.pred[i]), "actual": np.exp(result.actual[i])}
        for level in LEVELS:
            row[f"lower{int(level * 100)}"] = np.exp(result.lower[level][i])
            row[f"upper{int(level * 100)}"] = np.exp(result.upper[level][i])
        out["models"][key] = {k: v if isinstance(v, str) else np.round(v, 2).tolist() for k, v in row.items()}
    return out


def main() -> None:
    global SERIES
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["orders", "validate"])
    parser.add_argument("--family", choices=list(candidates()), action="append",
                        help="при orders: пересчитать только этот способ (остальные берутся из orders.json)")
    args = parser.parse_args()
    SERIES = backtest.log_series(prep.clean(prep.load()))
    REPORTS.mkdir(parents=True, exist_ok=True)

    if args.command == "orders":
        path = REPORTS / "orders.json"
        orders = json.loads(path.read_text(encoding="utf-8")) if args.family and path.exists() else {}
        orders.update(select_orders(args.family or list(candidates())))
        path.write_text(json.dumps(orders, ensure_ascii=False, indent=1), encoding="utf-8")
        for family, ranked in orders.items():
            print(family, ranked[:3])
        return

    orders = json.loads((REPORTS / "orders.json").read_text(encoding="utf-8"))
    report = evaluate(orders)
    report["meta"] = {"period": "validation", "windows_days": list(WINDOWS), "refit_days": 7,
                      "intervals": "эмпирические квантили ошибок за год до валидации; native – гауссовские ARIMA"}
    (REPORTS / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{'конфигурация':52} {'1–72':>6} {'1–24':>6} {'25–48':>6} {'49–72':>6}")
    for name, row in report["windows"].items():
        print(f"{name:52} {row['mae_1_72']:6.2f} {row['1–24']['mae']:6.2f} {row['25–48']['mae']:6.2f} "
              f"{row['49–72']['mae']:6.2f}")
    for key, row in report["models"].items():
        b = row["buckets"]["1–24"]
        print(key, {k: b[k] for k in ("mae", "skill", "cover80", "native_cover80", "width80", "native_width80")})


if __name__ == "__main__":
    main()
