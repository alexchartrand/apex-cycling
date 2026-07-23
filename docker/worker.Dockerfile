FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev gcc && rm -rf /var/lib/apt/lists/*

COPY backend/ ./
RUN pip install --no-cache-dir -e ".[dev]"

CMD ["python", "-m", "app.ingestion.runner"]
