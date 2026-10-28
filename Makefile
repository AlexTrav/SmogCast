.PHONY: data check test

# дописать свежие часы ряда PM2.5 и погоды из Open-Meteo и проверить его
data:
	"$(MAKE)" -C data update

# проверить ряд, как в CI
check:
	"$(MAKE)" -C data check

# все автотесты
test:
	"$(MAKE)" -C data test
