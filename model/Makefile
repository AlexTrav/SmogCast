.PHONY: build baselines figures test

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

# рисунки по сохранённым отчётам; шрифт Times New Roman – из Windows
figures: build
	docker run --rm -v "$(CURDIR):/model" -v "$(CURDIR)/../research:/research:ro" -v "$(FIGURES):/figures" \
		-v "C:/Windows/Fonts:/winfonts:ro" $(IMAGE) python figures.py

# pytest каркаса проверки и моделей (без ряда и сети)
test: build
	$(RUN) python -m pytest -q -p no:cacheprovider tests
