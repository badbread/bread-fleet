# Zero-Day Response Pipeline backend.
# Fetches the CISA KEV feed, maps entries to osquery detection
# queries, and deploys them as Fleet policies.

FROM python:3.12-slim

RUN useradd --create-home --uid 10003 zerodayd \
 && mkdir -p /data /app \
 && chown -R zerodayd:zerodayd /data /app

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=zerodayd:zerodayd src /app/src

USER zerodayd

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8090

CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8090"]
