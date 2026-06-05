"""Identificador de arranque del servidor (uvicorn). Reinicia en cada dev.sh / reload."""

from __future__ import annotations

import time
import uuid

SERVER_BOOT_ID: str = uuid.uuid4().hex
SERVER_BOOT_AT: str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

# work slug → ya limpiamos errores de imágenes en este arranque
_IMAGES_ERRORS_CLEARED: set[str] = set()


def mark_images_errors_cleared(work: str) -> None:
    _IMAGES_ERRORS_CLEARED.add(work)


def images_errors_cleared_for(work: str) -> bool:
    return work in _IMAGES_ERRORS_CLEARED
