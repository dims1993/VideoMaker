"""Generación de imágenes con Google Imagen (Gemini API).

Carga ``GOOGLE_API_KEY`` desde ``.env`` (via ``load_project_dotenv``).
Usa ``google-generativeai`` para configurar la clave y ``google.genai`` para
``generate_images`` (Imagen 3/4). Mock con ``GOOGLE_IMAGEN_MOCK=1``.
"""

from __future__ import annotations

import os
import struct
import zlib
from pathlib import Path
from typing import Any

from videomaker.core.config import load_project_dotenv

load_project_dotenv()

DEFAULT_MODEL = "imagen-3.0-generate-002"
FALLBACK_MODEL = "imagen-4.0-generate-001"
DEFAULT_ASPECT_RATIO = "16:9"


class GoogleImagenError(Exception):
    pass


def format_api_error(exc: Exception) -> str:
    """Mensaje legible para la UI (billing, cuota, etc.)."""
    msg = str(exc)
    if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "prepayment credits are depleted" in msg.lower():
        return (
            "Créditos de Google Imagen agotados. Recarga facturación en "
            "https://aistudio.google.com/ o usa GOOGLE_IMAGEN_MOCK=1 en .env para pruebas locales."
        )
    if "404" in msg and "not found" in msg.lower():
        return f"Modelo no disponible en tu cuenta: {msg[:200]}"
    return msg[:500]


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "")
    if not raw:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def use_mock() -> bool:
    return _env_bool("GOOGLE_IMAGEN_MOCK") or not get_api_key()


def get_api_key() -> str:
    return os.getenv("GOOGLE_API_KEY", "").strip()


def get_model() -> str:
    return (os.getenv("GOOGLE_IMAGEN_MODEL") or DEFAULT_MODEL).strip()


def get_aspect_ratio() -> str:
    return (os.getenv("GOOGLE_IMAGEN_ASPECT_RATIO") or DEFAULT_ASPECT_RATIO).strip()


def _configure_legacy_sdk(api_key: str) -> None:
    """google-generativeai — configure API key (requerido por el usuario)."""
    import google.generativeai as genai

    genai.configure(api_key=api_key)


def _write_minimal_png(path: Path, width: int = 640, height: int = 360, rgb: tuple[int, int, int] = (30, 41, 59)) -> None:
    """PNG RGB mínimo sin dependencias extra (mock)."""
    r, g, b = rgb
    raw_rows = []
    for _ in range(height):
        row = b"\x00" + bytes([r, g, b]) * width
        raw_rows.append(row)
    raw = b"".join(raw_rows)
    compressed = zlib.compress(raw, 9)

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")
    path.write_bytes(png)


def _generate_mock(prompt: str, output_path: Path) -> dict[str, Any]:
    """Placeholder PNG local (sin llamada a Google)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (1280, 720), color=(30, 41, 59))
        draw = ImageDraw.Draw(img)
        lines = [
            "MOCK · Google Imagen",
            output_path.name,
            "",
            (prompt or "")[:220],
        ]
        y = 48
        for line in lines:
            draw.text((48, y), line, fill=(148, 163, 184))
            y += 28
        img.save(output_path, "PNG")
    except Exception:
        _write_minimal_png(output_path)
    return {
        "mode": "mock",
        "path": str(output_path),
        "model": "mock",
    }


def _extract_image_bytes(response: Any, output_path: Path) -> bytes:
    generated = getattr(response, "generated_images", None) or []
    if not generated:
        raise GoogleImagenError("La API no devolvió imágenes (¿filtro de seguridad?)")
    first = generated[0]
    image = getattr(first, "image", None)
    if image is None:
        raise GoogleImagenError("Respuesta sin datos de imagen")

    data = getattr(image, "image_bytes", None)
    if data:
        return bytes(data)

    if hasattr(image, "save"):
        tmp = output_path.with_suffix(".tmp.png")
        image.save(str(tmp))
        data = tmp.read_bytes()
        tmp.unlink(missing_ok=True)
        return data

    raise GoogleImagenError("No se pudieron leer bytes de la imagen generada")


def _generate_via_imagen_api(prompt: str, output_path: Path, *, model: str, aspect_ratio: str) -> dict[str, Any]:
    api_key = get_api_key()
    if not api_key:
        raise GoogleImagenError("GOOGLE_API_KEY no configurada en .env")

    _configure_legacy_sdk(api_key)

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    config = types.GenerateImagesConfig(
        number_of_images=1,
        aspect_ratio=aspect_ratio,
        output_mime_type="image/png",
    )

    models_to_try = [model]
    if model != FALLBACK_MODEL:
        models_to_try.append(FALLBACK_MODEL)

    last_err: Exception | None = None
    for m in models_to_try:
        try:
            response = client.models.generate_images(model=m, prompt=prompt, config=config)
            image_bytes = _extract_image_bytes(response, output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(image_bytes)
            return {"mode": "api", "path": str(output_path), "model": m}
        except Exception as e:
            last_err = e
            continue

    raise GoogleImagenError(format_api_error(last_err or Exception("Error desconocido generando imagen")))


def generate_image_to_path(
    prompt: str,
    output_path: Path,
    *,
    negative_prompt: str | None = None,
) -> dict[str, Any]:
    """
    Genera una imagen y la guarda en ``output_path``.
    Devuelve metadatos incluyendo ruta local (servir via FileResponse).
    """
    text = (prompt or "").strip()
    if not text:
        raise GoogleImagenError("Prompt vacío")

    if negative_prompt and negative_prompt.strip():
        text = f"{text}\n\nAvoid: {negative_prompt.strip()}"

    output_path = Path(output_path)
    if output_path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
        output_path = output_path.with_suffix(".png")

    if use_mock():
        return _generate_mock(text, output_path)

    return _generate_via_imagen_api(
        text,
        output_path,
        model=get_model(),
        aspect_ratio=get_aspect_ratio(),
    )


def local_image_api_url(work_slug: str, filename: str) -> str:
    from urllib.parse import quote

    return (
        f"/api/pipeline/images-generation/image?"
        f"work={quote(work_slug)}&filename={quote(Path(filename).name)}"
    )
