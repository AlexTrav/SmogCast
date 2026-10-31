# образ только с зависимостями моделей; код моделей и исследования (prep.py, style.py) и ряд подключаются с хоста
FROM python:3.12-slim

# перебор моделей идёт параллельно процессами – по одному потоку BLAS на процесс, без переподписки ядер
ENV PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/mpl PYTHONPATH=/research \
    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
WORKDIR /model

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
