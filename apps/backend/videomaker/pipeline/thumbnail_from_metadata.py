"""Miniaturas YouTube desde ``packaging.json`` / ``metadata.json`` → prompts → images_generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from videomaker.core.metadata_settings_store import read_metadata_settings
from videomaker.pipeline.image_prompts_to_images import sync_manifest_image_status
from videomaker.pipeline.runner import (
    _infer_thumbnail_expression,
    _load_prompt_artifact,
    _pipeline_dir,
    _write_json,
    save_manual_images_generation_bundle,
)

_THUMB_ORDER_BASE = 10_000


def _read_packaging_or_metadata(work_dir: Path) -> dict[str, Any]:
    """Hook-first: ``packaging.json``; si no, ``metadata.json`` (legacy)."""
    for name in ("packaging.json", "metadata.json"):
        p = _pipeline_dir(work_dir) / name
        if not p.is_file():
            continue
        try:
            md = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"{name} no es JSON válido: {e}") from e
        if isinstance(md, dict):
            return md
    raise ValueError(
        "No existe pipeline/packaging.json ni metadata.json. "
        "Ejecuta Packaging (Título + Miniatura) o Metadata."
    )


def _read_metadata(work_dir: Path) -> dict[str, Any]:
    return _read_packaging_or_metadata(work_dir)


def extract_thumbnail_ideas(md: dict[str, Any]) -> tuple[list[str], str]:
    ed = md.get("editorial") if isinstance(md.get("editorial"), dict) else {}
    thumbs_raw = ed.get("thumbnail_ideas") if isinstance(ed, dict) else None
    ideas: list[str] = []
    if isinstance(thumbs_raw, list):
        for t in thumbs_raw:
            s = str(t).strip()
            if s:
                ideas.append(s)
    mkt = md.get("marketing") if isinstance(md.get("marketing"), dict) else {}
    hook = str(mkt.get("thumbnail_hook_text") or "").strip()
    return ideas, hook


def _thumbnail_ai_prompt(idea: str, *, hook_text: str, index: int) -> str:
    base = (
        "YouTube thumbnail, 16:9 aspect ratio, ultra sharp, high contrast, "
        "scroll-stopping composition, readable at small size. "
    )
    scene = idea.strip()
    overlay = ""
    if hook_text and index == 0:
        overlay = (
            f' Include bold, legible text overlay in the frame: "{hook_text}". '
            "Text must be large and high contrast."
        )
    return f"{base}{scene}{overlay}"


def _thumbnail_ai_prompt_with_visual_style(
    work_dir: Path,
    idea: str,
    *,
    hook_text: str,
    index: int,
) -> str:
    """
    Mismo estilo que Scene Editor / Gemini: ``scene_visual_settings.json`` guardado en
    Image Prompt Writer → sección «Estilo visual y avatar».
    """
    from videomaker.scene_editor.protagonist_expressions import (
        expressions_catalog_from_settings,
        resolve_protagonist_expression,
    )
    from videomaker.scene_editor.scene_visual_settings_store import read_scene_visual_settings
    from videomaker.scene_editor.visual_prompt_compose import (
        assemble_nano_banana_prompt,
        effective_avoid_en,
        enrich_scene_prompt,
        protagonist_wardrobe_from_settings,
    )

    settings = read_scene_visual_settings(work_dir)
    catalog = expressions_catalog_from_settings(settings)
    expr_key, expr_en = resolve_protagonist_expression(
        narration=idea,
        llm_key=None,
        catalog=catalog,
    )

    scene_parts = [
        "YouTube thumbnail composition, scroll-stopping, readable at small size.",
        idea.strip(),
        f"Protagonist facial expression ({expr_key}): {expr_en}.",
    ]
    if hook_text and index == 0:
        scene_parts.append(
            f'Bold high-contrast text overlay readable at small size: "{hook_text}".'
        )

    protagonist = str(settings.get("protagonist_en") or "").strip()
    if protagonist:
        scene_parts.insert(1, f"Channel presenter identity: {protagonist}.")

    scene = enrich_scene_prompt(
        " ".join(scene_parts),
        director_note=None,
        protagonist_en=str(settings.get("protagonist_en") or "").strip(),
        wardrobe_en=protagonist_wardrobe_from_settings(settings),
    )

    base_style = str(settings.get("base_style_en") or "").strip()
    if base_style and "thumbnail" not in base_style.lower():
        base_style = f"YouTube thumbnail still, {base_style.rstrip('.')}"

    return assemble_nano_banana_prompt(
        base_style_en=base_style or "YouTube thumbnail still, cinematic, high contrast",
        scene_prompt_en=scene,
        avoid_en=effective_avoid_en(settings),
        aspect_ratio="16:9",
        output_spec=str(settings.get("output_spec") or "2K output"),
    )


def _build_thumbnail_prompt_entries(
    work_dir: Path,
    ideas: list[str],
    hook_text: str,
    *,
    include_visual_style: bool,
) -> list[dict[str, Any]]:
    """``include_visual_style``: estilo Nano Banana 2 de Image Prompt Writer (sección avatar)."""

    prompts: list[dict[str, Any]] = []
    for i, idea in enumerate(ideas):
        pid = f"thumb_{i}"
        if include_visual_style:
            ai = _thumbnail_ai_prompt_with_visual_style(
                work_dir, idea, hook_text=hook_text, index=i
            )
            entry: dict[str, Any] = {
                "id": pid,
                "role": "thumbnail",
                "index": i,
                "text": idea,
                "ai_prompt": ai,
                "scene_prompt_en": ai,
                "act": "thumbnail",
                "section": "thumbnail",
                "selected": True,
                "visual_style_source": "image_prompt_writer_avatar_section",
            }
        else:
            ai = _thumbnail_ai_prompt(idea, hook_text=hook_text, index=i)
            entry = {
                "id": pid,
                "role": "thumbnail",
                "index": i,
                "text": idea,
                "ai_prompt": ai,
                "scene_prompt_en": ai,
                "act": "thumbnail",
                "section": "thumbnail",
                "selected": True,
            }
        prompts.append(entry)
    return prompts


def _carry_prompt_spine(bundle: dict[str, Any], work_dir: Path) -> None:
    try:
        art = _load_prompt_artifact(work_dir)
        vs = art.get("visual_symbols") if isinstance(art, dict) else None
        if isinstance(vs, list) and vs:
            bundle["visual_symbols"] = [v for v in vs if isinstance(v, dict)][:8]
        tn = art.get("thumbnail_narrative") if isinstance(art, dict) else None
        if isinstance(tn, dict) and any(
            str(tn.get(k) or "").strip() for k in ("core_contrast", "viewer_role", "envy_target", "emotion")
        ):
            bundle["thumbnail_narrative"] = {
                "core_contrast": str(tn.get("core_contrast") or "").strip(),
                "viewer_role": str(tn.get("viewer_role") or "").strip(),
                "envy_target": str(tn.get("envy_target") or "").strip(),
                "emotion": str(tn.get("emotion") or "").strip(),
            }
        ssf = art.get("scroll_stop_factors") if isinstance(art, dict) else None
        if isinstance(ssf, list) and ssf:
            vals = [str(x).strip() for x in ssf if str(x).strip()][:10]
            if vals:
                bundle["scroll_stop_factors"] = vals
    except Exception:
        pass


def push_thumbnail_ideas_to_image_prompts(
    work_dir: Path,
    *,
    include_avatar: bool = False,
    merge: bool = True,
) -> dict[str, Any]:
    """
    ``editorial.thumbnail_ideas`` (+ ``marketing.thumbnail_hook_text``) → ``image_prompts.json``.

    Con ``merge=True`` conserva los prompts de escena existentes y solo sustituye entradas
    con ``role=thumbnail``.
    """
    md = _read_metadata(work_dir)
    ideas, hook_text = extract_thumbnail_ideas(md)
    if not ideas:
        raise ValueError(
            "No hay ideas en editorial.thumbnail_ideas. Ejecuta Metadata o añádelas en el JSON."
        )

    thumb_entries = _build_thumbnail_prompt_entries(
        work_dir,
        ideas,
        hook_text,
        include_visual_style=include_avatar,
    )

    settings = read_metadata_settings(work_dir)
    tp = str(settings.get("target_platform") or "youtube").strip().lower()
    if tp not in ("youtube", "tiktok", "reels"):
        tp = "youtube"

    out = _pipeline_dir(work_dir) / "image_prompts.json"
    existing: dict[str, Any] | None = None
    if merge and out.is_file():
        try:
            raw = json.loads(out.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                existing = raw
        except (OSError, json.JSONDecodeError):
            existing = None

    if existing and merge:
        prev = existing.get("prompts")
        scene_prompts = (
            [p for p in prev if isinstance(p, dict) and p.get("role") != "thumbnail"]
            if isinstance(prev, list)
            else []
        )
        bundle = {**existing, "prompts": scene_prompts + thumb_entries}
        bundle["metadata_thumbnails"] = {
            "count": len(thumb_entries),
            "hook_text": hook_text or None,
            "include_visual_style": include_avatar,
            "visual_style_ref": "image_prompt_writer_avatar_section",
            "merged_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    else:
        bundle = {
            "version": 1,
            "source": "metadata_thumbnails",
            "target_platform": tp,
            "include_avatar": include_avatar,
            "thumbnail_hook_text": hook_text or None,
            "prompts": thumb_entries,
            "global_style": {
                "aspect_ratio": "16:9",
                "base_style_en": (
                    "YouTube thumbnail, cinematic, high contrast, bold composition, "
                    "sharp focus, no watermark"
                ),
            },
        }
        _carry_prompt_spine(bundle, work_dir)
        if include_avatar and thumb_entries:
            ad = thumb_entries[0].get("avatar_description")
            if ad:
                bundle["avatar_description"] = ad

    _write_json(out, bundle)
    return {
        "count": len(thumb_entries),
        "path": "pipeline/image_prompts.json",
        "include_avatar": include_avatar,
        "merge": merge,
        "hook_text": hook_text or None,
        "thumbnail_ids": [str(p.get("id") or "") for p in thumb_entries],
    }


def thumbnail_filename(thumb_index: int) -> str:
    return f"thumb_{int(thumb_index) + 1:02d}.png"


def sync_thumbnails_to_images_generation(work_dir: Path) -> dict[str, Any]:
    """Añade/actualiza filas ``role=thumbnail`` en images_generation.json sin tocar escenas."""
    prompts_path = _pipeline_dir(work_dir) / "image_prompts.json"
    if not prompts_path.is_file():
        raise ValueError("No existe pipeline/image_prompts.json. Prepara miniaturas antes.")

    try:
        bundle = json.loads(prompts_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError(f"No se pudo leer image_prompts.json: {e}") from e

    prompts_raw = bundle.get("prompts") if isinstance(bundle, dict) else None
    if not isinstance(prompts_raw, list):
        raise ValueError("image_prompts.json no contiene prompts.")

    thumb_prompts = [p for p in prompts_raw if isinstance(p, dict) and p.get("role") == "thumbnail"]
    if not thumb_prompts:
        raise ValueError(
            "No hay prompts con role=thumbnail. Usa «Preparar miniaturas» desde Metadata."
        )

    manifest_path = _pipeline_dir(work_dir) / "images_generation.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise ValueError(f"images_generation.json inválido: {e}") from e
        if not isinstance(manifest, dict):
            manifest = {}
    else:
        manifest = {}

    scene_images = [
        img
        for img in (manifest.get("images") or [])
        if isinstance(img, dict) and img.get("role") != "thumbnail"
    ]

    images_dir = work_dir / "pipeline" / "images"
    thumb_rows: list[dict[str, Any]] = []
    for i, prompt in enumerate(thumb_prompts):
        pid = str(prompt.get("id") or f"thumb_{i}")
        tidx = int(prompt.get("index") if isinstance(prompt.get("index"), int) else i)
        fn = thumbnail_filename(tidx)
        status = "generated" if (images_dir / fn).is_file() else "pending"
        order = _THUMB_ORDER_BASE + i + 1
        idea = str(prompt.get("text") or "").strip()
        thumb_rows.append(
            {
                "id": pid,
                "filename": fn,
                "act": "thumbnail",
                "order": order,
                "timestamp_hint": "0:00",
                "duration_hint_s": 1,
                "role": "thumbnail",
                "scene_description_es": idea[:240],
                "scene_prompt_en": str(prompt.get("scene_prompt_en") or "").strip() or None,
                "ai_prompt": str(prompt.get("ai_prompt") or prompt.get("text") or "").strip(),
                "negative_prompt": str(prompt.get("negative_prompt") or "").strip() or None,
                "status": status,
                "selected": True,
                "placeholder_alt": "Miniatura",
                "prompt_id": pid,
                "section": "thumbnail",
                "thumbnail_index": tidx,
            }
        )

    manifest["version"] = max(int(manifest.get("version") or 1), 2)
    manifest["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest["source"] = manifest.get("source") or "image_prompts"
    manifest["image_prompts_source"] = str(bundle.get("source") or "metadata_thumbnails")
    manifest["images"] = scene_images + thumb_rows
    manifest["total"] = len(manifest["images"])
    manifest["selected_count"] = sum(
        1 for r in manifest["images"] if isinstance(r, dict) and r.get("selected")
    )
    manifest["thumbnail_count"] = len(thumb_rows)

    manifest = sync_manifest_image_status(work_dir, manifest)
    save_manual_images_generation_bundle(work_dir, manifest)

    pending = sum(1 for r in thumb_rows if r.get("status") == "pending")
    generated = len(thumb_rows) - pending
    return {
        "path": "pipeline/images_generation.json",
        "thumbnail_count": len(thumb_rows),
        "thumbnail_ids": [str(r.get("id") or "") for r in thumb_rows],
        "pending": pending,
        "generated": generated,
        "scene_rows_preserved": len(scene_images),
    }


def prepare_metadata_thumbnails(
    work_dir: Path,
    *,
    include_avatar: bool = False,
    merge: bool = True,
) -> dict[str, Any]:
    """Prompts + manifest listo para generar solo miniaturas."""
    push_info = push_thumbnail_ideas_to_image_prompts(
        work_dir, include_avatar=include_avatar, merge=merge
    )
    sync_info = sync_thumbnails_to_images_generation(work_dir)
    return {"ok": True, "push": push_info, "manifest": sync_info}


def get_metadata_thumbnails_status(work_dir: Path) -> dict[str, Any]:
    meta_p = _pipeline_dir(work_dir) / "metadata.json"
    if meta_p.is_file():
        try:
            md = _read_metadata(work_dir)
            ideas, hook_text = extract_thumbnail_ideas(md)
        except ValueError:
            ideas, hook_text = [], ""
    else:
        ideas, hook_text = [], ""

    manifest_path = _pipeline_dir(work_dir) / "images_generation.json"
    manifest_thumbs = 0
    manifest_by_id: dict[str, dict[str, Any]] = {}
    if manifest_path.is_file():
        try:
            man = json.loads(manifest_path.read_text(encoding="utf-8"))
            for r in man.get("images") or []:
                if isinstance(r, dict) and r.get("role") == "thumbnail":
                    manifest_thumbs += 1
                    rid = str(r.get("id") or "")
                    if rid:
                        manifest_by_id[rid] = r
        except Exception:
            pass

    images_dir = work_dir / "pipeline" / "images"
    thumb_files: list[dict[str, Any]] = []
    for i, idea in enumerate(ideas):
        fn = thumbnail_filename(i)
        p = images_dir / fn
        pid = f"thumb_{i}"
        row = manifest_by_id.get(pid) or {}
        status = str(row.get("status") or ("generated" if p.is_file() else "pending"))
        thumb_files.append(
            {
                "index": i,
                "id": pid,
                "filename": fn,
                "idea": idea,
                "exists": p.is_file(),
                "bytes": p.stat().st_size if p.is_file() else 0,
                "status": status,
                "error": str(row.get("error") or "").strip() or None,
            }
        )

    return {
        "ideas": ideas,
        "hook_text": hook_text or None,
        "idea_count": len(ideas),
        "files": thumb_files,
        "manifest_thumbnail_rows": manifest_thumbs,
        "ready_to_generate": bool(ideas) and manifest_thumbs > 0,
    }


_THUMB_JOB_FILE = "thumbnail_generation_job.json"


def _thumb_job_path(work_dir: Path) -> Path:
    return _pipeline_dir(work_dir) / _THUMB_JOB_FILE


def read_thumbnail_generation_job(work_dir: Path) -> dict[str, Any]:
    p = _thumb_job_path(work_dir)
    if not p.is_file():
        return {"state": "idle"}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"state": "idle"}
    except Exception:
        return {"state": "idle"}


def write_thumbnail_generation_job(work_dir: Path, data: dict[str, Any]) -> dict[str, Any]:
    p = _thumb_job_path(work_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {**data, "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def get_thumbnail_generation_status(work_dir: Path) -> dict[str, Any]:
    """Estado del job en segundo plano + miniaturas en disco/manifest."""
    base = get_metadata_thumbnails_status(work_dir)
    job = read_thumbnail_generation_job(work_dir)
    return {**base, "job": job}


async def run_thumbnail_generation_job(
    work_dir: Path,
    *,
    work_slug: str,
    regenerate: bool = False,
) -> None:
    from videomaker.pipeline.images_generation_runner import generate_selected_images

    write_thumbnail_generation_job(
        work_dir,
        {
            "state": "running",
            "work": work_slug,
            "backend": "openai",
            "current": 0,
            "total": 0,
            "current_id": "",
            "detail": "Iniciando generación de miniaturas…",
        },
    )

    def _on_progress(evt: dict[str, Any]) -> None:
        write_thumbnail_generation_job(
            work_dir,
            {
                "state": "running",
                "work": work_slug,
                "backend": "openai",
                "current": int(evt.get("index") or 0),
                "total": int(evt.get("total") or 0),
                "current_id": str(evt.get("id") or ""),
                "detail": (
                    f"Generando {evt.get('filename') or evt.get('id') or 'miniatura'} "
                    f"({evt.get('index')}/{evt.get('total')}) — OpenAI puede tardar 1–3 min por imagen"
                ),
            },
        )

    try:
        status = get_metadata_thumbnails_status(work_dir)
        if not status.get("ready_to_generate"):
            sync_thumbnails_to_images_generation(work_dir)
            status = get_metadata_thumbnails_status(work_dir)

        thumb_ids = [str(f.get("id") or "") for f in (status.get("files") or []) if f.get("id")]
        if not thumb_ids:
            raise ValueError("No hay miniaturas preparadas en el manifest.")

        write_thumbnail_generation_job(
            work_dir,
            {
                "state": "running",
                "work": work_slug,
                "backend": "openai",
                "current": 0,
                "total": len(thumb_ids),
                "detail": f"Generando {len(thumb_ids)} miniatura(s) con OpenAI…",
            },
        )

        result = await generate_selected_images(
            work_dir,
            work_slug=work_slug,
            image_ids=thumb_ids,
            skip_generated=not regenerate,
            regenerate=regenerate,
            image_backend="openai",
            on_progress=_on_progress,
        )
        write_thumbnail_generation_job(
            work_dir,
            {
                "state": "done",
                "work": work_slug,
                "result": result,
                "detail": (
                    f"Listo: {result.get('generated', 0)} OK"
                    + (f", {result.get('failed', 0)} error(es)" if result.get("failed") else "")
                ),
            },
        )
    except Exception as exc:
        write_thumbnail_generation_job(
            work_dir,
            {"state": "error", "work": work_slug, "detail": str(exc)},
        )
