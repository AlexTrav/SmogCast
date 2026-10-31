.PHONY: test build run dev lock shots stop clean e2e e2e-update e2e-lock

IMAGE := smogcast-frontend
CONTAINER := smogcast-frontend

# Git Bash на Windows иначе превращает пути контейнера в пути Windows
export MSYS_NO_PATHCONV=1

# автотесты Vitest в контейнере (локально node_modules не нужен)
test:
	docker build --target test -t $(IMAGE)-test .
	docker run --rm $(IMAGE)-test

# собрать образ: проверка типов, сборка Vite, nginx; API=<адрес> – другой API вместо Render
# (например, make run API=http://localhost:8000 вместе с make -C backend run)
build:
	docker build $(if $(API),--build-arg VITE_API_BASE_URL=$(API)) -t $(IMAGE) .

# собранный сайт на http://localhost:8080 (данные – API на Render)
run: build
	docker run --rm -d -p 8080:80 --name $(CONTAINER) $(IMAGE)

# dev-сервер Vite с горячей перезагрузкой на http://localhost:5173; node_modules живёт в томе контейнера
dev:
	docker run --rm -it -p 5173:5173 -e VITE_USE_POLLING=1 -v "$(CURDIR):/app" -v /app/node_modules -w /app \
		node:24-alpine sh -c "npm ci --no-audit --no-fund && npm run dev"

# обновить package-lock.json после правки package.json (без node_modules на диске)
lock:
	docker run --rm -v "$(CURDIR):/app" -w /app node:24-alpine npm install --package-lock-only --no-audit --no-fund

# браузерные тесты Playwright: собранный сайт и Chromium в docker compose, API подменён сохранёнными ответами
# (e2e/fixtures); упавшие тесты – трассы и скриншоты в e2e/test-results
E2E := docker compose -f e2e/compose.yml
e2e:
	$(E2E) run --rm --build e2e; status=$$?; $(E2E) down; exit $$status

# переснять эталонные скриншоты после намеренной правки дизайна (e2e/snapshots)
e2e-update:
	$(E2E) run --rm --build e2e npx playwright test visual --update-snapshots; status=$$?; $(E2E) down; exit $$status

# обновить e2e/package-lock.json после правки e2e/package.json
e2e-lock:
	docker run --rm -v "$(CURDIR)/e2e:/e2e" -w /e2e mcr.microsoft.com/playwright:v1.49.1-noble npm install --package-lock-only --no-audit --no-fund

stop:
	docker stop $(CONTAINER)

clean:
	docker rmi -f $(IMAGE) $(IMAGE)-test
