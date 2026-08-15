# API test framework (pytest runner + report viewer) — ports 5001
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1

WORKDIR /srv/api-tests

COPY services/api-test-framework/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/api-test-framework/app ./app
COPY services/api-test-framework/tests ./tests
COPY services/api-test-framework/pytest.ini .

ENV API_TESTS_PYTHON_BIN=python \
    API_TESTS_WEATHER_URL=http://weather:5000

EXPOSE 5001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5001"]
