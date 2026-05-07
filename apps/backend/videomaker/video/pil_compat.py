"""Compatibilidad Pillow 10+ con MoviePy 1.x (resize vía PIL usa ``Image.ANTIALIAS``)."""

from __future__ import annotations

from PIL import Image

# Pillow 10 eliminó ANTIALIAS; MoviePy 1.x aún la referencia en moviepy/video/fx/resize.py
if not hasattr(Image, "ANTIALIAS"):
    try:
        Image.ANTIALIAS = Image.Resampling.LANCZOS  # type: ignore[attr-defined]
    except AttributeError:
        Image.ANTIALIAS = Image.LANCZOS
