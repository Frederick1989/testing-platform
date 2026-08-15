# Test Manager API — Python 3.11 slim image
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv/api

COPY services/test-manager-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/test-manager-api/app ./app
COPY services/test-manager-api/alembic.ini .
COPY services/test-manager-api/alembic ./alembic
COPY reports/templates ./reports-templates
COPY reports ./reports

ENV REPORTS_ROOT=/srv/api/reports \
    STORAGE_LOCAL_ROOT=/srv/api/data \
    REPORT_TEMPLATES_DIR=/srv/api/reports-templates

EXPOSE 7000

# Migrations run before the scheduler starts.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 7000"]
