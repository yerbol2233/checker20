FROM python:3.11-slim

WORKDIR /app

ENV PYTHONPATH=/app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create logs dir
RUN mkdir -p /app/logs

EXPOSE 8000

# Railway задаёт PORT динамически; локально по умолчанию 8000
CMD sh -c "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"
