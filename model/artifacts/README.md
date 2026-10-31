# Модели LSTM (ONNX)

Сюда распаковывается `lstm_artifacts.zip` из ноутбука [notebooks/lstm.ipynb](../notebooks/lstm.ipynb):
`lstm.onnx` и `lstm_weather.onnx` – обученные в Google Colab модели, рядом `*.json` – нормировка признаков,
дата окончания обучения и ход ранней остановки. Проверка на валидации – `make -C model lstm`.
