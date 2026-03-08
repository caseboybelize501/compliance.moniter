FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY connectors/ ./connectors/
COPY engine/ ./engine/
COPY frameworks/ ./frameworks/
COPY server/ ./server/
COPY ai/ ./ai/

RUN mkdir -p /app/logs

RUN useradd -m -u 1000 acmp && chown -R acmp:acmp /app
USER acmp

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]

EXPOSE 8000
