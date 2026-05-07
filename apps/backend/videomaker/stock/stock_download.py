"""Descarga vídeos de Pexels según un plan de `StockQuery` (una pista por término único)."""

from __future__ import annotations

import re
from pathlib import Path

import requests

from videomaker.core.models import StockQuery
from .stock_pexels import PexelsClient


def _slug(s: str, max_len: int = 40) -> str:
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
    s = re.sub(r"[-\s]+", "_", s.strip()).strip("_")
    return (s[:max_len] or "clip").lower()


def download_stock_for_queries(
    client: PexelsClient,
    queries: list[StockQuery],
    out_dir: Path,
    *,
    max_downloads: int = 35,
    timeout_s: int = 120,
) -> list[Path]:
    """
    Para cada término de búsqueda único (en orden), descarga el primer HD disponible.
    Devuelve rutas locales .mp4 en `out_dir`.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    paths: list[Path] = []
    idx = 0
    for q in queries:
        key = q.query.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        hits = client.search_videos(q.query, per_page=4)
        if not hits:
            continue
        url = hits[0].url
        if not url:
            continue
        dest = out_dir / f"{idx:04d}_{_slug(q.query)}.mp4"
        _download_file(url, dest, timeout_s=timeout_s)
        paths.append(dest)
        idx += 1
        if len(paths) >= max_downloads:
            break
    return paths


def _download_file(url: str, dest: Path, *, timeout_s: int) -> None:
    with requests.get(url, stream=True, timeout=timeout_s) as r:
        r.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 256):
                if chunk:
                    f.write(chunk)
