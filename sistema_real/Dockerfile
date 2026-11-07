# archivo: sistema_real/Dockerfile
# Imagen de la API REST de OptiSupport.
# El contexto de build es la RAIZ del repo (ver docker-compose.yml), para poder
# copiar tanto sistema_real/ como config/ (parametros compartidos).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencias
COPY sistema_real/requirements.txt /app/sistema_real/requirements.txt
RUN pip install --no-cache-dir -r /app/sistema_real/requirements.txt

# Codigo: parametros compartidos + servicio
COPY config/ /app/config/
COPY sistema_real/ /app/sistema_real/

# Carpeta de telemetria (se monta como volumen en docker-compose)
RUN mkdir -p /app/datos

EXPOSE 8000

# Healthcheck del contenedor
HEALTHCHECK --interval=15s --timeout=3s --retries=5 \
    CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://localhost:8000/health'); " || exit 1

CMD ["uvicorn", "sistema_real.main:app", "--host", "0.0.0.0", "--port", "8000"]