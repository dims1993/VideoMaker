FROM python:3.11-slim

WORKDIR /app

# System deps (certs + curl for debug)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/requirements.txt

COPY videomaker /app/videomaker
COPY migrations /app/migrations

ENV PYTHONUNBUFFERED=1

