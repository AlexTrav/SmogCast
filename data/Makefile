.PHONY: build update full check test clean

IMAGE := smogcast-data

# Git Bash на Windows иначе превращает пути контейнера (/data/series) в пути Windows
export MSYS_NO_PATHCONV=1

# ряд монтируется с хоста – результат сбора остаётся в папке data/series
RUN := docker run --rm -v "$(CURDIR)/series:/data/series" $(IMAGE)

# собрать образ со скриптами сбора
build:
	docker build -t $(IMAGE) .

# дописать свежие часы (последние 7 дней перезапрашиваются) и проверить ряд
update: build
	$(RUN) update

# выгрузить весь ряд заново с 01.09.2022
full: build
	$(RUN) full

# проверить ряд: непрерывная шкала, пропуски, диапазоны значений
check: build
	docker run --rm -v "$(CURDIR)/series:/data/series:ro" $(IMAGE) check

# pytest сбора и проверки (без обращения к сети)
test: build
	docker run --rm --entrypoint python $(IMAGE) -m pytest -q tests

# удалить образ (ряд в series/ остаётся)
clean:
	docker rmi -f $(IMAGE)
