"""Рисунки моделей по сохранённым отчётам (reports/); номера продолжают рисунки исследования.

    make -C model figures FIGURES=/путь/к/папке
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from style import AQUA, BLUE, COMMA, INK2, MAGENTA, ORANGE, YELLOW, save

REPORTS = Path(__file__).resolve().parent / "reports"
COLORS = {"persistence": ORANGE, "seasonal_24": BLUE, "seasonal_168": YELLOW, "profile_7d": AQUA}


def load(name: str) -> dict | None:
    path = REPORTS / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def horizon_axis(ax) -> None:
    ax.set_xticks(range(0, 73, 12))
    ax.set_xlim(1, 72)
    ax.set_ylim(0, None)
    ax.set_xlabel("горизонт прогноза, часов")
    ax.set_ylabel("MAE, мкг/м³")
    ax.yaxis.set_major_formatter(COMMA)


def fig_baselines(report: dict) -> None:
    fig, ax = plt.subplots(figsize=(10, 4.8))
    for key, curve in report["mae_by_horizon"].items():
        ax.plot(np.arange(1, len(curve) + 1), curve, color=COLORS[key], lw=2, label=report["models"][key]["name"])
    horizon_axis(ax)
    ax.legend(loc="lower right")
    save(fig, 16, "Ошибка базовых моделей по горизонту прогноза на валидации")


def fig_arima(report: dict, baseline: dict) -> None:
    fig, ax = plt.subplots(figsize=(10, 4.8))
    lines = [("arima_sarima", BLUE, report["models"]["arima_sarima"]["name"]),
             ("arima_harmonic", ORANGE, report["models"]["arima_harmonic"]["name"]),
             ("profile_7d", AQUA, "средний профиль за 7 дней (лучшая базовая)")]
    for key, color, label in lines:
        curve = report["mae_by_horizon"][key]
        ax.plot(np.arange(1, len(curve) + 1), curve, color=color, lw=2, label=label)
    curve = baseline["mae_by_horizon"]["seasonal_24"]
    ax.plot(np.arange(1, len(curve) + 1), curve, color=INK2, lw=1.2, ls=(0, (4, 3)), label="сезонно-наивная, сутки")
    horizon_axis(ax)
    ax.legend(loc="lower right")
    save(fig, 17, "Ошибка ARIMA по горизонту прогноза на валидации")


def fig_example(report: dict) -> None:
    example = report["example"]
    history = example["history"]
    fig, axes = plt.subplots(1, len(example["models"]), figsize=(12, 4.4), sharey=True)
    for ax, (key, row) in zip(np.atleast_1d(axes), example["models"].items()):
        past = np.arange(-len(history) + 1, 1)
        ahead = np.arange(1, len(row["pred"]) + 1)
        ax.plot(past, history, color=INK2, lw=1.4, label="факт до прогноза")
        ax.fill_between(ahead, row["lower95"], row["upper95"], color=BLUE, alpha=0.10, lw=0, label="интервал 95 %")
        ax.fill_between(ahead, row["lower80"], row["upper80"], color=BLUE, alpha=0.18, lw=0, label="интервал 80 %")
        ax.plot(ahead, row["actual"], color=INK2, lw=1.4, ls=(0, (4, 3)), label="факт")
        ax.plot(ahead, row["pred"], color=BLUE, lw=2, label="прогноз")
        ax.axvline(0, color=INK2, lw=1)
        ax.set_title(row["name"], loc="left", fontsize=12)
        ax.set_xticks(range(-48, 73, 24))
        ax.set_xlabel("часы от момента прогноза")
        ax.yaxis.set_major_formatter(COMMA)
    np.atleast_1d(axes)[0].set_ylabel("PM2.5, мкг/м³")
    np.atleast_1d(axes)[0].legend(loc="upper left", fontsize=10)
    save(fig, 18, "Пример прогноза ARIMA с интервалами 15.01.2025 18 00")


def fig_prophet(prophet: dict, arima: dict, baseline: dict) -> None:
    fig, ax = plt.subplots(figsize=(10, 4.8))
    lines = [(prophet["mae_by_horizon"]["prophet"], MAGENTA, prophet["models"]["prophet"]["name"]),
             (arima["mae_by_horizon"]["arima_harmonic"], ORANGE, arima["models"]["arima_harmonic"]["name"]),
             (arima["mae_by_horizon"]["profile_7d"], AQUA, "средний профиль за 7 дней (лучшая базовая)")]
    for curve, color, label in lines:
        ax.plot(np.arange(1, len(curve) + 1), curve, color=color, lw=2, label=label)
    curve = baseline["mae_by_horizon"]["persistence"]
    ax.plot(np.arange(1, len(curve) + 1), curve, color=INK2, lw=1.2, ls=(0, (4, 3)), label="последнее значение")
    horizon_axis(ax)
    ax.set_ylim(0, 12)
    ax.legend(loc="lower right")
    save(fig, 19, "Ошибка Prophet по горизонту прогноза на валидации")


# компоненты Prophet, подогнанного на всей обучающей части (до валидации): тренд, суточный и годовой ход
def fig_prophet_components() -> None:
    import pandas as pd

    import backtest
    import prep
    import prophet_model

    series = backtest.log_series(prep.clean(prep.load()))
    model = prophet_model.ProphetModel()
    model.fit(series[series.index < backtest.VALID_START])
    hours = pd.date_range("2024-01-01", periods=24, freq="h")  # сутки в UTC; местное время Алматы – UTC+5
    days = pd.date_range("2024-01-01", "2024-12-31", freq="D")
    daily = model.model.predict(pd.DataFrame({"ds": hours}))["daily"].to_numpy()
    yearly = model.model.predict(pd.DataFrame({"ds": days}))["yearly"].to_numpy()
    history = model.model.history
    trend = model.model.predict(history[["ds"]])["trend"].to_numpy()

    fig, axes = plt.subplots(3, 1, figsize=(10, 9))
    axes[0].plot(history["ds"], np.exp(trend), color=BLUE, lw=2)
    axes[0].set_title("тренд (уровень без сезонностей), мкг/м³", loc="left")
    local = (np.arange(24) + 5) % 24
    order = np.argsort(local)
    axes[1].plot(local[order], np.exp(daily[order]), color=ORANGE, lw=2, marker="o", ms=4)
    axes[1].set_xticks(range(0, 24, 2), [f"{h:02d}" for h in range(0, 24, 2)])
    axes[1].set_title("суточный ход – множитель к тренду по местному часу (UTC+5)", loc="left")
    axes[2].plot(days.day_of_year, np.exp(yearly), color=AQUA, lw=2)
    starts = pd.date_range("2025-01-01", periods=12, freq="MS").day_of_year
    axes[2].set_xticks(starts, ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя",
                                "дек"])
    axes[2].set_xlim(1, 366)
    axes[2].set_title("годовой ход – множитель к тренду", loc="left")
    for ax in axes[1:]:
        ax.axhline(1, color=INK2, lw=1)
    for ax in axes:
        ax.yaxis.set_major_formatter(COMMA)
    fig.tight_layout(h_pad=1.5)
    save(fig, 20, "Компоненты Prophet на обучающей части")


def fig_weather(report: dict) -> None:
    configs = report["configs"]
    buckets = ["1–24", "25–48", "49–72"]
    panels = [
        ("ARIMA + 12 гармоник, окно 90 дн.", [("arima_w90", BLUE, "без погоды"),
                                              ("arima_weather_w90", ORANGE, "с прогнозом погоды")]),
        ("Prophet", [("prophet", BLUE, "без погоды, вся история"),
                     ("prophet_feb2024", AQUA, "без погоды, история с 02.2024"),
                     ("prophet_weather_noyear", ORANGE, "с прогнозом погоды, история с 02.2024")]),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True)
    for ax, (title, bars) in zip(axes, panels):
        width = 0.8 / len(bars)
        for j, (key, color, label) in enumerate(bars):
            x = np.arange(len(buckets)) + (j - (len(bars) - 1) / 2) * width
            values = [configs[key][b]["mae"] for b in buckets]
            ax.bar(x, values, width=width * 0.9, color=color, label=label)
            for xi, v in zip(x, values):
                ax.text(xi, v + 0.1, f"{v:.2f}".replace(".", ","), ha="center", va="bottom", fontsize=9.5)
        ax.set_xticks(range(len(buckets)), [f"{b} ч" for b in buckets])
        ax.set_title(title, loc="left")
        ax.grid(axis="x", visible=False)
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), fontsize=10.5, frameon=False)
    axes[0].set_ylabel("MAE, мкг/м³")
    axes[0].yaxis.set_major_formatter(COMMA)
    save(fig, 21, "Ошибка моделей с прогнозом погоды и без на валидации")


def main() -> None:
    baseline = load("baselines/validation.json")
    fig_baselines(baseline)
    arima = load("arima/validation.json")
    if arima:
        fig_arima(arima, baseline)
        fig_example(arima)
    prophet = load("prophet/validation.json")
    if prophet and arima:
        fig_prophet(prophet, arima, baseline)
        fig_prophet_components()
    weather = load("weather/validation.json")
    if weather:
        fig_weather(weather)


if __name__ == "__main__":
    main()
