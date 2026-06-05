"""Cliente HTTP para ElevenLabs Text-to-Speech (Scene Editor, por bloque)."""

from __future__ import annotations

import os
from typing import Any

import requests

ELEVENLABS_API_BASE = "https://api.elevenlabs.io/v1"
DEFAULT_MODEL_ID = "eleven_turbo_v2_5"


class ElevenLabsError(RuntimeError):
    """Error de la API ElevenLabs con mensaje legible para la UI."""


def _api_key() -> str:
    return (os.environ.get("ELEVENLABS_API_KEY") or "").strip()


def default_voice_id() -> str:
    return (
        (os.environ.get("ELEVENLABS_VOICE_ID") or "").strip()
        or (os.environ.get("ELEVENSLABS_VOICE_ID") or "").strip()  # typo alias
    )


def default_model_id() -> str:
    return (os.environ.get("ELEVENLABS_MODEL_ID") or DEFAULT_MODEL_ID).strip() or DEFAULT_MODEL_ID


def is_configured() -> bool:
    return bool(_api_key() and default_voice_id())


def scene_tts_provider() -> str:
    """
    ``elevenlabs`` si hay API key + voice id (o provider explícito).
    ``mock`` si VIDEOMAKER_SCENE_TTS_PROVIDER=mock o faltan credenciales.
    """
    explicit = (os.environ.get("VIDEOMAKER_SCENE_TTS_PROVIDER") or "").strip().lower()
    if explicit == "mock":
        return "mock"
    if explicit == "elevenlabs":
        return "elevenlabs" if is_configured() else "mock"
    if _api_key() and default_voice_id():
        return "elevenlabs"
    return "mock"


def tts_config_public() -> dict[str, Any]:
    """Metadatos para la UI (sin exponer la API key)."""
    provider = scene_tts_provider()
    return {
        "provider": provider,
        "elevenlabs_configured": is_configured(),
        "voice_id": default_voice_id() if provider == "elevenlabs" else None,
        "model_id": default_model_id() if provider == "elevenlabs" else None,
    }


def list_voices(*, api_key: str | None = None) -> list[dict[str, Any]]:
    key = (api_key or _api_key()).strip()
    if not key:
        raise ElevenLabsError("Falta ELEVENLABS_API_KEY en .env")
    r = requests.get(
        f"{ELEVENLABS_API_BASE}/voices",
        headers={"xi-api-key": key},
        timeout=30,
    )
    if not r.ok:
        raise ElevenLabsError(_error_detail(r))
    data = r.json()
    voices = data.get("voices") if isinstance(data, dict) else None
    if not isinstance(voices, list):
        return []
    return [
        {
            "voice_id": str(v.get("voice_id") or ""),
            "name": str(v.get("name") or ""),
            "category": str(v.get("category") or ""),
        }
        for v in voices
        if isinstance(v, dict) and v.get("voice_id")
    ]


def synthesize_speech(
    text: str,
    *,
    voice_id: str | None = None,
    model_id: str | None = None,
    api_key: str | None = None,
    stability: float | None = None,
    similarity_boost: float | None = None,
) -> bytes:
    """Devuelve bytes MP3."""
    key = (api_key or _api_key()).strip()
    if not key:
        raise ElevenLabsError(
            "Falta ELEVENLABS_API_KEY. Añádela a .env para usar ElevenLabs en el Scene Editor."
        )
    vid = (voice_id or default_voice_id()).strip()
    if not vid:
        raise ElevenLabsError(
            "Falta ELEVENLABS_VOICE_ID. Copia un voice_id desde el panel de ElevenLabs."
        )
    mid = (model_id or default_model_id()).strip()
    txt = (text or "").strip()
    if not txt:
        raise ValueError("Texto vacío.")

    voice_settings: dict[str, Any] = {
        "stability": _float_env("ELEVENLABS_STABILITY", stability, default=0.5),
        "similarity_boost": _float_env(
            "ELEVENLABS_SIMILARITY_BOOST", similarity_boost, default=0.75
        ),
    }
    style = _optional_float_env("ELEVENLABS_STYLE")
    if style is not None:
        voice_settings["style"] = style
    if os.environ.get("ELEVENLABS_SPEAKER_BOOST", "1").strip().lower() not in {"0", "false", "no"}:
        voice_settings["use_speaker_boost"] = True

    payload: dict[str, Any] = {
        "text": txt,
        "model_id": mid,
        "voice_settings": voice_settings,
    }

    r = requests.post(
        f"{ELEVENLABS_API_BASE}/text-to-speech/{vid}",
        headers={
            "xi-api-key": key,
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )
    if not r.ok:
        raise ElevenLabsError(_error_detail(r))
    if not r.content:
        raise ElevenLabsError("ElevenLabs devolvió audio vacío.")
    return r.content


def _optional_float_env(name: str) -> float | None:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _float_env(name: str, override: float | None, *, default: float) -> float:
    if override is not None:
        return float(override)
    raw = (os.environ.get(name) or "").strip()
    if raw:
        try:
            return float(raw)
        except ValueError:
            pass
    return default


def _error_detail(r: requests.Response) -> str:
    try:
        body = r.json()
        if isinstance(body, dict):
            detail = body.get("detail")
            if isinstance(detail, dict):
                return str(detail.get("message") or detail)
            if isinstance(detail, list) and detail:
                first = detail[0]
                if isinstance(first, dict):
                    return str(first.get("msg") or first)
            if detail:
                return str(detail)
    except Exception:
        pass
    return f"ElevenLabs HTTP {r.status_code}: {(r.text or '')[:240]}"
