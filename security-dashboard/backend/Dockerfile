# Security Posture Dashboard backend.
# Serves synthetic fleet compliance data through a FastAPI API. The
# image is intentionally minimal: no Fleet API client, no Claude SDK,
# just FastAPI + the seed data file. In production, add httpx for
# Fleet polling and a Postgres driver for historical snapshots.

FROM python:3.12-slim

RUN useradd --create-home --uid 10002 dashboard \
 && mkdir -p /app \
 && chown -R dashboard:dashboard /app

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=dashboard:dashboard src /app/src

USER dashboard

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8089

CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8089"]
