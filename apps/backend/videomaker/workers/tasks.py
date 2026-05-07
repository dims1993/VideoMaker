"""Tareas Celery (sync canal, etc.)."""

from __future__ import annotations

from videomaker.workers.celery_app import celery_app
from videomaker.web.jobs import run_channel_sync


@celery_app.task(name="videomaker.channel_sync")
def channel_sync_task(work: str, channel_id: str, max_videos: int = 25, lang: str = "es") -> dict:
    run_channel_sync(work, channel_id=channel_id, max_videos=max_videos, lang=lang)
    return {"ok": True, "channel_id": channel_id}

