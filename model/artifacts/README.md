# Модели LSTM (ONNX)

Обученные в Google Colab модели по режимам обучения, в каждой папке – `lstm.onnx` и `lstm_weather.onnx`,
рядом `*.json` – нормировка признаков, дата окончания обучения и ход ранней остановки:

| Папка | Обучение до | Для чего | Ноутбук |
|---|---|---|---|
| `validation/` | 01.10.2024 | подбор и проверка на валидации (`make -C model lstm`) | [notebooks/lstm_validation.ipynb](../notebooks/lstm_validation.ipynb) |
| `test/` | 01.10.2025 | итоговая проверка на отложенном тестовом годе | [notebooks/lstm_test_live.ipynb](../notebooks/lstm_test_live.ipynb) |
| `live/` | конец снимка ряда | прогнозы на сайте | [notebooks/lstm_test_live.ipynb](../notebooks/lstm_test_live.ipynb) |

Архив из ноутбука (`lstm_<режимы>_<дата>.zip`) распаковывается сюда целиком – папки режимов создаются сами.
