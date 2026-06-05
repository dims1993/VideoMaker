"""Quita la marca de agua (rombo/estrella) de imágenes generadas en Gemini web."""

from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from videomaker.pipeline.images_generation_runner import images_dir, load_manifest, order_filename

Corner = Literal["bottom-right", "bottom-left"]


def _require_cv2():
    try:
        import cv2  # noqa: F401

        return cv2
    except ImportError as e:
        raise RuntimeError(
            "Falta opencv-python-headless. En el venv: pip install opencv-python-headless"
        ) from e


def watermark_corner() -> Corner:
    raw = (os.getenv("GEMINI_WATERMARK_CORNER") or "bottom-right").strip().lower()
    if raw in ("bottom-left", "bl", "left"):
        return "bottom-left"
    return "bottom-right"


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _corner_anchor(h: int, w: int, corner: Corner) -> tuple[int, int]:
    """Fallback: centro del rombo (~2.8% desde la esquina en imágenes Gemini)."""
    m = min(h, w)
    margin = max(16, int(m * _env_float("GEMINI_WATERMARK_MARGIN_RATIO", 0.028)))
    if corner == "bottom-right":
        return w - margin, h - margin
    return margin, h - margin


def _find_watermark_center(img_bgr, corner: Corner) -> tuple[int, int]:
    """Localiza el centro del logo por brillo en la esquina."""
    import numpy as np

    h, w = img_bgr.shape[:2]
    m = min(h, w)
    box = max(80, int(m * _env_float("GEMINI_WATERMARK_SEARCH_RATIO", 0.075)))
    if corner == "bottom-right":
        x0, y0 = w - box, h - box
        region = img_bgr[y0:h, x0:w]
    else:
        x0, y0 = 0, h - box
        region = img_bgr[y0:h, x0:box]

    if region.size == 0:
        return _corner_anchor(h, w, corner)

    import cv2

    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY).astype(np.float32)
    rh, rw = gray.shape[:2]
    edge = max(3, min(rh, rw) // 14)
    ring = np.concatenate(
        [
            gray[:edge, :].ravel(),
            gray[-edge:, :].ravel(),
            gray[:, :edge].ravel(),
            gray[:, -edge:].ravel(),
        ]
    )
    bg = float(np.median(ring))
    yy, xx = np.mgrid[0:rh, 0:rw]
    if corner == "bottom-right":
        weights = (xx / max(rw, 1)) ** 1.4 * (yy / max(rh, 1)) ** 1.4
    else:
        weights = (1.0 - xx / max(rw, 1)) ** 1.4 * (yy / max(rh, 1)) ** 1.4
    score = np.maximum(0.0, gray - bg - 2.0) * weights
    peak = float(np.max(score))
    if peak < 4.0:
        return _corner_anchor(h, w, corner)
    thr = max(4.0, peak * 0.35)
    ys, xs = np.where(score >= thr)
    if len(xs) < 8:
        return _corner_anchor(h, w, corner)
    cx = int(round(float(np.mean(xs)))) + x0
    cy = int(round(float(np.mean(ys)))) + y0
    return cx, cy


def _fixed_rhombus_mask(
    h: int,
    w: int,
    corner: Corner,
    center: tuple[int, int],
):
    """Rombo completo del logo Gemini centrado en ``center``."""
    import cv2
    import numpy as np

    cv2 = _require_cv2()
    cx, cy = center
    m = min(h, w)
    radius = max(32, int(m * _env_float("GEMINI_WATERMARK_R_RATIO", 0.042)))
    pts = np.array(
        [
            [cx, cy - radius],
            [cx + radius, cy],
            [cx, cy + radius],
            [cx - radius, cy],
        ],
        dtype=np.int32,
    )
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillConvexPoly(mask, pts, 255)
    dilate = _env_int("GEMINI_WATERMARK_DILATE", 7)
    ksize = _env_int("GEMINI_WATERMARK_KERNEL", 17)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ksize, ksize))
    mask = cv2.dilate(mask, kernel, dilate)
    return mask


def _detect_watermark_mask(img_bgr, corner: Corner | None = None):
    """Detecta overlay + rombo completo en la posición real del logo."""
    import cv2
    import numpy as np

    cv2 = _require_cv2()
    corner = corner or watermark_corner()
    h, w = img_bgr.shape[:2]
    center = _find_watermark_center(img_bgr, corner)
    m = min(h, w)
    box = max(72, int(m * _env_float("GEMINI_WATERMARK_BOX_RATIO", 0.09)))
    cx, cy = center

    if corner == "bottom-right":
        x0 = max(0, cx - box // 2)
        y0 = max(0, cy - box // 2)
        x1 = min(w, cx + box // 2)
        y1 = min(h, cy + box // 2)
    else:
        x0 = max(0, cx - box // 2)
        y0 = max(0, cy - box // 2)
        x1 = min(w, cx + box // 2)
        y1 = min(h, cy + box // 2)

    region = img_bgr[y0:y1, x0:x1]
    rh, rw = region.shape[:2]
    patch = np.zeros((rh, rw), dtype=np.uint8)
    if region.size == 0:
        return _fixed_rhombus_mask(h, w, corner, center)

    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY).astype(np.float32)
    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    v_channel = hsv[:, :, 2].astype(np.float32)
    s_channel = hsv[:, :, 1].astype(np.float32)

    edge = max(4, min(rh, rw) // 10)
    ring = np.concatenate(
        [
            gray[:edge, :].ravel(),
            gray[-edge:, :].ravel(),
            gray[:, :edge].ravel(),
            gray[:, -edge:].ravel(),
        ]
    )
    bg = float(np.median(ring))

    diff_thresh = _env_float("GEMINI_WATERMARK_DIFF_THRESH", 4.0)
    diff = gray - bg
    by_diff = (diff > diff_thresh).astype(np.uint8) * 255
    by_hsv = ((v_channel > bg + 2) & (s_channel < 115)).astype(np.uint8) * 255
    by_bright = ((v_channel > _env_int("GEMINI_WATERMARK_V_THRESH", 100)) & (s_channel < 100)).astype(
        np.uint8
    ) * 255
    cand = cv2.bitwise_or(cv2.bitwise_or(by_diff, by_hsv), by_bright)
    blur = cv2.GaussianBlur(gray, (0, 0), 1.4)
    cand = cv2.bitwise_or(cand, (blur > bg + 2).astype(np.uint8) * 255)

    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13))
    cand = cv2.morphologyEx(cand, cv2.MORPH_CLOSE, k, iterations=3)
    cand = cv2.dilate(cand, k, iterations=3)
    patch = cand

    detected = np.zeros((h, w), dtype=np.uint8)
    detected[y0:y1, x0:x1] = patch
    fixed = _fixed_rhombus_mask(h, w, corner, center)
    combined = cv2.bitwise_or(detected, fixed)
    k_final = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, k_final, iterations=2)
    return combined


def build_watermark_mask(img_bgr, corner: Corner | None = None):
    return _detect_watermark_mask(img_bgr, corner)


def _patch_fill_watermark(img_bgr, mask):
    """Rellena la zona enmascarada copiando textura del fondo inmediato (encima/izquierda)."""
    import cv2
    import numpy as np

    out = img_bgr.copy()
    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        return out

    h, w = out.shape[:2]
    y0, y1 = int(ys.min()), int(ys.max())
    x0, x1 = int(xs.min()), int(xs.max())
    bh = y1 - y0 + 1
    bw = x1 - x0 + 1
    pad = max(4, int(min(h, w) * 0.008))

    src_y0 = max(0, y0 - bh - pad)
    src_y1 = src_y0 + bh
    src_x0 = max(0, x0 - pad)
    src_x1 = min(w, x1 + 1 + pad)
    source = out[src_y0:src_y1, src_x0:src_x1]
    if source.size == 0 or source.shape[0] < 2:
        src_y0 = max(0, y0 - bh // 2)
        source = out[src_y0 : src_y0 + bh, x0 : x1 + 1]

    patch = cv2.resize(source, (bw, bh), interpolation=cv2.INTER_LINEAR)
    m = mask[y0 : y1 + 1, x0 : x1 + 1].astype(np.float32) / 255.0
    m = cv2.GaussianBlur(m, (0, 0), 2.5)
    m3 = np.stack([m, m, m], axis=2)
    orig = out[y0 : y1 + 1, x0 : x1 + 1].astype(np.float32)
    blended = orig * (1.0 - m3) + patch.astype(np.float32) * m3
    out[y0 : y1 + 1, x0 : x1 + 1] = np.clip(blended, 0, 255).astype(np.uint8)
    return out


def remove_gemini_watermark_from_path(
    src: Path,
    *,
    dest: Path | None = None,
    corner: Corner | None = None,
) -> dict[str, Any]:
    """Inpainting local; sobrescribe dest si es None."""
    cv2 = _require_cv2()

    src = Path(src)
    if not src.is_file():
        raise FileNotFoundError(str(src))
    dest = Path(dest) if dest is not None else src

    img = cv2.imread(str(src), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"No se pudo leer la imagen: {src.name}")

    h, w = img.shape[:2]
    mask = build_watermark_mask(img, corner)
    radius = max(10, _env_int("GEMINI_WATERMARK_INPAINT_RADIUS", 22))
    result = cv2.inpaint(img, mask, radius, cv2.INPAINT_NS)
    result = _patch_fill_watermark(result, mask)
    result = cv2.inpaint(result, mask, max(6, radius // 3), cv2.INPAINT_TELEA)

    import numpy as np

    gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
    lap = cv2.Laplacian(gray, cv2.CV_16S, ksize=3)
    lap = np.abs(lap).astype(np.float32)
    ys, xs = np.where(mask > 0)
    if len(xs):
        y0, y1 = int(ys.min()), int(ys.max())
        x0, x1 = int(xs.min()), int(xs.max())
        pad = 6
        y0, y1 = max(0, y0 - pad), min(h - 1, y1 + pad)
        x0, x1 = max(0, x0 - pad), min(w - 1, x1 + pad)
        sub_lap = lap[y0 : y1 + 1, x0 : x1 + 1]
        if sub_lap.size and float(np.max(sub_lap)) > 25:
            touch = np.zeros((h, w), np.uint8)
            touch[y0 : y1 + 1, x0 : x1 + 1] = (sub_lap > 20).astype(np.uint8) * 255
            touch = cv2.dilate(touch, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)), 1)
            if touch.sum() > 0:
                result = _patch_fill_watermark(result, touch)
                result = cv2.inpaint(result, touch, 8, cv2.INPAINT_NS)

    dest.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(dest), result):
        raise OSError(f"No se pudo escribir {dest}")

    mask_px = int(mask.sum()) // 255
    return {
        "filename": dest.name,
        "width": int(img.shape[1]),
        "height": int(img.shape[0]),
        "mask_pixels": mask_px,
        "bytes": dest.stat().st_size,
    }


def _latest_backup_dir(work_dir: Path) -> Path | None:
    root = work_dir / "pipeline" / "images" / "_backup_before_watermark"
    if not root.is_dir():
        return None
    dirs = sorted((p for p in root.iterdir() if p.is_dir()), reverse=True)
    return dirs[0] if dirs else None


def _source_image_path(work_dir: Path, out_dir: Path, filename: str, *, prefer_backup: bool) -> Path:
    if prefer_backup:
        backup = _latest_backup_dir(work_dir)
        if backup is not None:
            candidate = backup / filename
            if candidate.is_file():
                return candidate
    return out_dir / filename


def _backup_dir(work_dir: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    d = work_dir / "pipeline" / "images" / "_backup_before_watermark" / stamp
    d.mkdir(parents=True, exist_ok=True)
    return d


def remove_gemini_watermarks_in_work(
    work_dir: Path,
    *,
    image_ids: list[str] | None = None,
    backup: bool = True,
    prefer_backup_source: bool = True,
) -> dict[str, Any]:
    """Procesa PNGs en pipeline/images/ (manifest o lista de IDs)."""
    work_dir = Path(work_dir)
    manifest = load_manifest(work_dir)
    out_dir = images_dir(work_dir)
    wanted = {str(i) for i in (image_ids or [])} if image_ids else None

    rows: list[dict[str, Any]] = []
    for row in manifest.get("images") or []:
        if not isinstance(row, dict):
            continue
        rid = str(row.get("id") or "")
        if wanted is not None and rid not in wanted:
            continue
        order = int(row.get("order") or 0)
        if order <= 0:
            continue
        fn = str(row.get("filename") or order_filename(order))
        src = _source_image_path(work_dir, out_dir, fn, prefer_backup=prefer_backup_source)
        dest = out_dir / fn
        if not src.is_file() and not dest.is_file():
            continue
        rows.append({"id": rid, "order": order, "src": src, "dest": dest, "filename": fn})

    if not rows:
        raise ValueError("No hay imágenes PNG en disco para procesar.")

    backup_root: Path | None = None
    if backup and not prefer_backup_source:
        backup_root = _backup_dir(work_dir)

    processed: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for item in rows:
        src: Path = item["src"]
        dest: Path = item["dest"]
        try:
            if backup_root is not None and dest.is_file():
                shutil.copy2(dest, backup_root / dest.name)
            info = remove_gemini_watermark_from_path(src, dest=dest)
            info["source"] = str(src)
            processed.append({**item, **info})
        except Exception as e:
            errors.append({"filename": dest.name, "detail": str(e)[:300]})

    return {
        "processed": len(processed),
        "failed": len(errors),
        "backup_dir": str(backup_root) if backup_root else None,
        "source_backup": str(_latest_backup_dir(work_dir)) if prefer_backup_source else None,
        "items": processed,
        "errors": errors,
    }
