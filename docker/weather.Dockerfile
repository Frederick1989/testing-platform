# Weather mock API under test — port 5000
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1

WORKDIR /srv/weather

COPY services/weather-mock/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/weather-mock/app ./app

EXPOSE 5000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5000"]
