.PHONY: data check test api

# дописать свежие часы ряда PM2.5 и погоды из Open-Meteo и проверить его
data:
	"$(MAKE)" -C data update

# проверить ряд, как в CI
check:
	"$(MAKE)" -C data check

# все автотесты: сбор и база, исследование, каркас проверки и модели, API
test:
	"$(MAKE)" -C data test
	"$(MAKE)" -C research test
	"$(MAKE)" -C model test
	"$(MAKE)" -C backend test

# API локально на http://localhost:8000 (база – из .env)
api:
	"$(MAKE)" -C backend run
