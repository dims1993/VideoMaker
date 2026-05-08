"""Celery app (Redis broker/backend).

Se activa si REDIS_URL está configurado. Para desarrollo:
  export REDIS_URL=redis://localhost:6379/0
  celery -A videomaker.workers.celery_app worker -l info
"""

from __future__ import annotations

import os

from celery import Celery


def _redis_url() -> str:
    return os.environ.get("REDIS_URL", "redis://localhost:6379/0").strip() or "redis://localhost:6379/0"


celery_app = Celery(
    "videomaker",
    broker=_redis_url(),
    backend=_redis_url(),
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# Ensure tasks are registered when the worker boots.
# (Celery only knows tasks that have been imported or autodiscovered.)
celery_app.conf.update(
    include=[
        "videomaker.workers.tasks",
    ]
)

