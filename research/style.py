"""Общее оформление рисунков для отчёта: шрифт, палитра, оси, сохранение «Рисунок N – Название.png».
Используется рисунками исследования (research/figures.py) и моделей (model/)."""
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

OUT = Path(os.environ.get("FIGURES", "/figures"))

# шрифт отчёта – Times New Roman из Windows (папка Fonts подключена только для чтения)
for name in ("times.ttf", "timesbd.ttf", "timesi.ttf"):
    path = Path("/winfonts") / name
    if path.exists():
        font_manager.fontManager.addfont(str(path))

# палитра: категориальные цвета по порядку, чернила и сетка – нейтральные
BLUE, ORANGE, AQUA, YELLOW, MAGENTA = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"
BLUE_LIGHT = "#9ec5f4"
CRITICAL = "#d03b3b"
INK, INK2, MUTED, GRID, AXIS, WASH = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#f0efec"
SEQUENTIAL = LinearSegmentedColormap.from_list("blue", ["#cde2fb", "#86b6ef", "#3987e5", "#256abf", "#104281",
                                                        "#0d366b"])

plt.rcParams.update({
    "font.family": "Times New Roman", "font.size": 12, "axes.titlesize": 13, "axes.labelsize": 12,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.8, "axes.axisbelow": True, "legend.frameon": True, "legend.framealpha": 0.95,
    "legend.edgecolor": GRID, "lines.linewidth": 2, "savefig.dpi": 200, "savefig.bbox": "tight",
    "axes.formatter.use_locale": False,
})

COMMA = FuncFormatter(lambda v, _: f"{v:g}".replace(".", ","))
UNIT = "PM2.5, мкг/м³"


def num(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def naive(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    return index.tz_localize(None)


def save(fig, n: int, title: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"Рисунок {n} – {title}.png", facecolor="white")
    plt.close(fig)
    print("saved", n, title)
