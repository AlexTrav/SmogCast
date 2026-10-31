"""Исследование ряда PM2.5 (шаг 2): описательная статистика, сезонность, тренды, стационарность, аномалии,
связь с погодой. Результат – results/eda.json; рисунки строит figures.py.

    make -C research eda
"""
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.tsa.seasonal import MSTL
from statsmodels.tsa.stattools import acf, adfuller, kpss

import prep

RESULTS = Path(__file__).resolve().parent / "results"
WEATHER = ["temp", "rh", "dew", "wind", "pressure", "precip", "cloud"]


def r(value: float, digits: int = 2) -> float:
    return round(float(value), digits)


# MSTL логарифма PM2.5 обучающей части: тренд, суточная (24 ч) и недельная (168 ч) сезонность, остаток
def decompose_hourly(train: pd.DataFrame) -> pd.DataFrame:
    log = np.log(train["pm2_5"])
    result = MSTL(log.to_numpy(), periods=(24, 168), stl_kwargs={"robust": True}).fit()
    seasonal = np.asarray(result.seasonal)
    return pd.DataFrame({
        "observed": log.to_numpy(),
        "trend": result.trend,
        "s24": seasonal[:, 0],
        "s168": seasonal[:, 1],
        "resid": result.resid,
    }, index=train.index)


# годовой ход среднесуточного логарифма: регрессия на линейный тренд и harmonics годовых гармоник.
# STL с периодом 365 здесь не годится: в обучающей части три года, и сезонная компонента повторяет
# сами данные вместо среднего годового хода; наклон тренда (в долях за год) – в attrs["slope"]
def decompose_daily(train: pd.DataFrame, harmonics: int = 3) -> pd.DataFrame:
    daily = prep.daily_mean(np.log(train["pm2_5"]))
    years = np.asarray((daily.index - daily.index[0]) / pd.Timedelta(days=365.25), dtype=float)
    waves = [f(2 * np.pi * k * years) for k in range(1, harmonics + 1) for f in (np.sin, np.cos)]
    design = np.column_stack([np.ones_like(years), years, *waves])
    coef, *_ = np.linalg.lstsq(design, daily.to_numpy(), rcond=None)
    trend, seasonal = design[:, :2] @ coef[:2], design[:, 2:] @ coef[2:]
    result = pd.DataFrame({"observed": daily, "trend": trend, "seasonal": seasonal,
                           "resid": daily.to_numpy() - trend - seasonal}, index=daily.index)
    result.attrs["slope"] = float(coef[1])
    return result


def describe(values: pd.Series) -> dict:
    return {"mean": r(values.mean(), 1), "median": r(values.median(), 1), "p95": r(values.quantile(0.95), 1),
            "max": r(values.max(), 1), "skew": r(stats.skew(values)), "n": int(len(values))}


# ADF (H0: единичный корень) и KPSS (H0: стационарность); p-значения KPSS табличные – за пределами таблицы
# statsmodels возвращает границу, поэтому предупреждение глушится и сохраняется как есть
def stationarity(values: pd.Series) -> dict:
    values = values.dropna().to_numpy()
    adf_stat, adf_p, *_ = adfuller(values, maxlag=48, autolag="AIC", result_object=False)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        kpss_stat, kpss_p, *_ = kpss(values, regression="c", nlags="auto")
    return {"adf_stat": r(adf_stat), "adf_p": r(adf_p, 4), "kpss_stat": r(kpss_stat, 3), "kpss_p": r(kpss_p, 3)}


def seasons_table(frame: pd.DataFrame) -> list[dict]:
    labels = prep.heating_season(frame.index)
    daily = prep.daily_mean(frame["pm2_5"])
    daily_labels = prep.heating_season(daily.index)
    rows = []
    for season in sorted(labels.dropna().unique()):
        part = frame[labels == season]
        days = daily[daily_labels == season]
        rows.append({
            "season": season,
            "hours": int(len(part)),
            "test": bool(part.index[0] >= prep.TEST_START),
            **{column: r(part[column].mean(), 1) for column in ["pm2_5", "no2", "co", "so2", "temp", "wind", "rh"]},
            "days_over_who": r((days > prep.WHO_24H).mean(), 3),
            "smog_days": int((days > prep.SMOG_DAY).sum()),
        })
    return rows


def summers_table(frame: pd.DataFrame) -> list[dict]:
    summer = frame[frame.index.month.isin([6, 7, 8])]
    rows = []
    for year, part in summer.groupby(summer.index.year):
        rows.append({"year": int(year), **{c: r(part[c].mean(), 1) for c in ["pm2_5", "no2", "co", "dust", "temp"]}})
    return rows


# средние загрязнителей по циклам модели CAMS отдельно для зимы и лета – чтобы сезон не смешивался со сменой модели
def cycles_table(frame: pd.DataFrame) -> list[dict]:
    cycles = prep.cams_cycle(frame.index)
    daily = prep.daily_mean(frame["pm2_5"])
    daily_cycles = prep.cams_cycle(daily.index)
    rows = []
    for name, start in prep.CAMS_CYCLES:
        part = frame[cycles == name]
        row = {"cycle": name, "from": part.index[0].date().isoformat(), "to": part.index[-1].date().isoformat(),
               "smog_days": int((daily[daily_cycles == name] > prep.SMOG_DAY).sum())}
        for season, months in [("winter", [12, 1, 2]), ("summer", [6, 7, 8])]:
            months_part = part[part.index.month.isin(months)]
            row[season] = ({c: r(months_part[c].mean(), 1) for c in ["pm2_5", "no2", "co", "so2", "temp", "wind"]}
                           | {"hours": int(len(months_part))}) if len(months_part) else None
        rows.append(row)
    return rows


# средние в новогоднюю ночь (31.12 22:00 – 01.01 04:00) и на Наурыз (21–23 марта) против соседних дней
def holidays(frame: pd.DataFrame) -> dict:
    pm = frame["pm2_5"]
    night = pm[(pm.index.hour >= 22) | (pm.index.hour <= 4)]
    new_year, nauryz = [], []
    for year in sorted(set(pm.index.year)):
        ny = night[((night.index.month == 12) & (night.index.day == 31) & (night.index.year == year - 1)
                    & (night.index.hour >= 22))
                   | ((night.index.month == 1) & (night.index.day == 1) & (night.index.year == year)
                      & (night.index.hour <= 4))]
        around = night[((night.index.year == year - 1) & (night.index.month == 12) & night.index.day.isin(range(24, 31)))
                       | ((night.index.year == year) & (night.index.month == 1) & night.index.day.isin(range(2, 8)))]
        if len(ny) == 7 and len(around):
            new_year.append({"year": int(year), "night": r(ny.mean(), 1), "around": r(around.mean(), 1),
                             "ratio": r(ny.mean() / around.mean())})
        march = pm[(pm.index.year == year) & (pm.index.month == 3)]
        if len(march):
            holiday = march[march.index.day.isin([21, 22, 23])]
            near = march[march.index.day.isin(list(range(14, 21)) + list(range(24, 31)))]
            nauryz.append({"year": int(year), "holiday": r(holiday.mean(), 1), "around": r(near.mean(), 1),
                           "ratio": r(holiday.mean() / near.mean())})
    return {"new_year_night": new_year, "nauryz": nauryz}


# ранговая корреляция PM2.5 с погодой в отопительный сезон и летом (июнь–август) и лаг максимальной связи
def weather_links(frame: pd.DataFrame) -> dict:
    heating = prep.heating_season(frame.index).notna().to_numpy()
    summer = frame.index.month.isin([6, 7, 8])
    out = {"spearman": {}, "lags": {}}
    for name, mask in [("heating", heating), ("summer", summer)]:
        part = frame[mask]
        out["spearman"][name] = {c: r(stats.spearmanr(part["pm2_5"], part[c]).statistic) for c in WEATHER}
    part = frame[heating]
    for column in ["wind", "temp", "rh"]:
        corr = {k: part["pm2_5"].corr(part[column].shift(k), method="spearman") for k in range(0, 49, 3)}
        best = max(corr, key=lambda k: abs(corr[k]))
        out["lags"][column] = {"best_lag_h": best, "corr": r(corr[best]), "corr_lag0": r(corr[0])}
    return out


def main() -> None:
    raw = prep.load()
    glitch = prep.glitches(raw)
    frame = prep.clean(raw)
    train, test = prep.split(frame)
    pm = frame["pm2_5"]
    heating = prep.heating_season(frame.index).notna()
    daily = prep.daily_mean(pm)

    print("MSTL почасового ряда (обучающая часть)…")
    hourly = decompose_hourly(train)
    print("годовой ход среднесуточного ряда (тренд и гармоники)…")
    yearly = decompose_daily(train)

    log_train = np.log(train["pm2_5"])
    acf_values = acf(log_train.to_numpy(), nlags=336, fft=True)
    outliers = prep.robust_outliers(pd.Series(hourly["resid"].to_numpy(), index=hourly.index))
    smog = prep.episodes(daily)

    result = {
        "cams_glitch": {"hours": int(glitch.sum()), "from": raw.index[glitch][0].isoformat(),
                        "to": raw.index[glitch][-1].isoformat()},
        "snapshot": {
            "start": frame.index[0].isoformat(), "end": frame.index[-1].isoformat(), "hours": int(len(frame)),
            "test_start": prep.TEST_START.tz_convert(prep.TZ).isoformat(),
            "train_hours": int(len(train)), "test_hours": int(len(test)),
        },
        "describe": {
            "all": describe(pm), "heating": describe(pm[heating]), "non_heating": describe(pm[~heating]),
            "train_skew_raw": r(stats.skew(train["pm2_5"])), "train_skew_log": r(stats.skew(log_train)),
        },
        "who": {
            "days": int(len(daily)), "days_over_24h": int((daily > prep.WHO_24H).sum()),
            "share_over_24h": r((daily > prep.WHO_24H).mean(), 3), "smog_days": int((daily > prep.SMOG_DAY).sum()),
            "mean_over_year_norm": r(pm.mean() / prep.WHO_YEAR, 1),
        },
        "monthly_mean": {int(m): r(v, 1) for m, v in pm.groupby(pm.index.month).mean().items()},
        "hourly_profile": {
            "winter": {int(h): r(v, 1) for h, v in pm[pm.index.month.isin([12, 1, 2])].groupby(
                lambda t: t.hour).mean().items()},
            "summer": {int(h): r(v, 1) for h, v in pm[pm.index.month.isin([6, 7, 8])].groupby(
                lambda t: t.hour).mean().items()},
        },
        "weekday_mean": {
            name: {int(d): r(v, 1) for d, v in pm[mask].groupby(pm[mask].index.day_of_week).mean().items()}
            for name, mask in [("heating", heating.to_numpy()), ("non_heating", ~heating.to_numpy())]
        },
        "seasons": seasons_table(frame),
        "summers": summers_table(frame),
        "cams_cycles": cycles_table(frame),
        "decomposition": {
            "hourly_strength": {
                "trend": r(prep.strength(hourly["trend"], hourly["resid"])),
                "daily_24h": r(prep.strength(hourly["s24"], hourly["resid"])),
                "weekly_168h": r(prep.strength(hourly["s168"], hourly["resid"])),
            },
            "daily_strength": {
                "trend": r(prep.strength(yearly["trend"], yearly["resid"])),
                "yearly": r(prep.strength(yearly["seasonal"], yearly["resid"])),
                "trend_per_year_pct": r((np.exp(yearly.attrs["slope"]) - 1) * 100, 1),
            },
            # размах среднего профиля компоненты (по часу суток, по часу недели, по году) в единицах ln PM2.5
            "amplitude_log": {
                "daily_24h": r(np.ptp(hourly["s24"].groupby(hourly.index.hour).mean())),
                "weekly_168h": r(np.ptp(hourly["s168"].groupby(
                    hourly.index.day_of_week * 24 + hourly.index.hour).mean())),
                "yearly": r(np.ptp(yearly["seasonal"])),
            },
        },
        "stationarity_train_log": {
            "level": stationarity(log_train),
            "diff_1h": stationarity(log_train.diff()),
            "diff_24h": stationarity(log_train.diff(24)),
        },
        "acf_train_log": {str(k): r(acf_values[k], 3) for k in [1, 2, 3, 6, 12, 24, 48, 72, 168, 336]},
        "anomalies": {
            "smog_episodes": len(smog),
            "top_episodes": smog.sort_values("peak", ascending=False).head(10).to_dict("records"),
            "resid_outliers_hours": int(outliers.sum()),
            "resid_outliers_share": r(outliers.mean(), 4),
            "dust_hours_over_100": int((frame["dust"] > 100).sum()),
            "pm10_days_over_100": int((prep.daily_mean(frame["pm10"]) > 100).sum()),
            "pm25_to_pm10": {"heating": r((frame["pm2_5"] / frame["pm10"])[heating].median()),
                             "non_heating": r((frame["pm2_5"] / frame["pm10"])[~heating].median())},
        },
        "holidays": holidays(frame),
        "weather": weather_links(frame),
    }
    # погода в смоговые сутки против остальных суток отопительного сезона
    days = frame[WEATHER].resample("D").mean().loc[daily.index]
    smog_days = daily > prep.SMOG_DAY
    heating_days = prep.heating_season(daily.index).notna()
    result["weather"]["smog_days_vs_heating"] = {
        c: {"smog": r(days.loc[smog_days, c].mean(), 1), "heating": r(days.loc[heating_days & ~smog_days, c].mean(), 1)}
        for c in WEATHER
    }

    RESULTS.mkdir(exist_ok=True)
    path = RESULTS / "eda.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"сохранено: {path.name}")
    print(json.dumps({k: result[k] for k in ["snapshot", "describe", "who", "decomposition"]}, ensure_ascii=False,
                     indent=1))


if __name__ == "__main__":
    main()
