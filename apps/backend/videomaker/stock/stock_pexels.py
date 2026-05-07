"""Cliente mínimo Pexels (vídeo stock). Requiere PEXELS_API_KEY en entorno."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests

PEXELS_VIDEO_SEARCH = "https://api.pexels.com/videos/search"


@dataclass
class PexelsVideoHit:
    id: int
    url: str
    thumbnail: str
    duration_s: int


class PexelsClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("PEXELS_API_KEY", "")
        if not self.api_key:
            raise RuntimeError(
                "Falta PEXELS_API_KEY. Añádela a .env o al entorno del proceso."
            )

    def search_videos(
        self,
        query: str,
        *,
        per_page: int = 5,
        orientation: str = "landscape",
    ) -> list[PexelsVideoHit]:
        headers = {"Authorization": self.api_key}
        params: dict[str, Any] = {
            "query": query,
            "per_page": per_page,
            "orientation": orientation,
        }
        r = requests.get(PEXELS_VIDEO_SEARCH, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        out: list[PexelsVideoHit] = []
        for v in data.get("videos", []):
            files = v.get("video_files") or []
            best = None
            for f in files:
                if f.get("quality") == "hd" and f.get("link"):
                    best = f["link"]
                    break
            if not best and files:
                best = files[0].get("link", "")
            out.append(
                PexelsVideoHit(
                    id=int(v["id"]),
                    url=best or "",
                    thumbnail=(v.get("image") or ""),
                    duration_s=int(v.get("duration") or 0),
                )
            )
        return out
