"""Рисунки моделей по сохранённым отчётам (reports/); номера продолжают рисунки исследования.

    make -C model figures FIGURES=/путь/к/папке
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from style import AQUA, BLUE, COMMA, INK2, ORANGE, YELLOW, save

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


def main() -> None:
    baseline = load("baselines/validation.json")
    fig_baselines(baseline)
    arima = load("arima/validation.json")
    if arima:
        fig_arima(arima, baseline)
        fig_example(arima)


if __name__ == "__main__":
    main()
