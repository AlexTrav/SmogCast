.PHONY: build eda sources figures test all

IMAGE := smogcast-research

# Git Bash на Windows иначе превращает пути контейнера в пути Windows
export MSYS_NO_PATHCONV=1

# рисунки – в папку отчёта, если передана: make figures FIGURES=/путь/к/Рисункам
FIGURES ?= $(CURDIR)/figures
# код исследования и снимок ряда – с хоста (ряд только для чтения)
RUN := docker run --rm -v "$(CURDIR):/research" -v "$(CURDIR)/../data/series:/series:ro" $(IMAGE)

build:
	docker build -t $(IMAGE) .

# статистика ряда -> results/eda.json
eda: build
	$(RUN) python eda.py

# ветер и температура по годам в ERA5 и ECMWF IFS (запрос к Open-Meteo) -> results/sources.json
sources: build
	$(RUN) python sources.py

# рисунки по снимку ряда и results/eda.json; шрифт Times New Roman – из Windows
figures: build
	docker run --rm -v "$(CURDIR):/research" -v "$(CURDIR)/../data/series:/series:ro" -v "$(FIGURES):/figures" \
		-v "C:/Windows/Fonts:/winfonts:ro" $(IMAGE) python figures.py

# pytest вспомогательных функций (без ряда и сети)
test: build
	$(RUN) python -m pytest -q -p no:cacheprovider tests

all: eda sources figures
