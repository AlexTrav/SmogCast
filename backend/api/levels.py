"""Индекс US AQI по PM2.5 (EPA, редакция 2024) – та же шкала, что в model/aqi.py, но с шестью уровнями
и самим числом индекса 0–500, как его показывают IQAir и AirNow."""

# (концентрация от, до в мкг/м³, индекс от, до, ключ уровня); концентрация усекается до 0,1
BREAKPOINTS = (
    (0.0, 9.0, 0, 50, "good"),
    (9.1, 35.4, 51, 100, "moderate"),
    (35.5, 55.4, 101, 150, "sensitive"),
    (55.5, 125.4, 151, 200, "unhealthy"),
    (125.5, 225.4, 201, 300, "very_unhealthy"),
    (225.5, 325.4, 301, 500, "hazardous"),
)


def _row(value: float) -> tuple:
    c = int(max(value, 0.0) * 10) / 10
    for row in BREAKPOINTS:
        if c <= row[1]:
            return c, row
    return c, BREAKPOINTS[-1]


def aqi(value: float) -> int:
    c, (c_lo, c_hi, i_lo, i_hi, _) = _row(value)
    if c > c_hi:
        return i_hi
    return round((i_hi - i_lo) / (c_hi - c_lo) * (c - c_lo) + i_lo)


def level(value: float) -> str:
    return _row(value)[1][4]
