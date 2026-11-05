FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /service

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN useradd --create-home appuser
USER appuser

EXPOSE 5000

# Single worker on purpose: the cache and circuit breakers live in process memory.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5000", "--no-access-log"]
