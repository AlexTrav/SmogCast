# образ только с зависимостями моделей; код моделей и исследования (prep.py, style.py) и ряд подключаются с хоста
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/mpl PYTHONPATH=/research
WORKDIR /model

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
