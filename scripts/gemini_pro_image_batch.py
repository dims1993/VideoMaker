#!/usr/bin/env python3
"""
Genera imágenes en lote usando Gemini web (Google AI Pro en el navegador).

La suscripción Pro NO alimenta la API de prepago; este script usa tu sesión
logueada en gemini.google.com.

Modos
-----
  assist  — Copia cada prompt al portapapeles; tú generas en Gemini; el script
            detecta el PNG más reciente en Descargas y lo mueve a pipeline/images/.
  auto    — Automatiza pegar/enviar/descargar vía Chrome con depuración remota (CDP).

Uso rápido (modo assist, recomendado la primera vez)
---------------------------------------------------
  cd /ruta/al/repo
  source .venv/bin/activate
  python scripts/gemini_pro_image_batch.py --work output/ui_session --orders 12

Uso auto (Chrome con tu cuenta Pro)
-----------------------------------
  1. Cierra Chrome por completo.
  2. Abre Chrome con depuración remota (macOS):

     /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome \\
       --remote-debugging-port=9222 --user-data-dir=\"$HOME/.videomaker-chrome-profile\"

  3. Inicia sesión en Google y abre https://gemini.google.com/app
  4. En otra terminal:

     python scripts/gemini_pro_image_batch.py --mode auto --work output/ui_session --limit 5

Requisitos auto: pip install playwright && playwright install chromium
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "apps" / "backend") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "apps" / "backend"))

GEMINI_URL = "https://gemini.google.com/app"


def order_filename(order: int) -> str:
    return f"{int(order):03d}.png"


def parse_orders(spec: str | None) -> set[int] | None:
    if not spec or not spec.strip():
        return None
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return out


def load_rows(work_dir: Path, *, orders: set[int] | None, only_pending: bool) -> list[dict[str, Any]]:
    from videomaker.pipeline.images_generation_runner import load_manifest

    manifest = load_manifest(work_dir)
    rows = [r for r in (manifest.get("images") or []) if isinstance(r, dict)]
    rows.sort(key=lambda r: int(r.get("order") or 0))

    if orders is not None:
        rows = [r for r in rows if int(r.get("order") or 0) in orders]

    if only_pending:
        rows = [r for r in rows if r.get("status") != "generated"]

    return rows


def save_manifest(work_dir: Path, manifest: dict[str, Any]) -> None:
    from videomaker.pipeline.runner import save_manual_images_generation_bundle

    save_manual_images_generation_bundle(work_dir, manifest)


def mark_generated(work_dir: Path, order: int, filename: str) -> None:
    from videomaker.pipeline.images_generation_runner import load_manifest

    manifest = load_manifest(work_dir)
    for row in manifest.get("images") or []:
        if isinstance(row, dict) and int(row.get("order") or 0) == order:
            row["status"] = "generated"
            row["filename"] = filename
            row.pop("error", None)
            break
    save_manifest(work_dir, manifest)


def copy_to_clipboard(text: str) -> None:
    if sys.platform == "darwin":
        subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
    elif sys.platform.startswith("linux"):
        subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode("utf-8"), check=True)
    else:
        print(text[:200], "…\n(portapapeles no disponible en esta OS; copia manual)")


def newest_png_since(folder: Path, since: float) -> Path | None:
    if not folder.is_dir():
        return None
    best: Path | None = None
    best_mtime = since
    for p in folder.glob("*.png"):
        try:
            m = p.stat().st_mtime
        except OSError:
            continue
        if m >= since and m >= best_mtime:
            best = p
            best_mtime = m
    for p in folder.glob("*.PNG"):
        try:
            m = p.stat().st_mtime
        except OSError:
            continue
        if m >= since and m >= best_mtime:
            best = p
            best_mtime = m
    return best


def move_to_pipeline(work_dir: Path, order: int, src: Path) -> Path:
    dest = work_dir / "pipeline" / "images" / order_filename(order)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest


def run_assist(
    work_dir: Path,
    rows: list[dict[str, Any]],
    *,
    downloads_dir: Path,
    open_browser: bool,
) -> None:
    if not rows:
        print("No hay filas para procesar.")
        return

    print(f"\nModo ASISTIDO — {len(rows)} imagen(es)")
    print("Abre https://gemini.google.com/app con tu cuenta Pro.")
    print("Modo imagen: elige «Crear imagen» / Nano Banana si te lo pide.\n")

    if open_browser:
        if sys.platform == "darwin":
            subprocess.run(["open", GEMINI_URL], check=False)

    for i, row in enumerate(rows, start=1):
        order = int(row["order"])
        prompt = str(row.get("ai_prompt") or "").strip()
        if not prompt:
            print(f"[{i}/{len(rows)}] Orden {order}: sin prompt, omitido.")
            continue

        dest = work_dir / "pipeline" / "images" / order_filename(order)
        if dest.is_file():
            ans = input(f"  {order_filename(order)} ya existe. ¿Sobrescribir? [s/N] ").strip().lower()
            if ans not in ("s", "si", "sí", "y", "yes"):
                print("  Omitido.")
                continue

        copy_to_clipboard(prompt)
        started = time.time()
        print(f"\n[{i}/{len(rows)}] Orden {order} → {order_filename(order)}")
        print(f"  Prompt copiado ({len(prompt)} chars). Pega en Gemini y genera la imagen.")
        print("  Descarga el PNG (o déjalo en Descargas).")
        try:
            input("  Pulsa Enter cuando la imagen esté lista… ")
        except KeyboardInterrupt:
            print("\nInterrumpido.")
            return

        # ¿Ya guardó directo en pipeline/images?
        if dest.is_file() and dest.stat().st_mtime >= started - 2:
            mark_generated(work_dir, order, dest.name)
            print(f"  ✓ Detectado en {dest}")
            continue

        found = newest_png_since(downloads_dir, started - 5)
        if found:
            move_to_pipeline(work_dir, order, found)
            mark_generated(work_dir, order, order_filename(order))
            print(f"  ✓ Movido desde Descargas: {found.name} → {dest}")
        else:
            manual = input(f"  Ruta al PNG (Enter para omitir): ").strip()
            if manual and Path(manual).is_file():
                move_to_pipeline(work_dir, order, Path(manual))
                mark_generated(work_dir, order, order_filename(order))
                print(f"  ✓ Guardado en {dest}")
            else:
                print("  No se encontró PNG nuevo en Descargas.")

    print("\nListo. Recarga Images Generation en Videomaker.")


def run_auto_cdp(
    work_dir: Path,
    rows: list[dict[str, Any]],
    *,
    cdp_url: str,
    delay_s: float,
    work_slug: str,
) -> None:
    import os

    from videomaker.engines.gemini_web_batch import run_gemini_web_batch

    if not rows:
        print("No hay filas para procesar.")
        return

    os.environ["GEMINI_WEB_CDP_URL"] = cdp_url
    os.environ["GEMINI_WEB_DELAY_SEC"] = str(delay_s)

    image_ids = [str(r.get("id") or "") for r in rows if r.get("id")]
    print(f"\nModo AUTO (CDP) — {len(image_ids)} imagen(es) — misma conversación Gemini")
    print("Preferible usar la app: Images Generation → Generar con Gemini Pro\n")

    def _log(msg: str) -> None:
        print(msg)

    result = run_gemini_web_batch(
        work_dir,
        work_slug=work_slug,
        image_ids=image_ids,
        skip_generated=True,
        log=_log,
    )
    print(f"\nListo: {result.get('generated')} ok, {result.get('failed')} fallos.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch imágenes vía Gemini web (Google AI Pro)")
    parser.add_argument("--work", default="output/ui_session", help="Carpeta de sesión")
    parser.add_argument("--mode", choices=("assist", "auto"), default="assist")
    parser.add_argument("--orders", default=None, help="Ej: 12 o 1,2,5-10")
    parser.add_argument("--all", action="store_true", help="Incluir ya generadas (solo assist útil)")
    parser.add_argument("--limit", type=int, default=0, help="Máximo N imágenes esta sesión")
    parser.add_argument("--cdp", default="http://127.0.0.1:9222", help="URL depuración Chrome")
    parser.add_argument("--delay", type=float, default=25.0, help="Segundos espera tras enviar (auto)")
    parser.add_argument("--downloads", default=None, help="Carpeta Descargas (assist)")
    parser.add_argument("--no-open", action="store_true", help="No abrir gemini.google.com (assist)")
    args = parser.parse_args()

    work_dir = (REPO_ROOT / args.work).resolve()
    if not work_dir.is_dir():
        raise SystemExit(f"No existe work dir: {work_dir}")

    orders = parse_orders(args.orders)
    only_pending = not args.all
    rows = load_rows(work_dir, orders=orders, only_pending=only_pending)

    if args.limit > 0:
        rows = rows[: args.limit]

    downloads = Path(args.downloads).expanduser() if args.downloads else Path.home() / "Downloads"

    if args.mode == "assist":
        run_assist(work_dir, rows, downloads_dir=downloads, open_browser=not args.no_open)
    else:
        run_auto_cdp(work_dir, rows, cdp_url=args.cdp, delay_s=args.delay, work_slug=args.work)


if __name__ == "__main__":
    main()
