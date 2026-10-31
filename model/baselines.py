"""Базовые модели – планка, которую должны превзойти ARIMA, Prophet и LSTM; их проверка на валидации.

    make -C model baselines              # валидация (по умолчанию)
    make -C model baselines PERIOD=test  # отложенный тест – только на итоговом сравнении (шаг 6)
"""
import argparse
import json
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

import backtest
import prep

REPORTS = Path(__file__).resolve().parent / "reports" / "baselines"


class Persistence:
    key, name = "persistence", "последнее значение"

    def fit(self, history: pd.Series) -> None:
        pass

    def predict(self, history: pd.Series, horizon: int) -> np.ndarray:
        return np.full(horizon, history.iloc[-1])


# сезонно-наивная: значение в тот же час периодом раньше; если этот час ещё в будущем – ещё на период раньше
# (для суток и горизонта 30 ч – значение за 48 ч до целевого часа, последнее известное в тот же час суток)
class SeasonalNaive:
    def __init__(self, period: int, key: str, name: str) -> None:
        self.period, self.key, self.name = period, key, name

    def fit(self, history: pd.Series) -> None:
        pass

    def predict(self, history: pd.Series, horizon: int) -> np.ndarray:
        values = history.to_numpy()
        h = np.arange(1, horizon + 1)
        back = np.ceil(h / self.period).astype(int) * self.period
        return values[len(values) - 1 + h - back]


# средний профиль: среднее (в логарифмах) за последние days суток в тот же час суток
class DailyProfile:
    def __init__(self, days: int = 7) -> None:
        self.days, self.key, self.name = days, f"profile_{days}d", f"средний профиль за {days} дней"

    def fit(self, history: pd.Series) -> None:
        pass

    def predict(self, history: pd.Series, horizon: int) -> np.ndarray:
        values = history.to_numpy()
        h = np.arange(1, horizon + 1)
        first = np.ceil(h / 24).astype(int)
        back = (first[:, None] + np.arange(self.days)[None, :]) * 24
        return values[len(values) - 1 + h[:, None] - back].mean(axis=1)


def baselines() -> list:
    return [
        Persistence(),
        SeasonalNaive(24, "seasonal_24", "сезонно-наивная, сутки"),
        SeasonalNaive(168, "seasonal_168", "сезонно-наивная, неделя"),
        DailyProfile(7),
    ]


# проверка на части period; интервалы – по ошибкам той же модели за год до начала части (без заглядывания в неё)
def evaluate(models: list, series: pd.Series, period: str) -> tuple[dict, dict]:
    start, end = backtest.PERIODS[period]
    at = backtest.origins(series, start, end)
    calibration_at = backtest.origins(series, start - timedelta(days=365), start)
    results = {}
    for model in models:
        result = backtest.run(model, series, at)
        quantiles = backtest.interval_quantiles(backtest.run(model, series, calibration_at))
        results[model.key] = backtest.add_intervals(result, quantiles)
    reference = results["seasonal_24"]
    report = {model.key: {"name": model.name, **backtest.summary(results[model.key], reference)} for model in models}
    curves = {key: np.round(backtest.horizon_metrics(result)["mae"], 4).tolist() for key, result in results.items()}
    return report, curves


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--period", choices=list(backtest.PERIODS), default="validation")
    args = parser.parse_args()

    series = backtest.log_series(prep.clean(prep.load()))
    report, curves = evaluate(baselines(), series, args.period)
    start, end = backtest.PERIODS[args.period]
    meta = {"period": args.period, "start": start.isoformat(), "end": (end or series.index[-1]).isoformat(),
            "horizon": backtest.HORIZON, "origin_hours": list(backtest.ORIGIN_HOURS),
            "intervals": "эмпирические квантили ошибок за год до начала части"}
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / f"{args.period}.json"
    path.write_text(json.dumps({"meta": meta, "models": report, "mae_by_horizon": curves}, ensure_ascii=False,
                               indent=1), encoding="utf-8")
    print(f"сохранено: {path.relative_to(REPORTS.parents[1])}")
    print(f"\n{'модель':28} {'MAE 1–24':>9} {'MAE 25–48':>10} {'MAE 49–72':>10} {'sMAPE 1–24':>11} "
          f"{'выигрыш 1–24':>13} {'покр. 80%':>10}")
    for row in report.values():
        b = row["buckets"]
        print(f"{row['name']:28} {b['1–24']['mae']:9.2f} {b['25–48']['mae']:10.2f} {b['49–72']['mae']:10.2f} "
              f"{b['1–24']['smape']:11.1f} {b['1–24']['skill']:13.3f} {b['1–24']['cover80']:10.2f}")


if __name__ == "__main__":
    main()
