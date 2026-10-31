.PHONY: build run test readonly

IMAGE := smogcast-api

export MSYS_NO_PATHCONV=1

# контекст сборки – корень репозитория (в образ идут отчёты model/reports)
build:
	docker build -f Dockerfile -t $(IMAGE) ..

# строка подключения API: пользователь только для чтения (SmogCast/.env.api после make readonly),
# пока его нет – владелец базы из SmogCast/.env
ENV_FILE := $(if $(wildcard $(CURDIR)/../.env.api),$(CURDIR)/../.env.api,$(CURDIR)/../.env)

# API локально на http://localhost:8000 (документация – /docs)
run: build
	docker run --rm --env-file "$(ENV_FILE)" -p 8000:8000 $(IMAGE)

# один раз (или чтобы сменить пароль): пользователь базы только для чтения -> SmogCast/.env.api
readonly: build
	docker run --rm --env-file "$(CURDIR)/../.env" -v "$(CURDIR)/readonly.py:/app/readonly.py:ro" 		-v "$(CURDIR)/..:/out" $(IMAGE) python readonly.py

# pytest: точки API на временном Postgres 18 в docker compose
test:
	docker compose -f compose.test.yml run --rm --build tests; \
	status=$$?; docker compose -f compose.test.yml down -v; exit $$status
