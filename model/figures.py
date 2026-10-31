"""Рисунки моделей по сохранённым отчётам (reports/); номера продолжают рисунки исследования.

    make -C model figures FIGURES=/путь/к/папке
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from style import AQUA, BLUE, COMMA, ORANGE, YELLOW, save

REPORTS = Path(__file__).resolve().parent / "reports"
COLORS = {"persistence": ORANGE, "seasonal_24": BLUE, "seasonal_168": YELLOW, "profile_7d": AQUA}


def fig_baselines() -> None:
    report = json.loads((REPORTS / "baselines" / "validation.json").read_text(encoding="utf-8"))
    fig, ax = plt.subplots(figsize=(10, 4.8))
    for key, curve in report["mae_by_horizon"].items():
        h = np.arange(1, len(curve) + 1)
        ax.plot(h, curve, color=COLORS[key], lw=2, label=report["models"][key]["name"])
    ax.set_xticks(range(0, 73, 12))
    ax.set_xlim(1, 72)
    ax.set_ylim(0, None)
    ax.set_xlabel("горизонт прогноза, часов")
    ax.set_ylabel("MAE, мкг/м³")
    ax.yaxis.set_major_formatter(COMMA)
    ax.legend(loc="lower right")
    save(fig, 16, "Ошибка базовых моделей по горизонту прогноза на валидации")


if __name__ == "__main__":
    fig_baselines()
