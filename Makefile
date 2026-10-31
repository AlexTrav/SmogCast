.PHONY: data check test api site

# дописать свежие часы ряда PM2.5 и погоды из Open-Meteo и проверить его
data:
	"$(MAKE)" -C data update

# проверить ряд, как в CI
check:
	"$(MAKE)" -C data check

# все автотесты: сбор и база, исследование, каркас проверки и модели, API, сайт
test:
	"$(MAKE)" -C data test
	"$(MAKE)" -C research test
	"$(MAKE)" -C model test
	"$(MAKE)" -C backend test
	"$(MAKE)" -C frontend test

# API локально на http://localhost:8000 (база – из .env)
api:
	"$(MAKE)" -C backend run

# сайт локально на http://localhost:5173 (dev-сервер, данные – API на Render)
site:
	"$(MAKE)" -C frontend dev
