.PHONY: build update full check seed hourly test clean

IMAGE := smogcast-data

# Git Bash на Windows иначе превращает пути контейнера (/data/series) в пути Windows
export MSYS_NO_PATHCONV=1

# ряд монтируется с хоста – результат сбора остаётся в папке data/series
RUN := docker run --rm -v "$(CURDIR)/series:/data/series" $(IMAGE)
# строка подключения к базе – из SmogCast/.env (в git не попадает); сам файл в образ не копируется
DB := docker run --rm --env-file "$(CURDIR)/../.env" $(IMAGE)

# собрать образ со скриптами сбора
build:
	docker build -t $(IMAGE) .

# дописать свежие часы в CSV (последние 7 дней перезапрашиваются) и проверить ряд
update: build
	$(RUN) update

# выгрузить весь ряд в CSV заново с 01.09.2022
full: build
	$(RUN) full

# проверить ряд в CSV: непрерывная шкала, пропуски, диапазоны значений
check: build
	docker run --rm -v "$(CURDIR)/series:/data/series:ro" $(IMAGE) check

# один раз: создать таблицы в базе и загрузить в неё ряд из CSV
seed: build
	docker run --rm --env-file "$(CURDIR)/../.env" -v "$(CURDIR)/series:/data/series:ro" $(IMAGE) seed

# ежечасный запуск вручную (по расписанию его делает GitHub Actions): ряд, снимки прогнозов, журнал
hourly: build
	$(DB) hourly

# pytest: сбор и проверка ряда без сети, база – на временном Postgres 18 в docker compose
test:
	docker compose -f compose.test.yml run --rm --build tests; \
	status=$$?; docker compose -f compose.test.yml down -v; exit $$status

# удалить образ (ряд в series/ остаётся)
clean:
	docker rmi -f $(IMAGE)
