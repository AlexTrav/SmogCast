import pandas as pd

from .config import COLUMNS, RANGES, START_DATE


# проверка ряда: колонки, непрерывная почасовая шкала UTC с START_DATE, пропуски, диапазоны, свежесть;
# возвращает список найденных проблем (пустой – ряд в порядке)
def check_series(frame: pd.DataFrame, now: pd.Timestamp | None = None, max_age_hours: int | None = None) -> list[str]:
    if list(frame.columns) != COLUMNS:
        return [f"колонки {list(frame.columns)}, ожидались {COLUMNS}"]
    if frame.empty:
        return ["ряд пуст"]

    problems = []
    time = frame["time"]
    start = pd.Timestamp(START_DATE).tz_localize("UTC")
    if time.iloc[0] != start:
        problems.append(f"ряд начинается с {time.iloc[0]}, ожидалось {start}")
    duplicated = time[time.duplicated()]
    if len(duplicated):
        problems.append(f"повторяются часы ({len(duplicated)}), первый – {duplicated.iloc[0]}")
    if not time.is_monotonic_increasing:
        problems.append("часы идут не по порядку")
    steps = time.diff()
    gaps = frame.loc[steps > pd.Timedelta(hours=1), "time"]
    if len(gaps):
        problems.append(f"разрывы шкалы ({len(gaps)}), первый – перед {gaps.iloc[0]}")

    for column, (low, high) in RANGES.items():
        values = frame[column]
        missing = int(values.isna().sum())
        if missing:
            problems.append(f"{column}: пропусков {missing}")
        outside = values[(values < low) | (values > high)]
        if len(outside):
            problems.append(f"{column}: {len(outside)} значений вне [{low}; {high}], например {outside.iloc[0]}")

    if max_age_hours is not None:
        now = now if now is not None else pd.Timestamp.now(tz="UTC")
        age = (now - time.iloc[-1]) / pd.Timedelta(hours=1)
        if age > max_age_hours:
            problems.append(f"последний час {time.iloc[-1]} старше {max_age_hours} ч")
    return problems


# сводка для вывода в консоль: период и минимум/среднее/максимум по колонкам
def summary(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "ряд пуст"
    lines = [f"часов: {len(frame)}, с {frame['time'].iloc[0]} по {frame['time'].iloc[-1]} (UTC)", ""]
    lines.append(f"{'колонка':10} {'мин':>9} {'среднее':>9} {'макс':>9}")
    for column in COLUMNS[1:]:
        values = frame[column]
        lines.append(f"{column:10} {values.min():9.1f} {values.mean():9.1f} {values.max():9.1f}")
    return "\n".join(lines)
