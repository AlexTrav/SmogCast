"""Уровни качества воздуха по PM2.5 – шкала US AQI (EPA, редакция 2024), её же показывает IQAir.

Верхние границы уровней включительно: хорошо ≤ 9,0; умеренно ≤ 35,4; вредно для чувствительных групп ≤ 55,4;
вредно ≤ 125,4; очень вредно и опасно – выше. Отдельно на графиках – суточная норма ВОЗ 15 мкг/м³.
"""
import numpy as np

BREAKS = (9.0, 35.4, 55.4, 125.4)
LEVELS = ("хорошо", "умеренно", "вредно для чувствительных", "вредно", "очень вредно")
SMOG = 35.4  # «смог» для понятных мер: воздух вредный хотя бы для чувствительных групп


# номер уровня 0…4 для концентраций в мкг/м³
def level(values: np.ndarray) -> np.ndarray:
    return np.digitize(np.asarray(values, dtype=float), BREAKS, right=True)


# понятные меры по прогнозам и фактам в мкг/м³ (форма – прогнозы × часы горизонта):
# доля часов, где уровень угадан точно и с ошибкой не больше чем на один уровень; для смога (выше SMOG) –
# какую долю часов со смогом модель предсказала и какая доля её тревог оказалась ложной
def scores(actual: np.ndarray, forecast: np.ndarray) -> dict:
    true_level, pred_level = level(actual), level(forecast)
    smog, alarm = actual > SMOG, forecast > SMOG
    hits = int((smog & alarm).sum())
    return {
        "level_exact": float((true_level == pred_level).mean()),
        "level_within_one": float((np.abs(true_level - pred_level) <= 1).mean()),
        "smog_hours": int(smog.sum()),
        "smog_caught": hits / int(smog.sum()) if smog.any() else float("nan"),
        "false_alarms": int((alarm & ~smog).sum()) / int(alarm.sum()) if alarm.any() else float("nan"),
    }


# матрица уровней: строки – фактический уровень, столбцы – предсказанный (число часов)
def confusion(actual: np.ndarray, forecast: np.ndarray) -> np.ndarray:
    matrix = np.zeros((len(LEVELS), len(LEVELS)), dtype=int)
    np.add.at(matrix, (level(actual).ravel(), level(forecast).ravel()), 1)
    return matrix
