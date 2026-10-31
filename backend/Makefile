.PHONY: build run test

IMAGE := smogcast-api

export MSYS_NO_PATHCONV=1

# контекст сборки – корень репозитория (в образ идут отчёты model/reports)
build:
	docker build -f Dockerfile -t $(IMAGE) ..

# API локально на http://localhost:8000 (документация – /docs); строка подключения – из SmogCast/.env
run: build
	docker run --rm --env-file "$(CURDIR)/../.env" -p 8000:8000 $(IMAGE)

# pytest: точки API на временном Postgres 18 в docker compose
test:
	docker compose -f compose.test.yml run --rm --build tests; \
	status=$$?; docker compose -f compose.test.yml down -v; exit $$status
