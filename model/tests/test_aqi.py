import numpy as np

import aqi
import backtest
import final
import prep
import pandas as pd


def test_levels_use_inclusive_upper_bounds():
    values = np.array([0, 9.0, 9.1, 35.4, 35.5, 55.4, 55.5, 125.4, 125.5, 400])
    assert aqi.level(values).tolist() == [0, 0, 1, 1, 2, 2, 3, 3, 4, 4]


def test_scores_on_known_example():
    actual = np.array([[5.0, 20.0, 40.0, 60.0]])
    forecast = np.array([[6.0, 40.0, 30.0, 70.0]])  # угадан 1-й и 4-й час; 2-й и 3-й ошиблись на один уровень
    scores = aqi.scores(actual, forecast)
    assert scores["level_exact"] == 0.5 and scores["level_within_one"] == 1.0
    # смог (> 35,4) фактически в 3-м и 4-м часах, тревога – во 2-м и 4-м: пойман 1 из 2, ложная 1 из 2
    assert scores["smog_hours"] == 2 and scores["smog_caught"] == 0.5 and scores["false_alarms"] == 0.5


def test_scores_without_smog():
    scores = aqi.scores(np.array([[5.0, 10.0]]), np.array([[6.0, 12.0]]))
    assert np.isnan(scores["smog_caught"]) and np.isnan(scores["false_alarms"])


def test_confusion_counts_every_hour():
    actual = np.array([[5.0, 20.0, 40.0]])
    forecast = np.array([[5.0, 40.0, 40.0]])
    matrix = aqi.confusion(actual, forecast)
    assert matrix.sum() == 3 and matrix[0, 0] == 1 and matrix[1, 2] == 1 and matrix[2, 2] == 1


def test_blend_is_geometric_mean():
    index = pd.date_range("2025-01-01", periods=2, freq="6h", tz=prep.TZ)
    actual = np.log(np.full((2, 3), 20.0))
    a = backtest.Result("a", index, np.log(np.full((2, 3), 10.0)), actual)
    b = backtest.Result("b", index, np.log(np.full((2, 3), 40.0)), actual)
    mixed = final.blend("a + b", [a, b])
    assert np.allclose(np.exp(mixed.pred), 20.0) and mixed.origins.equals(index)
