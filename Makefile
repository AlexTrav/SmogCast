.PHONY: data check test

# дописать свежие часы ряда PM2.5 и погоды из Open-Meteo и проверить его
data:
	"$(MAKE)" -C data update

# проверить ряд, как в CI
check:
	"$(MAKE)" -C data check

# все автотесты: сбор и база, исследование, каркас проверки и модели
test:
	"$(MAKE)" -C data test
	"$(MAKE)" -C research test
	"$(MAKE)" -C model test
