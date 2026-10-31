"""Prophet: аддитивная модель ln PM2.5 = тренд + суточная + годовая (+ недельная) сезонность (+ ступени циклов CAMS).

    make -C model prophet   # варианты на валидации, интервалы для лучшего -> reports/prophet/validation.json
"""
import json
import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import timedelta
from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd

import backtest
import baselines
import prep
import weather

REPORTS = Path(__file__).resolve().parent / "reports" / "prophet"
LEVELS = (0.8, 0.95)
LOW, HIGH = np.log(0.3), np.log(500)

logging.getLogger("cmdstanpy").disabled = True  # cmdstanpy пишет о каждой подгонке
# предупреждение о годовой сезонности при истории короче двух лет – ожидаемо и учтено в выводах; не засоряем логи
logging.getLogger("prophet").setLevel(logging.ERROR)
# «Importing plotly failed» – Prophet ищет plotly для интерактивных графиков; они не нужны (рисунки – matplotlib)
logging.getLogger("prophet.plot").disabled = True


# ступени уровня после обновлений CAMS: 1 начиная с даты цикла (известны и в будущем – это расписание, не данные)
def cams_steps(ds: pd.Series) -> pd.DataFrame:
    utc = pd.to_datetime(ds).dt.tz_localize("UTC")
    return pd.DataFrame({f"cams_{name}": (utc >= start).astype(float) for name, start in prep.CAMS_CYCLES[1:]})


class ProphetModel:
    """Prophet по ln PM2.5 в шкале UTC (без скачка местного времени 01.03.2024). Между подгонками новые часы
    не учитываются: Prophet – функция от времени, а не от последних наблюдений."""

    def __init__(self, steps: bool = False, weekly: bool = False, window_days: int | None = None,
                 weather_vars: tuple[str, ...] = (), yearly: bool = True,
                 history_start: pd.Timestamp | None = None) -> None:
        self.steps, self.weekly, self.window_days, self.yearly = steps, weekly, window_days, yearly
        self.weather_vars = tuple(weather_vars)
        # с погодой история ограничена архивом прогнозов – для честного контроля её можно ограничить и без погоды
        self.history_start = weather.START if weather_vars else history_start
        if window_days is not None:
            parts = [f"окно {window_days} дн."]
        elif self.history_start is not None:
            parts = [f"история с {self.history_start:%d.%m.%Y}"]
        else:
            parts = ["вся история"]
        if steps:
            parts.append("ступени CAMS")
        if weekly:
            parts.append("недельная сезонность")
        if weather_vars:
            parts.append("прогноз погоды (" + ", ".join(weather.NAMES[v] for v in self.weather_vars) + ")")
        if not yearly:
            parts.append("без годовой сезонности")
        self.name = "Prophet: " + ", ".join(parts)
        self.model = None

    def _frame(self, index: pd.DatetimeIndex, values=None, weather_values: np.ndarray | None = None) -> pd.DataFrame:
        frame = pd.DataFrame({"ds": index.tz_convert("UTC").tz_localize(None)})
        if values is not None:
            frame["y"] = np.asarray(values)
        if self.steps:
            frame = pd.concat([frame, cams_steps(frame["ds"])], axis=1)
        if self.weather_vars:
            for i, name in enumerate(self.weather_vars):
                frame[f"w_{name}"] = weather_values[:, i]
        return frame

    def fit(self, history: pd.Series) -> None:
        from prophet import Prophet  # тяжёлый импорт – только в процессах, где модель действительно нужна

        if self.window_days is not None:
            history = history.iloc[-self.window_days * 24:]
        if self.history_start is not None:
            history = history[history.index >= self.history_start]  # с погодой – раньше архива прогнозов нет
        model = Prophet(daily_seasonality=10, yearly_seasonality=6 if self.yearly else False,
                        weekly_seasonality=self.weekly, changepoint_prior_scale=0.05, uncertainty_samples=0)
        if self.steps:
            for name, start in prep.CAMS_CYCLES[1:]:
                if history.index[0] < start <= history.index[-1]:  # ступень, которой нет в истории, не выучить
                    model.add_regressor(f"cams_{name}", standardize=False)
        for name in self.weather_vars:
            model.add_regressor(f"w_{name}")
        past = weather.history(history.index, self.weather_vars) if self.weather_vars else None
        self.model = model.fit(self._frame(history.index, history.to_numpy(), past))

    def predict(self, history: pd.Series, horizon: int) -> np.ndarray:
        future = pd.date_range(history.index[-1] + timedelta(hours=1), periods=horizon, freq="h")
        ahead = weather.future(history.index[-1], horizon, self.weather_vars) if self.weather_vars else None
        forecast = self.model.predict(self._frame(future, weather_values=ahead))
        # части прогноза (ln PM2.5) для «почему такой прогноз» на сайте: yhat = тренд + суточный + годовой ход
        # (+ регрессоры, если они есть)
        self.parts = pd.DataFrame({name: forecast[name].to_numpy() if name in forecast else np.zeros(horizon)
                                   for name in ("trend", "daily", "yearly")}, index=future)
        return np.clip(forecast["yhat"].to_numpy(), LOW, HIGH)


VARIANTS = {
    "auto": dict(),
    "auto_weekly": dict(weekly=True),
    "steps": dict(steps=True),
    "steps_weekly": dict(steps=True, weekly=True),
    "window365": dict(window_days=365),
}


def make(variant: str) -> ProphetModel:
    return ProphetModel(**VARIANTS[variant])


def main() -> None:
    series = backtest.log_series(prep.clean(prep.load()))
    start, end = backtest.PERIODS["validation"]
    at = backtest.origins(series, start, end)
    workers = os.cpu_count()
    print(f"Prophet: {len(VARIANTS)} вариантов × {len(backtest.refit_blocks(at))} недельных блоков, "
          f"процессов: {workers}", flush=True)

    results = {}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for variant in VARIANTS:
            began = time.perf_counter()
            results[variant] = backtest.run_blocks(partial(make, variant), series, at, pool.map)
            mean = float(np.mean(backtest.horizon_metrics(results[variant])["mae"]))
            print(f"  {variant:13} MAE 1–72 = {mean:.2f}, {time.perf_counter() - began:.0f} с", flush=True)

        best = min(results, key=lambda v: float(np.mean(backtest.horizon_metrics(results[v])["mae"])))
        print(f"калибровка интервалов для лучшего варианта ({best}) на годе до валидации…", flush=True)
        calibration = backtest.run_blocks(partial(make, best), series,
                                          backtest.origins(series, start - timedelta(days=365), start), pool.map)
    backtest.add_intervals(results[best], backtest.interval_quantiles(calibration, LEVELS))

    reference = backtest.run(baselines.SeasonalNaive(24, "seasonal_24", "сезонно-наивная, сутки"), series, at)
    report = {"meta": {"period": "validation", "refit_days": 7, "scale": "ln PM2.5, время UTC",
                       "intervals": "эмпирические квантили ошибок за год до валидации"},
              "variants": {}, "models": {}, "mae_by_horizon": {}}
    for variant, result in results.items():
        report["variants"][variant] = {"name": result.name,
                                       "mae_1_72": round(float(np.mean(backtest.horizon_metrics(result)["mae"])), 4),
                                       **backtest.summary(result, reference)["buckets"]}
    report["models"]["prophet"] = {"name": results[best].name, "variant": best,
                                   **backtest.summary(results[best], reference)}
    report["mae_by_horizon"]["prophet"] = np.round(backtest.horizon_metrics(results[best])["mae"], 4).tolist()
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    b = report["models"]["prophet"]["buckets"]
    print("лучший:", results[best].name, {k: (v["mae"], v["skill"], v["cover80"]) for k, v in b.items()})


if __name__ == "__main__":
    main()
