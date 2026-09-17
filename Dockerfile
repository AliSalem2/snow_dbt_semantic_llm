# Serves the chat demo and the MCP endpoint on Cloud Run.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DBT_TARGET=serve \
    DBT_PROJECT_DIR=/app/dbt \
    DBT_PROFILES_DIR=/app/dbt

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY dbt/ ./dbt/
# dbt packages are fetched at build time; the container has no network budget
# for it at startup.
RUN cd dbt && dbt deps

COPY app/ ./app/

# Cloud Run sets PORT.
CMD exec uvicorn app.web:app --host 0.0.0.0 --port ${PORT:-8080}
