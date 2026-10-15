FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FABRICA_DATOS=/data/datos \
    FABRICA_RESULTADOS=/data/resultados \
    FABRICA_VIVO=/data/vivo

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY config.yaml .
COPY fabrica ./fabrica
# Fecha en que se armó esta versión (la muestra /salud: sirve para saber si la actualización llegó)
RUN date -u +"%Y-%m-%d %H:%M UTC" > /app/VERSION

# Datos, resultados de la fábrica, estado de la liga y logs viven en este volumen
RUN mkdir -p /data
VOLUME ["/data"]

CMD ["python", "-m", "fabrica.servicio"]
