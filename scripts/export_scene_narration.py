#!/usr/bin/env python3
"""Une los MP3/WAV de scene_audio/ en narracion.wav (orden del Scene Editor)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "apps" / "backend") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "apps" / "backend"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", default="output/ui_session")
    parser.add_argument("--gap-ms", type=int, default=0, help="Silencio entre bloques")
    args = parser.parse_args()

    work_dir = (REPO_ROOT / args.work).resolve()
    from videomaker.scene_editor.audio_service import export_chunks_to_narration_wav
    from videomaker.scene_editor.store import read_chunks
    from videomaker.web.io_util import finalize_new_narration

    chunks = read_chunks(work_dir) or []
    if not chunks:
        print("No hay chunks en scene_editor.json")
        return 1

    result = export_chunks_to_narration_wav(work_dir, chunks, chunk_gap_ms=args.gap_ms)
    finalize_new_narration(work_dir)
    vo = work_dir / "pipeline" / "voiceovers.json"
    vo.parent.mkdir(parents=True, exist_ok=True)
    vo.write_text(
        json.dumps(
            {
                "wav": "narracion.wav",
                "duration_s": result["duration_s"],
                "source": "scene_editor_chunks",
                "chunks_used": result["chunks_used"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        f"OK: {result['path']} · {result['chunks_used']} bloques · "
        f"{result['duration_s']:.1f}s (~{result['duration_s']/60:.1f} min)"
    )
    if result["chunks_missing"]:
        print(f"Aviso: {len(result['chunks_missing'])} bloques sin archivo en disco")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
