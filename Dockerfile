FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY README.md ./

RUN pip install . \
 && useradd -u 1000 -m connector \
 && chown -R 1000:1000 /app

USER 1000:1000

ENTRYPOINT ["vested-connect"]
CMD ["worker", "--bootstrap=/app/bootstrap.py"]
