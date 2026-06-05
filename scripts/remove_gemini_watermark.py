#!/usr/bin/env python3
"""Quita la marca de agua de Gemini en pipeline/images/*.png."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "apps" / "backend") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "apps" / "backend"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Quitar marca de agua Gemini (esquina inferior).")
    parser.add_argument("--work", default="output/ui_session", help="Carpeta de sesión")
    parser.add_argument("--no-backup", action="store_true", help="No copiar originales a _backup_before_watermark")
    parser.add_argument(
        "--no-prefer-backup",
        action="store_true",
        help="No usar el backup previo como fuente (reprocessa el PNG actual)",
    )
    args = parser.parse_args()

    work_dir = (REPO_ROOT / args.work).resolve()
    from videomaker.pipeline.gemini_watermark import remove_gemini_watermarks_in_work

    result = remove_gemini_watermarks_in_work(
        work_dir,
        backup=not args.no_backup,
        prefer_backup_source=not args.no_prefer_backup,
    )
    print(f"Procesadas: {result['processed']} · Fallos: {result['failed']}")
    if result.get("backup_dir"):
        print(f"Backup: {result['backup_dir']}")
    for err in result.get("errors") or []:
        print(f"  ✗ {err.get('filename')}: {err.get('detail')}")
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
