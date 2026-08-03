# pagent cloud API
# build from repo root:
#   docker build -f cloud/backend/Dockerfile -t pagent-cloud-api .

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY cloud/backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY pyproject.toml README.md /tmp/pagent/
COPY src /tmp/pagent/src
RUN pip install --no-cache-dir /tmp/pagent

COPY cloud/backend /app/cloud/backend

RUN mkdir -p /var/pagent/runtime

EXPOSE 8787

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
  CMD curl -fsS http://127.0.0.1:8787/api/ready || exit 1

CMD ["uvicorn", "cloud.backend.app:app", "--host", "0.0.0.0", "--port", "8787"]
