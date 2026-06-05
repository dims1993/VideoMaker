"""Generación de imágenes con OpenAI Images API (ChatGPT / gpt-image-1, dall-e-3)."""

from __future__ import annotations

import base64
import os
import struct
import zlib
from pathlib import Path
from typing import Any

import requests

from videomaker.core.config import load_project_dotenv

load_project_dotenv()

DEFAULT_MODEL = "gpt-image-2"
DEFAULT_SIZE = "1280x720"  # 16:9 exacto, ancho ≥640 (YouTube thumbnail)


class OpenAIImagesError(Exception):
    pass


def format_api_error(exc: Exception) -> str:
    msg = str(exc)
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        try:
            body = exc.response.json()
            err = body.get("error") if isinstance(body, dict) else None
            if isinstance(err, dict) and err.get("message"):
                msg = str(err["message"])
        except Exception:
            msg = (exc.response.text or msg)[:500]
    low = msg.lower()
    if "insufficient" in low or "quota" in low or "billing" in low or "exceeded" in low:
        return (
            "Cuota o facturación de OpenAI agotada. Revisa "
            "https://platform.openai.com/settings/organization/billing "
            "o usa OPENAI_IMAGES_MOCK=1 en .env para pruebas locales."
        )
    if "invalid_api_key" in low or "incorrect api key" in low:
        return "OPENAI_API_KEY inválida. Configúrala en .env (misma clave que Metadata/Script Writer)."
    return msg[:500]


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "")
    if not raw:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def use_mock() -> bool:
    return _env_bool("OPENAI_IMAGES_MOCK") or not get_api_key()


def get_api_key() -> str:
    return os.getenv("OPENAI_API_KEY", "").strip()


def get_base_url() -> str:
    return os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")


def get_model() -> str:
    return (os.getenv("OPENAI_IMAGE_MODEL") or DEFAULT_MODEL).strip()


def get_size() -> str:
    return (os.getenv("OPENAI_IMAGE_SIZE") or DEFAULT_SIZE).strip()


def _write_minimal_png(path: Path, width: int = 1280, height: int = 720) -> None:
    r, g, b = 30, 41, 59
    raw_rows = [b"\x00" + bytes([r, g, b]) * width for _ in range(height)]
    raw = b"".join(raw_rows)
    compressed = zlib.compress(raw, 9)

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")
    path.write_bytes(png)


def _generate_mock(prompt: str, output_path: Path) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (1280, 720), color=(15, 23, 42))
        draw = ImageDraw.Draw(img)
        lines = ["MOCK · OpenAI Images", output_path.name, "", (prompt or "")[:220]]
        y = 48
        for line in lines:
            draw.text((48, y), line, fill=(148, 163, 184))
            y += 28
        img.save(output_path, "PNG")
    except Exception:
        _write_minimal_png(output_path)
    return {"mode": "mock", "path": str(output_path), "model": "mock"}


def _uses_response_format_param(model: str) -> bool:
    """Solo DALL·E acepta ``response_format``; GPT Image devuelve base64 sin ese parámetro."""
    m = (model or "").strip().lower()
    return m.startswith("dall-e")


def _build_payload(prompt: str, *, model: str, size: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "size": size,
    }
    if _uses_response_format_param(model):
        payload["response_format"] = "b64_json"
        if model == "dall-e-3":
            payload["quality"] = os.getenv("OPENAI_IMAGE_QUALITY", "standard").strip() or "standard"
    return payload


def _generate_via_api(prompt: str, output_path: Path, *, model: str, size: str) -> dict[str, Any]:
    api_key = get_api_key()
    if not api_key:
        raise OpenAIImagesError("OPENAI_API_KEY no configurada en .env")

    url = f"{get_base_url()}/images/generations"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = _build_payload(prompt, model=model, size=size)

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=180)
        r.raise_for_status()
    except requests.RequestException as e:
        raise OpenAIImagesError(format_api_error(e)) from e

    data = r.json()
    items = data.get("data") if isinstance(data, dict) else None
    if not items or not isinstance(items, list):
        raise OpenAIImagesError("La API no devolvió imágenes.")

    first = items[0] if isinstance(items[0], dict) else {}
    b64 = first.get("b64_json") or first.get("b64")
    if b64:
        image_bytes = base64.b64decode(b64)
    else:
        img_url = first.get("url")
        if not img_url:
            raise OpenAIImagesError(
                "Respuesta sin imagen (sin b64_json ni url). "
                f"Claves: {', '.join(sorted(first.keys())) or 'vacío'}"
            )
        try:
            img_r = requests.get(str(img_url), timeout=120)
            img_r.raise_for_status()
            image_bytes = img_r.content
        except requests.RequestException as e:
            raise OpenAIImagesError(format_api_error(e)) from e

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(image_bytes)
    return {"mode": "api", "path": str(output_path), "model": model, "size": size}


def generate_image_to_path(
    prompt: str,
    output_path: Path,
    *,
    negative_prompt: str | None = None,
) -> dict[str, Any]:
    """Genera PNG en ``output_path`` vía OpenAI Images API."""
    text = (prompt or "").strip()
    if not text:
        raise OpenAIImagesError("Prompt vacío")

    if negative_prompt and negative_prompt.strip():
        text = f"{text}\n\nAvoid: {negative_prompt.strip()}"

    output_path = Path(output_path)
    if output_path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
        output_path = output_path.with_suffix(".png")

    if use_mock():
        return _generate_mock(text, output_path)

    return _generate_via_api(text, output_path, model=get_model(), size=get_size())
