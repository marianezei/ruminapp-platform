FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY reproducao ./reproducao

USER 10001:10001
EXPOSE 8080 9464
CMD ["uvicorn", "reproducao.api:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
