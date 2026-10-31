"""Проверка обученных в Colab LSTM (artifacts/*.onnx) на валидации тем же кодом, что ARIMA и Prophet.

    make -C model lstm   # -> reports/lstm/validation.json
"""
import json
from datetime import timedelta
from pathlib import Path

import numpy as np

import backtest
import baselines
import lstm
import prep

REPORTS = Path(__file__).resolve().parent / "reports" / "lstm"
VARIANTS = ("lstm", "lstm_weather")


def main() -> None:
    frame = prep.clean(prep.load())
    series = backtest.log_series(frame)
    start, end = backtest.PERIODS["validation"]
    at = backtest.origins(series, start, end)
    reference = backtest.run(baselines.SeasonalNaive(24, "seasonal_24", "сезонно-наивная, сутки"), series, at)
    report = {"meta": {"period": "validation", "trained_until": start.isoformat(),
                       "intervals": "эмпирические квантили ошибок за год до валидации (без погоды) или с 08.02.2024 "
                                    "(с погодой); модели обучены до начала валидации, веса фиксированы"},
              "models": {}, "mae_by_horizon": {}, "training": {}}
    results = {}
    for variant in VARIANTS:
        model = lstm.LstmModel(variant, frame=frame)
        results[variant] = backtest.run(model, series, at)
        # калибровка интервалов – на годе до валидации; варианту с погодой нужны прогнозы погоды (архив с 08.02.2024)
        first = start - timedelta(days=365) if not model.variables else lstm.weather.START + timedelta(days=8)
        calibration = backtest.run(model, series, backtest.origins(series, first, start))
        backtest.add_intervals(results[variant], backtest.interval_quantiles(calibration))
        meta = json.loads((lstm.ARTIFACTS / "validation" / f"{variant}.json").read_text(encoding="utf-8"))
        report["training"][variant] = {k: meta[k] for k in ("epochs", "hold_loss", "torch", "created")}
        report["models"][variant] = {"name": results[variant].name, **backtest.summary(results[variant], reference)}
        report["mae_by_horizon"][variant] = np.round(backtest.horizon_metrics(results[variant])["mae"], 4).tolist()
    report["dm"] = {name: backtest.dm_test(results["lstm_weather"], results["lstm"], bounds)
                    for name, bounds in backtest.BUCKETS.items()}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    for variant, row in report["models"].items():
        print(row["name"], {k: (v["mae"], v["skill"], v["cover80"]) for k, v in row["buckets"].items()})
    print("с погодой против без:", report["dm"])


if __name__ == "__main__":
    main()
