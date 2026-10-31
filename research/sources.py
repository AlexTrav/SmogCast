"""Однородность погодных данных: средние ветер и температура по годам в реанализе ERA5 и в оперативной
модели ECMWF IFS (её Open-Meteo отдаёт как best_match – она и лежит в ряду). Результат – results/sources.json.

    make -C research sources
"""
import json
import urllib.parse
import urllib.request
from collections import defaultdict

import eda

URL = "https://archive-api.open-meteo.com/v1/archive"
MODELS = {"best_match": "best_match (в ряду)", "era5": "ERA5", "ecmwf_ifs": "ECMWF IFS"}


def yearly(model: str) -> dict:
    params = {"latitude": 43.25, "longitude": 76.92, "start_date": "2022-09-01", "end_date": "2026-10-20",
              "hourly": "wind_speed_10m,temperature_2m", "models": model, "timezone": "GMT"}
    request = urllib.request.Request(f"{URL}?{urllib.parse.urlencode(params)}",
                                     headers={"User-Agent": "SmogCast-research/1.0 (student project)"})
    with urllib.request.urlopen(request, timeout=120) as response:
        hourly = json.load(response)["hourly"]
    sums = defaultdict(lambda: [0.0, 0.0, 0])
    for time, wind, temp in zip(hourly["time"], hourly["wind_speed_10m"], hourly["temperature_2m"]):
        if wind is None or temp is None:
            continue
        acc = sums[int(time[:4])]
        acc[0] += wind
        acc[1] += temp
        acc[2] += 1
    return {year: {"wind": round(w / n, 2), "temp": round(t / n, 2), "hours": n} for year, (w, t, n) in sorted(sums.items())}


def main() -> None:
    result = {"period": "2022-09-01 – 2026-10-20 (UTC)", "models": {m: yearly(m) for m in MODELS}}
    path = eda.RESULTS / "sources.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
