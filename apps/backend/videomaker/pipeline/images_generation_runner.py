"""Generación batch de imágenes seleccionadas en images_generation.json."""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from collections.abc import Callable
from typing import Any

from videomaker.engines.google_imagen import (
    GoogleImagenError,
    generate_image_to_path as google_generate_image_to_path,
    local_image_api_url,
    use_mock as google_use_mock,
)
from videomaker.engines.openai_images import (
    OpenAIImagesError,
    generate_image_to_path as openai_generate_image_to_path,
    use_mock as openai_use_mock,
)

ImageGenerationError = GoogleImagenError | OpenAIImagesError
from videomaker.pipeline.image_prompts_to_images import sync_manifest_image_status
from videomaker.pipeline.runner import save_manual_images_generation_bundle


def order_filename(order: int) -> str:
    return f"{int(order):03d}.png"


def images_dir(work_dir: Path) -> Path:
    d = work_dir / "pipeline" / "images"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_manifest(work_dir: Path) -> dict[str, Any]:
    p = work_dir / "pipeline" / "images_generation.json"
    if not p.is_file():
        raise ValueError("No existe pipeline/images_generation.json.")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError(f"Manifest inválido: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("Manifest inválido.")
    return sync_manifest_image_status(work_dir, data)


def _batch_delay_sec() -> float:
    try:
        return max(0.0, float(os.getenv("GOOGLE_IMAGEN_BATCH_DELAY_SEC", "1.5")))
    except ValueError:
        return 1.5


def normalize_manifest_filenames(manifest: dict[str, Any]) -> None:
    """Escenas → ``001.png``; miniaturas metadata → ``thumb_01.png`` (no usar order 10001)."""
    for row in manifest.get("images") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("role") or "") == "thumbnail":
            row["act"] = "thumbnail"
            tidx = row.get("thumbnail_index")
            if isinstance(tidx, int):
                row["filename"] = f"thumb_{tidx + 1:02d}.png"
            continue
        order = row.get("order")
        if isinstance(order, int) and order > 0:
            row["filename"] = order_filename(order)


def _normalize_manifest_filenames(manifest: dict[str, Any]) -> None:
    normalize_manifest_filenames(manifest)


def _apply_selection_from_ids(manifest: dict[str, Any], image_ids: list[str]) -> set[str]:
    """Sincroniza selected en disco con los IDs que envía la UI."""
    wanted = {str(i) for i in image_ids}
    for row in manifest.get("images") or []:
        if not isinstance(row, dict):
            continue
        rid = str(row.get("id") or "")
        row["selected"] = rid in wanted
    manifest["selected_count"] = sum(
        1 for r in (manifest.get("images") or []) if isinstance(r, dict) and r.get("selected")
    )
    return wanted


def _reset_stale_errors(manifest: dict[str, Any], wanted: set[str]) -> int:
    """Quita errores de intentos anteriores en imágenes que no van en este batch."""
    cleared = 0
    for row in manifest.get("images") or []:
        if not isinstance(row, dict):
            continue
        rid = str(row.get("id") or "")
        if rid in wanted:
            continue
        if row.get("status") == "error":
            row["status"] = "pending"
            row.pop("error", None)
            cleared += 1
    return cleared


def clear_all_image_errors(manifest: dict[str, Any]) -> int:
    """Resetea todas las tarjetas en error a pending (p. ej. tras reiniciar dev.sh)."""
    cleared = 0
    for row in manifest.get("images") or []:
        if not isinstance(row, dict):
            continue
        if row.get("status") == "error":
            row["status"] = "pending"
            row.pop("error", None)
            cleared += 1
    return cleared


def _batch_delay_sec_for(backend: str) -> float:
    key = (
        "OPENAI_IMAGES_BATCH_DELAY_SEC"
        if backend == "openai"
        else "GOOGLE_IMAGEN_BATCH_DELAY_SEC"
    )
    default = "1.0" if backend == "openai" else "1.5"
    try:
        return max(0.0, float(os.getenv(key, default)))
    except ValueError:
        return float(default)


def _generator_label(backend: str) -> tuple[str, bool]:
    if backend == "openai":
        return ("openai_images_mock" if openai_use_mock() else "openai_images", openai_use_mock())
    return ("google_imagen_mock" if google_use_mock() else "google_imagen", google_use_mock())


async def generate_selected_images(
    work_dir: Path,
    *,
    work_slug: str,
    image_ids: list[str] | None = None,
    skip_generated: bool = True,
    regenerate: bool = False,
    image_backend: str = "google",
    on_progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    manifest = load_manifest(work_dir)
    _normalize_manifest_filenames(manifest)

    rows = [r for r in (manifest.get("images") or []) if isinstance(r, dict)]
    stale_errors_cleared = 0
    if image_ids:
        wanted = _apply_selection_from_ids(manifest, image_ids)
        stale_errors_cleared = _reset_stale_errors(manifest, wanted)
        rows = [r for r in rows if str(r.get("id")) in wanted]
        save_manual_images_generation_bundle(work_dir, manifest)
    else:
        rows = [r for r in rows if r.get("selected", True) is not False]

    if skip_generated and not regenerate:
        rows = [r for r in rows if r.get("status") != "generated"]

    if not rows:
        raise ValueError("No hay imágenes seleccionadas pendientes de generar.")

    rows = [r for r in rows if str(r.get("role") or "") != "thumbnail"]
    if not rows:
        raise ValueError(
            "Las miniaturas (thumb_*.png) se generan desde Metadata con OpenAI, no desde este paso."
        )

    rows.sort(key=lambda r: int(r.get("order") or 0))

    backend = (image_backend or "google").strip().lower()
    if backend not in ("google", "openai"):
        raise ValueError(f"image_backend no soportado: {image_backend}")

    generate_fn = openai_generate_image_to_path if backend == "openai" else google_generate_image_to_path

    out_dir = images_dir(work_dir)
    delay = _batch_delay_sec_for(backend)
    generated = 0
    failed = 0
    errors: list[dict[str, str]] = []
    results: list[dict[str, Any]] = []

    total_rows = len(rows)
    for row_index, row in enumerate(rows):
        order = int(row.get("order") or 0)
        if order <= 0:
            failed += 1
            errors.append({"id": str(row.get("id") or ""), "detail": "order inválido"})
            continue

        if str(row.get("role") or "") == "thumbnail":
            tidx = row.get("thumbnail_index")
            filename = (
                f"thumb_{int(tidx) + 1:02d}.png"
                if isinstance(tidx, int)
                else str(row.get("filename") or order_filename(order))
            )
        else:
            filename = order_filename(order)
        row["filename"] = filename
        prompt = str(row.get("ai_prompt") or "").strip()
        negative = row.get("negative_prompt")
        neg_str = str(negative).strip() if negative else None
        out_path = out_dir / filename

        row["status"] = "generating"
        row.pop("error", None)
        manifest["selected_count"] = sum(
            1 for r in (manifest.get("images") or []) if isinstance(r, dict) and r.get("selected", True)
        )
        save_manual_images_generation_bundle(work_dir, manifest)
        if on_progress:
            on_progress(
                {
                    "phase": "generating",
                    "index": row_index + 1,
                    "total": total_rows,
                    "id": str(row.get("id") or ""),
                    "filename": filename,
                }
            )

        try:
            meta = await asyncio.to_thread(
                generate_fn,
                prompt,
                out_path,
                negative_prompt=neg_str,
            )
            row["status"] = "generated"
            row.pop("error", None)
            url = local_image_api_url(work_slug, filename)
            row["local_url"] = url
            generated += 1
            results.append(
                {
                    "id": str(row.get("id") or ""),
                    "order": order,
                    "filename": filename,
                    "local_url": url,
                    "mode": meta.get("mode"),
                    "model": meta.get("model"),
                }
            )
        except (GoogleImagenError, OpenAIImagesError, OSError) as e:
            row["status"] = "error"
            row["error"] = str(e)
            failed += 1
            errors.append({"id": str(row.get("id") or ""), "detail": str(e)})

        manifest["selected_count"] = sum(
            1 for r in (manifest.get("images") or []) if isinstance(r, dict) and r.get("selected", True)
        )
        save_manual_images_generation_bundle(work_dir, manifest)

        if delay > 0:
            await asyncio.sleep(delay)

    manifest["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    gen_label, is_mock = _generator_label(backend)
    manifest["generator"] = gen_label
    save_manual_images_generation_bundle(work_dir, manifest)

    return {
        "generated": generated,
        "failed": failed,
        "total_requested": len(rows),
        "stale_errors_cleared": stale_errors_cleared,
        "image_backend": backend,
        "mock": is_mock,
        "results": results,
        "errors": errors,
    }


def delete_selected_images(
    work_dir: Path,
    *,
    image_ids: list[str],
) -> dict[str, Any]:
    """Elimina PNGs del disco y marca las entradas del manifest como pending."""
    if not image_ids:
        raise ValueError("No hay imágenes seleccionadas.")

    manifest = load_manifest(work_dir)
    _normalize_manifest_filenames(manifest)
    wanted = {str(i) for i in image_ids}

    out_dir = images_dir(work_dir)
    deleted_files = 0
    updated = 0
    missing_files: list[str] = []

    for row in manifest.get("images") or []:
        if not isinstance(row, dict):
            continue
        rid = str(row.get("id") or "")
        if rid not in wanted:
            continue

        filename = Path(str(row.get("filename") or "")).name
        if not filename:
            order = int(row.get("order") or 0)
            if order > 0 and str(row.get("role") or "") != "thumbnail":
                filename = order_filename(order)
        if not filename:
            continue
        row["filename"] = filename

        path = out_dir / filename
        if path.is_file():
            path.unlink()
            deleted_files += 1
        else:
            missing_files.append(filename)

        row["status"] = "pending"
        row.pop("error", None)
        row.pop("local_url", None)
        updated += 1

    if updated == 0:
        raise ValueError("Ningún ID coincide con el manifest.")

    manifest["selected_count"] = sum(
        1 for r in (manifest.get("images") or []) if isinstance(r, dict) and r.get("selected")
    )
    save_manual_images_generation_bundle(work_dir, manifest)

    return {
        "deleted": deleted_files,
        "updated": updated,
        "files_missing": len(missing_files),
        "manifest": manifest,
    }
