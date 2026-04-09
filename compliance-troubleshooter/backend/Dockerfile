# Compliance Troubleshooter backend.
# python:3.12-slim base, no build dependencies because the runtime
# packages (fastapi, httpx, anthropic, uvicorn) are pure Python wheels.
# Multi-stage would shave a few MB but adds rebuild complexity that the
# MVP does not need.

FROM python:3.12-slim

# Run as non-root. The container has no business writing anywhere
# outside /data (the audit log volume) and /tmp.
RUN useradd --create-home --uid 10001 troubleshooter \
 && mkdir -p /data /app \
 && chown -R troubleshooter:troubleshooter /data /app

WORKDIR /app

# Copy requirements first so the pip install layer caches independently
# of the source code. Standard Docker layering pattern.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=troubleshooter:troubleshooter src /app/src

USER troubleshooter

# uvicorn binds the port from BACKEND_BIND env. The healthcheck in the
# Compose file hits /healthz on this port.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8088

CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8088"]
