.PHONY: build baselines arima-orders arima prophet weather lstm select final figures test

IMAGE := smogcast-model

# Git Bash на Windows иначе превращает пути контейнера в пути Windows
export MSYS_NO_PATHCONV=1

# часть ряда для проверки: validation (по умолчанию) или test – только на итоговом сравнении
PERIOD ?= validation
# рисунки – в папку отчёта, если передана: make figures FIGURES=/путь/к/Рисункам
FIGURES ?= $(CURDIR)/figures
# код моделей, общий код исследования (снимок ряда, оформление рисунков) и сам ряд – с хоста
RUN := docker run --rm -v "$(CURDIR):/model" -v "$(CURDIR)/../research:/research:ro" \
	-v "$(CURDIR)/../data/series:/series:ro" $(IMAGE)

build:
	docker build -t $(IMAGE) .

# базовые модели на скользящей проверке -> reports/baselines/$(PERIOD).json
baselines: build
	$(RUN) python baselines.py --period $(PERIOD)

# ARIMA: подбор порядков по AIC на обучающей части (около 15 минут) -> reports/arima/orders.json
arima-orders: build
	$(RUN) python arima.py orders

# ARIMA: окна 28/56/90 дней на валидации и интервалы для лучших (до получаса) -> reports/arima/validation.json
arima: build
	$(RUN) python arima.py validate

# Prophet: 5 вариантов на валидации и интервалы для лучшего (около 15 минут) -> reports/prophet/validation.json
prophet: build
	$(RUN) python -W ignore prophet_model.py

# помогает ли прогноз погоды: ARIMA и Prophet с погодой и без, окна ARIMA до 365 суток (около 30 минут)
# -> reports/weather/validation.json; нужен архив прогнозов data/series/weather_prev.csv (make -C ../data prev)
weather: build
	$(RUN) python -W ignore compare_weather.py

# LSTM, обученная в Colab (notebooks/lstm.ipynb -> artifacts/*.onnx): проверка на валидации (около минуты)
# -> reports/lstm/validation.json
lstm: build
	$(RUN) python -W ignore lstm_eval.py

# выбор модели по умолчанию (одна модель или смесь) на валидации – до теста (около 10 минут)
# -> reports/final/selection.json
select: build
	$(RUN) python -W ignore final.py select

# итог на отложенном тестовом годе – только после select (около 10 минут) -> reports/final/test.json
final: build
	$(RUN) python -W ignore final.py final

# рисунки по сохранённым отчётам; шрифт Times New Roman – из Windows
figures: build
	docker run --rm -v "$(CURDIR):/model" -v "$(CURDIR)/../research:/research:ro" -v "$(FIGURES):/figures" \
		-v "$(CURDIR)/../data/series:/series:ro" -v "C:/Windows/Fonts:/winfonts:ro" $(IMAGE) python -W ignore figures.py

# pytest каркаса проверки и моделей (без ряда и сети)
test: build
	$(RUN) python -m pytest -q -p no:cacheprovider tests
