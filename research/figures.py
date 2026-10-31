"""Рисунки исследования ряда (шаг 2) по снимку ряда и results/eda.json.

    make -C research figures FIGURES=/путь/к/папке
Имена файлов – «Рисунок N – Название.png»; номера – порядок в разделе исследования, в отчёте их можно сдвинуть.
"""
import json
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402
from statsmodels.tsa.stattools import pacf  # noqa: E402

import eda  # noqa: E402
import prep  # noqa: E402

OUT = Path(os.environ.get("FIGURES", "/figures"))
EDA = json.loads((eda.RESULTS / "eda.json").read_text(encoding="utf-8"))

# шрифт отчёта – Times New Roman из Windows (папка Fonts подключена только для чтения)
for name in ("times.ttf", "timesbd.ttf", "timesi.ttf"):
    path = Path("/winfonts") / name
    if path.exists():
        font_manager.fontManager.addfont(str(path))

# палитра: категориальные цвета по порядку, чернила и сетка – нейтральные
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
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
MONTHS = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]
WEEKDAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
UNIT = "PM2.5, мкг/м³"


def num(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def naive(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    return index.tz_localize(None)


def date_axis(ax, fmt: str = "%m.%Y", interval: int = 6) -> None:
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=range(1, 13, interval) if interval > 1 else None))
    ax.xaxis.set_major_formatter(mdates.DateFormatter(fmt))


# норма ВОЗ подписывается в легенде: подпись прямо на линии налезает на данные
def who_line(ax) -> None:
    ax.axhline(prep.WHO_24H, color=INK2, lw=1, ls=(0, (4, 3)), label="норма ВОЗ, 15 мкг/м³ за сутки")


# вертикальные линии обновлений модели CAMS (первый цикл – начало ряда, его не рисуем)
def upgrades(ax) -> None:
    for name, start in prep.CAMS_CYCLES[1:]:
        x = start.tz_convert(prep.TZ).tz_localize(None)
        ax.axvline(x, color=INK2, lw=1, ls=(0, (1, 2)))
        ax.text(x, 0.99, f" CAMS {name}", transform=ax.get_xaxis_transform(), va="top", ha="left", color=INK2,
                fontsize=10)


def save(fig, n: int, title: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"Рисунок {n} – {title}.png", facecolor="white")
    plt.close(fig)
    print("saved", n, title)


def fig_series(frame: pd.DataFrame, daily: pd.Series) -> None:
    fig, ax = plt.subplots(figsize=(11, 4.6))
    ax.plot(naive(frame.index), frame["pm2_5"], color=BLUE_LIGHT, lw=0.4, label="почасовые значения")
    ax.plot(naive(daily.index), daily, color=BLUE, lw=1.4, label="среднесуточные")
    test_start = prep.TEST_START.tz_convert(prep.TZ).tz_localize(None)
    ax.axvspan(test_start, naive(frame.index)[-1], color=WASH, zorder=0)
    ax.text(test_start, 0.9, "  отложенный тест", transform=ax.get_xaxis_transform(), va="top", color=INK2,
            fontsize=11)
    who_line(ax)
    upgrades(ax)
    ax.set_ylabel(UNIT)
    ax.set_ylim(0, None)
    ax.set_xlim(naive(frame.index)[0], naive(frame.index)[-1])
    date_axis(ax)
    ax.yaxis.set_major_formatter(COMMA)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncols=3, frameon=False)
    save(fig, 1, "Почасовой и среднесуточный PM2.5 в Алматы")


def fig_distribution(train: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    raw, log = train["pm2_5"], np.log(train["pm2_5"])
    for ax, values, xlabel, skew in [
        (axes[0], raw, UNIT, EDA["describe"]["train_skew_raw"]),
        (axes[1], log, "ln PM2.5", EDA["describe"]["train_skew_log"]),
    ]:
        ax.hist(values, bins=60, color=BLUE, edgecolor="white", linewidth=0.6)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("часов")
        ax.set_title(f"асимметрия {num(skew)}", color=INK2, fontsize=12)
        ax.xaxis.set_major_formatter(COMMA)
    save(fig, 2, "Распределение почасового PM2.5 до и после логарифма")


def fig_heatmap(frame: pd.DataFrame) -> None:
    pm = frame["pm2_5"]
    table = pm.groupby([pm.index.hour, pm.index.month]).mean().unstack()
    fig, ax = plt.subplots(figsize=(9, 6.2))
    image = ax.imshow(table.to_numpy(), aspect="auto", cmap=SEQUENTIAL, origin="lower")
    ax.set_xticks(range(12), MONTHS)
    ax.set_yticks(range(0, 24, 2), [f"{h:02d}:00" for h in range(0, 24, 2)])
    ax.set_xlabel("месяц")
    ax.set_ylabel("час суток (местное время)")
    ax.grid(False)
    bar = fig.colorbar(image, ax=ax, pad=0.02)
    bar.set_label("средний " + UNIT)
    bar.outline.set_visible(False)
    save(fig, 3, "Средний PM2.5 по часу суток и месяцу")


def fig_daily_profile(frame: pd.DataFrame) -> None:
    pm = frame["pm2_5"]
    fig, ax = plt.subplots(figsize=(10, 4.6))
    for months, color, label in [([12, 1, 2], BLUE, "зима (декабрь–февраль)"),
                                 ([6, 7, 8], ORANGE, "лето (июнь–август)")]:
        part = pm[pm.index.month.isin(months)]
        grouped = part.groupby(part.index.hour)
        q25, median, q75 = grouped.quantile(0.25), grouped.median(), grouped.quantile(0.75)
        ax.fill_between(median.index, q25, q75, color=color, alpha=0.12, lw=0)
        ax.plot(median.index, median, color=color, marker="o", ms=4, label=f"{label}, медиана и квартили")
    ax.set_xticks(range(0, 24, 2), [f"{h:02d}" for h in range(0, 24, 2)])
    ax.set_xlabel("час суток (местное время)")
    ax.set_ylabel(UNIT)
    ax.set_ylim(0, None)
    ax.legend(loc="upper left")
    save(fig, 4, "Суточный профиль PM2.5 зимой и летом")


def fig_weekday() -> None:
    fig, ax = plt.subplots(figsize=(8, 4.2))
    for key, color, label in [("heating", BLUE, "отопительный сезон"), ("non_heating", ORANGE, "остальное время")]:
        values = EDA["weekday_mean"][key]
        days = sorted(values, key=int)
        ax.plot(range(7), [values[d] for d in days], color=color, marker="o", ms=5, label=label)
    ax.set_xticks(range(7), WEEKDAYS)
    ax.set_ylabel("средний " + UNIT)
    ax.set_ylim(0, None)
    ax.legend(loc="lower left")
    save(fig, 5, "Средний PM2.5 по дням недели")


def fig_months_box(daily: pd.Series) -> None:
    fig, ax = plt.subplots(figsize=(10, 4.6))
    data = [daily[daily.index.month == m].to_numpy() for m in range(1, 13)]
    parts = ax.boxplot(data, widths=0.55, patch_artist=True, showfliers=True,
                       medianprops={"color": INK, "lw": 1.5}, whiskerprops={"color": INK2},
                       capprops={"color": INK2}, flierprops={"marker": "o", "ms": 3, "mfc": BLUE_LIGHT,
                                                             "mec": "none"})
    for box in parts["boxes"]:
        box.set(facecolor="#cde2fb", edgecolor=BLUE)
    ax.set_xticks(range(1, 13), MONTHS)
    ax.set_ylabel("среднесуточный " + UNIT)
    who_line(ax)
    ax.legend(loc="upper center")
    save(fig, 6, "Среднесуточный PM2.5 по месяцам")


def fig_mstl(hourly: pd.DataFrame) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(11, 10))
    index = naive(hourly.index)
    trend = hourly["trend"].resample("D").mean()
    axes[0].plot(naive(trend.index), trend, color=BLUE, lw=1.4)
    axes[0].set_title("тренд (ln PM2.5, усреднён по суткам)", loc="left")
    date_axis(axes[0])
    window = (hourly.index >= pd.Timestamp("2025-01-06", tz=prep.TZ)) & (hourly.index < pd.Timestamp("2025-02-03", tz=prep.TZ))
    axes[1].plot(index[window], hourly.loc[window, "s24"], color=BLUE, lw=1.2)
    axes[1].set_title("суточная сезонность, 24 ч (фрагмент 06.01–02.02.2025)", loc="left")
    axes[2].plot(index[window], hourly.loc[window, "s168"], color=ORANGE, lw=1.2)
    axes[2].set_title("недельная сезонность, 168 ч (тот же фрагмент)", loc="left")
    for ax in axes[1:3]:
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    axes[3].plot(index, hourly["resid"], color=MUTED, lw=0.3)
    axes[3].set_title("остаток", loc="left")
    date_axis(axes[3])
    for ax in axes:
        ax.yaxis.set_major_formatter(COMMA)
    fig.tight_layout(h_pad=1.2)
    save(fig, 7, "Разложение MSTL логарифма PM2.5 обучающей части")


def fig_yearly(yearly: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(11, 7.4))
    index = naive(yearly.index)
    axes[0].plot(index, np.exp(yearly["observed"]), color=BLUE_LIGHT, lw=0.8, label="среднесуточный уровень")
    axes[0].plot(index, np.exp(yearly["trend"] + yearly["seasonal"]), color=BLUE, lw=2,
                 label="тренд и годовая сезонность")
    axes[0].plot(index, np.exp(yearly["trend"]), color=INK2, lw=1.2, ls=(0, (4, 3)), label="линейный тренд")
    axes[0].set_ylabel(UNIT)
    axes[0].set_ylim(0, None)
    date_axis(axes[0])
    axes[0].legend(loc="upper right")
    # годовой ход по календарным дням: средний множитель к тренду для каждого дня года
    profile = np.exp(yearly["seasonal"]).groupby(yearly.index.day_of_year).mean()
    axes[1].plot(profile.index, profile, color=ORANGE, lw=2)
    axes[1].axhline(1, color=INK2, lw=1)
    starts = pd.date_range("2025-01-01", periods=12, freq="MS").day_of_year
    axes[1].set_xticks(starts, MONTHS)
    axes[1].set_xlim(1, 366)
    axes[1].set_ylabel("множитель к тренду")
    axes[1].set_title("годовой ход (во сколько раз уровень выше или ниже тренда)", loc="left")
    for ax in axes:
        ax.yaxis.set_major_formatter(COMMA)
    fig.tight_layout(h_pad=1.5)
    save(fig, 8, "Тренд и годовая сезонность среднесуточного PM2.5")


def fig_seasons() -> None:
    seasons = [s for s in EDA["seasons"] if s["hours"] > 3000]  # текущий сезон только начался – не сравниваем
    summers = EDA["summers"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), gridspec_kw={"width_ratios": [len(seasons), len(summers)]},
                             sharey=True)
    for ax, labels, values, color, title in [
        (axes[0], [s["season"] for s in seasons], [s["pm2_5"] for s in seasons], BLUE,
         "отопительный сезон (15.10–15.04)"),
        (axes[1], [str(s["year"]) for s in summers], [s["pm2_5"] for s in summers], ORANGE, "лето (июнь–август)"),
    ]:
        bars = ax.bar(labels, values, width=0.55, color=color)
        for bar, value in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, value + 0.6, num(value, 1), ha="center", va="bottom",
                    color=INK, fontsize=11)
        ax.set_title(title, loc="left")
        ax.grid(axis="x", visible=False)
    for s, bar in zip(seasons, axes[0].patches):
        if s["test"]:
            axes[0].text(bar.get_x() + bar.get_width() / 2, 1, "тест", ha="center", va="bottom", color="white",
                         fontsize=11)
    axes[0].set_ylabel("средний " + UNIT)
    save(fig, 9, "Средний PM2.5 по отопительным сезонам и летом")


def fig_pollutants(frame: pd.DataFrame) -> None:
    monthly = frame[["pm2_5", "no2", "co", "so2"]].resample("MS").mean()
    index = monthly / monthly.mean()
    fig, ax = plt.subplots(figsize=(11, 4.6))
    for column, color, label in [("pm2_5", BLUE, "PM2.5"), ("no2", ORANGE, "NO₂"), ("co", AQUA, "CO"),
                                 ("so2", YELLOW, "SO₂")]:
        ax.plot(naive(index.index), index[column], color=color, marker="o", ms=3.5, label=label)
    ax.axhline(1, color=INK2, lw=1)
    upgrades(ax)
    ax.set_ylabel("среднее за месяц / среднее за весь ряд")
    date_axis(ax)
    ax.yaxis.set_major_formatter(COMMA)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncols=4, frameon=False)
    save(fig, 10, "Сезонный ход загрязнителей по оценке CAMS")


def fig_acf(train: pd.DataFrame) -> None:
    log = np.log(train["pm2_5"]).to_numpy()
    acf_values = eda.acf(log, nlags=336, fft=True)
    pacf_values = pacf(log, nlags=72, method="ywm")
    bound = 1.96 / np.sqrt(len(log))
    fig, axes = plt.subplots(2, 1, figsize=(11, 7))
    for ax, values, title, ticks in [
        (axes[0], acf_values, "автокорреляция (ACF), до 336 ч", range(0, 337, 24)),
        (axes[1], pacf_values, "частная автокорреляция (PACF), до 72 ч", range(0, 73, 6)),
    ]:
        lags = np.arange(len(values))
        ax.vlines(lags, 0, values, color=BLUE, lw=1.2)
        ax.axhspan(-bound, bound, color=WASH, zorder=0)
        ax.axhline(0, color=AXIS, lw=1)
        ax.set_title(title, loc="left")
        ax.set_xticks(list(ticks))
        ax.yaxis.set_major_formatter(COMMA)
    axes[1].set_xlabel("лаг, часов")
    fig.tight_layout(h_pad=1.2)
    save(fig, 11, "Автокорреляция логарифма PM2.5 обучающей части")


def fig_smog(daily: pd.Series) -> None:
    fig, ax = plt.subplots(figsize=(11, 4.4))
    ax.plot(naive(daily.index), daily, color=BLUE, lw=1.1, label="среднесуточный PM2.5")
    smog = daily[daily > prep.SMOG_DAY]
    ax.scatter(naive(smog.index), smog, s=26, color=CRITICAL, edgecolor="white", linewidth=1, zorder=3,
               label=f"смоговые сутки (выше {prep.SMOG_DAY:g} мкг/м³), {len(smog)}")
    ax.axhline(prep.SMOG_DAY, color=CRITICAL, lw=1, ls=(0, (4, 3)))
    who_line(ax)
    upgrades(ax)
    ax.set_ylabel(UNIT)
    ax.set_xlim(naive(daily.index)[0], naive(daily.index)[-1])
    ax.set_ylim(0, None)
    date_axis(ax)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncols=3, frameon=False)
    save(fig, 12, "Смоговые сутки в Алматы")


def fig_weather_corr() -> None:
    names = {"temp": "температура", "rh": "влажность", "dew": "точка росы", "wind": "скорость ветра",
             "pressure": "давление", "precip": "осадки", "cloud": "облачность"}
    corr = EDA["weather"]["spearman"]
    order = sorted(names, key=lambda c: corr["heating"][c])
    y = np.arange(len(order))
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(y + 0.19, [corr["heating"][c] for c in order], height=0.36, color=BLUE, label="отопительный сезон")
    ax.barh(y - 0.19, [corr["summer"][c] for c in order], height=0.36, color=ORANGE, label="лето (июнь–август)")
    ax.set_yticks(y, [names[c] for c in order])
    ax.axvline(0, color=AXIS, lw=1)
    ax.set_xlabel("ранговая корреляция Спирмена с PM2.5")
    ax.xaxis.set_major_formatter(COMMA)
    ax.grid(axis="y", visible=False)
    ax.legend(loc="upper left")
    save(fig, 13, "Связь PM2.5 с погодой")


def fig_wind(frame: pd.DataFrame) -> None:
    part = frame[prep.heating_season(frame.index).notna().to_numpy()]
    edges = [0, 2, 4, 6, 8, 10, 12, 15, 40]
    bins = pd.cut(part["wind"], edges, right=False)
    grouped = part["pm2_5"].groupby(bins, observed=True)
    q25, median, q75 = grouped.quantile(0.25), grouped.median(), grouped.quantile(0.75)
    labels = [f"{a}–{b}" if b < 40 else f"{a}+" for a, b in zip(edges, edges[1:])]
    x = np.arange(len(median))
    fig, ax = plt.subplots(figsize=(9, 4.4))
    ax.fill_between(x, q25, q75, color=BLUE, alpha=0.12, lw=0)
    ax.plot(x, median, color=BLUE, marker="o", ms=5)
    ax.set_xticks(x, labels)
    ax.set_xlabel("скорость ветра, км/ч")
    ax.set_ylabel(UNIT + ", медиана и квартили")
    ax.set_ylim(0, None)
    save(fig, 14, "PM2.5 при разной скорости ветра в отопительный сезон")


def fig_sources() -> None:
    models = json.loads((eda.RESULTS / "sources.json").read_text(encoding="utf-8"))["models"]
    years = sorted(models["era5"], key=int)
    x = np.arange(len(years))
    fig, ax = plt.subplots(figsize=(8, 4.2))
    for key, color, label in [("era5", BLUE, "реанализ ERA5"), ("best_match", ORANGE, "оперативная ECMWF IFS (в ряду)")]:
        values = [models[key][y]["wind"] for y in years]
        ax.plot(x, values, color=color, marker="o", ms=6, label=label)
        ax.text(x[-1] + 0.08, values[-1], num(values[-1], 1), va="center", color=INK, fontsize=11)
    ax.set_xticks(x, [y if y != years[0] else f"{y} (с сентября)" for y in years])
    ax.set_ylabel("средняя скорость ветра, км/ч")
    ax.set_ylim(0, None)
    ax.yaxis.set_major_formatter(COMMA)
    ax.legend(loc="lower left")
    save(fig, 15, "Средняя скорость ветра по годам в ERA5 и IFS")


def main() -> None:
    frame = prep.clean(prep.load())
    train, _ = prep.split(frame)
    daily = prep.daily_mean(frame["pm2_5"])
    hourly = eda.decompose_hourly(train)
    yearly = eda.decompose_daily(train)

    fig_series(frame, daily)
    fig_distribution(train)
    fig_heatmap(frame)
    fig_daily_profile(frame)
    fig_weekday()
    fig_months_box(daily)
    fig_mstl(hourly)
    fig_yearly(yearly)
    fig_seasons()
    fig_pollutants(frame)
    fig_acf(train)
    fig_smog(daily)
    fig_weather_corr()
    fig_wind(frame)
    fig_sources()


if __name__ == "__main__":
    main()
