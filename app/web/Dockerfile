FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    RUMINAPP_DEBUG=0

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN RUMINAPP_SECRET_KEY=build METRICS_PORT=0 python manage.py collectstatic --noinput >/dev/null

USER 10001:10001
EXPOSE 8080 9464
CMD ["gunicorn", "config.wsgi:application"]
