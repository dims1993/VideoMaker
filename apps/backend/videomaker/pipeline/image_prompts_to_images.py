"""Construye `images_generation.json` desde `image_prompts.json`."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from videomaker.pipeline.runner import save_manual_images_generation_bundle

_PLACEHOLDER_ALT = "Imagen por desarrollar"


def _format_timestamp(ms: int) -> str:
    s = max(0, ms // 1000)
    return f"{s // 60}:{s % 60:02d}"


def _normalize_act(raw: str | None, role: str | None = None) -> str:
    act = (raw or "").strip().lower()
    if act in ("hook", "intro", "body", "cta", "outro", "act2", "act3", "act4", "thumbnail"):
        return act
    role_l = (role or "").lower()
    if role_l == "thumbnail" or "thumbnail" in role_l:
        return "thumbnail"
    if "intro" in role_l:
        return "intro"
    if "outro" in role_l:
        return "outro"
    if "hook" in role_l:
        return "hook"
    if "cta" in role_l or "cierre" in role_l:
        return "cta"
    return "body"


def _safe_filename(order: int, _prompt_id: str = "") -> str:
    return f"{int(order):03d}.png"


def _scene_description(prompt: dict[str, Any]) -> str:
    for key in ("situation", "scene_description_es", "segment_text", "narration_text"):
        val = (prompt.get(key) or "").strip()
        if val:
            return val[:240]
    return (prompt.get("ai_prompt") or prompt.get("text") or "")[:240]


def _duration_hint_s(prompt: dict[str, Any]) -> int:
    ms = prompt.get("duration_ms")
    if isinstance(ms, (int, float)) and ms > 0:
        return max(1, int(round(ms / 1000)))
    hint = prompt.get("duration_hint_s")
    if isinstance(hint, (int, float)) and hint > 0:
        return max(1, int(round(hint)))
    return 10


def sync_manifest_image_status(work_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Marca generated si el PNG existe en pipeline/images/."""
    images_dir = work_dir / "pipeline" / "images"
    images = manifest.get("images")
    if not isinstance(images, list):
        return manifest

    for row in images:
        if not isinstance(row, dict):
            continue
        fn = Path(str(row.get("filename") or "")).name
        if fn and (images_dir / fn).is_file():
            row["status"] = "generated"
        elif row.get("status") != "error":
            row["status"] = "pending"
    return manifest


def build_images_generation_manifest(
    work_dir: Path,
    prompts_bundle: dict[str, Any],
) -> dict[str, Any]:
    prompts_raw = prompts_bundle.get("prompts")
    if not isinstance(prompts_raw, list) or not prompts_raw:
        raise ValueError("image_prompts.json no contiene prompts.")

    prompts: list[dict[str, Any]] = [p for p in prompts_raw if isinstance(p, dict)]
    if not prompts:
        raise ValueError("image_prompts.json no contiene prompts válidos.")

    has_selection = any("selected" in p for p in prompts)
    if has_selection:
        export_prompts = [p for p in prompts if p.get("selected", True)]
        if not export_prompts:
            raise ValueError(
                "Ningún prompt marcado para exportar. Activa la casilla ✓ en al menos una tarjeta de salida."
            )
        prompts = export_prompts

    def _sort_key(p: dict[str, Any], idx: int) -> tuple[float, int]:
        timing = p.get("timing")
        if isinstance(timing, dict):
            if timing.get("mode") == "relative_hook" or timing.get("reconciled"):
                order = p.get("order")
                if isinstance(order, int):
                    return (float(order), idx)
            start = timing.get("audio_start_s")
            if isinstance(start, (int, float)):
                return (float(start), idx)
            start = timing.get("start_sec_estimated") or timing.get("start_sec")
            if isinstance(start, (int, float)) and timing.get("mode") != "relative_hook":
                return (float(start), idx)
        order = p.get("order")
        if isinstance(order, int):
            return (float(order), idx)
        pid = p.get("id")
        if pid in ("intro", "outro"):
            return (-1.0 if pid == "intro" else 99999.0, idx)
        try:
            return (1000.0 + int(str(pid)), idx)
        except (TypeError, ValueError):
            return (2000.0 + idx, idx)

    prompts = sorted(enumerate(prompts), key=lambda t: _sort_key(t[1], t[0]))
    prompts = [p for _, p in prompts]

    images_dir = work_dir / "pipeline" / "images"
    images: list[dict[str, Any]] = []
    cumulative_ms = 0

    for idx, prompt in enumerate(prompts, start=1):
        prompt_id = str(prompt.get("id") or prompt.get("chunk_id") or idx)
        filename = _safe_filename(idx, prompt_id)
        duration_s = _duration_hint_s(prompt)
        timestamp_hint = _format_timestamp(cumulative_ms)
        cumulative_ms += duration_s * 1000

        status = "generated" if (images_dir / filename).is_file() else "pending"
        preselect = prompt.get("selected", True) if has_selection else False
        images.append(
            {
                "id": prompt_id,
                "filename": filename,
                "act": _normalize_act(str(prompt.get("act") or ""), str(prompt.get("role") or "")),
                "order": idx,
                "timestamp_hint": timestamp_hint,
                "duration_hint_s": duration_s,
                "role": str(prompt.get("role") or "scene"),
                "track": str(prompt.get("track") or "").strip() or None,
                "scene_description_es": _scene_description(prompt),
                "scene_prompt_en": str(prompt.get("scene_prompt_en") or "").strip() or None,
                "ai_prompt": str(prompt.get("ai_prompt") or prompt.get("text") or "").strip(),
                "negative_prompt": str(prompt.get("negative_prompt") or "").strip() or None,
                "status": status,
                "selected": preselect,
                "placeholder_alt": _PLACEHOLDER_ALT,
                "prompt_id": prompt_id,
                "section": (prompt.get("section") or "").strip() or None,
                "camera_motion": str(prompt.get("camera_motion") or "").strip() or None,
                "camera_motion_direction": str(prompt.get("camera_motion_direction") or "").strip()
                or None,
                "pacing_role": str(prompt.get("pacing_role") or "").strip() or None,
                "sequence_block": str(prompt.get("sequence_block") or "").strip() or None,
            }
        )

    style_bits: list[str] = []
    gs = prompts_bundle.get("global_style")
    if isinstance(gs, dict):
        for key in ("base_style_en", "style", "aspect_ratio"):
            val = gs.get(key)
            if isinstance(val, str) and val.strip():
                style_bits.append(val.strip()[:80])
    target = str(prompts_bundle.get("target_generator") or "").strip()

    return {
        "version": 2,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "image_prompts",
        "image_prompts_source": str(prompts_bundle.get("source") or "image_prompts"),
        "generator": target or "manual",
        "style": style_bits[0] if style_bits else "",
        "total": len(images),
        "selected_count": sum(1 for img in images if img.get("selected")),
        "images": images,
    }


def push_image_prompts_to_images_generation(work_dir: Path) -> dict[str, Any]:
    """Reemplaza images_generation.json desde image_prompts.json (proyecto nuevo)."""
    prompts_path = work_dir / "pipeline" / "image_prompts.json"
    if not prompts_path.is_file():
        raise ValueError("No existe pipeline/image_prompts.json. Guarda prompts en Image Prompt Writer primero.")

    try:
        bundle = json.loads(prompts_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError(f"No se pudo leer image_prompts.json: {e}") from e

    if not isinstance(bundle, dict):
        raise ValueError("image_prompts.json inválido.")

    from videomaker.llm.image_prompt_timing_reconcile import try_reconcile_image_prompts

    try_reconcile_image_prompts(work_dir)
    try:
        bundle = json.loads(prompts_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass

    manifest = build_images_generation_manifest(work_dir, bundle)
    save_manual_images_generation_bundle(work_dir, manifest)
    pending = sum(1 for img in manifest["images"] if img.get("status") == "pending")
    generated = manifest["total"] - pending
    return {
        "path": "pipeline/images_generation.json",
        "total": manifest["total"],
        "pending": pending,
        "generated": generated,
    }
