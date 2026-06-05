#!/usr/bin/env python3
"""Redirige al script en la raíz del repositorio."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_TARGET = _ROOT / "youtube_oauth_setup.py"

if __name__ == "__main__":
    raise SystemExit(
        subprocess.call([sys.executable, str(_TARGET), *sys.argv[1:]], cwd=str(_ROOT))
    )
