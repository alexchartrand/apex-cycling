FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev gcc && rm -rf /var/lib/apt/lists/*

COPY backend/ ./
RUN pip install --no-cache-dir -e ".[dev]"

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && python -m app.training.cli apply-facilities && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]
