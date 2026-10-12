FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data \
    TZ=UTC

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.yaml .
COPY fabrica ./fabrica

# Datos, liga y resultados viven en este volumen persistente
RUN mkdir -p /data
VOLUME ["/data"]

CMD ["python", "-m", "fabrica.main"]
