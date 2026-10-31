# образ API; собирается из корня репозитория (make build, Render, состав контекста – .dockerignore):
# нужны код api, отчёты model/reports и лёгкие модели для кнопки «Пересчитать сейчас» (model/light.py и то,
# что он импортирует, prep.py исследования, обученные LSTM в ONNX)
FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY model/reports ./reports
COPY model/light.py model/lstm.py model/baselines.py model/backtest.py model/weather.py research/prep.py ./model/
COPY model/artifacts/live ./model/artifacts/live
COPY backend/api ./api
COPY backend/tests ./tests

# onnxruntime – в один поток: на бесплатном Render доля одного ядра
ENV REPORTS=/app/reports PYTHONPATH=/app/model PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1
# Render передаёт порт в переменной PORT
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
