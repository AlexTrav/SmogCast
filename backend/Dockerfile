# образ API; собирается из корня репозитория (make build, Render): нужны код api и отчёты model/reports
FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY model/reports ./reports
COPY backend/api ./api
COPY backend/tests ./tests

ENV REPORTS=/app/reports PYTHONUNBUFFERED=1
# Render передаёт порт в переменной PORT
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
