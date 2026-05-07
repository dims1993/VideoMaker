#!/usr/bin/env bash
# Crea .venv con Python 3.11 e instala dependencias + torch + Coqui TTS.
#
# En macOS 15/26 a veces el python@3.11 de Homebrew rompe ensurepip/get-pip (error pyexpat /
# libexpat). La opción más fiable es usar "uv", que trae su propio CPython 3.11.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

install_deps() {
  .venv/bin/python -m pip install -U pip
  .venv/bin/python -m pip install -r requirements.txt
  .venv/bin/python -m pip install torch TTS
  # TTS 0.22.x arrastra transformers 5.x, incompatible (BeamSearchScorer en XTTS).
  .venv/bin/python -m pip install "transformers==4.37.2" "tokenizers==0.15.2"
}

if command -v uv >/dev/null 2>&1; then
  echo "==> Usando uv (recomendado si Homebrew python@3.11 falla al instalar pip)"
  uv venv --clear --seed pip -p 3.11 .venv
  install_deps
  echo ""
  echo "Listo. Activa:"
  echo "  source .venv/bin/activate"
  echo "Usa siempre: python -m pip ...  (así no dependes del script 'pip' en PATH)"
  echo ""
  echo "Interfaz (FastAPI + React en dev):  bash scripts/dev.sh"
  exit 0
fi

echo "uv no está en el PATH. Instálalo (una vez):"
echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
echo "y vuelve a ejecutar:  bash scripts/setup_venv.sh"
echo ""
echo "Alternativa manual con Homebrew (cada comando en su propia línea, con Enter):"
echo "  brew install python@3.11"
echo "  brew reinstall expat && brew reinstall python@3.11   # si ves error pyexpat/libexpat"
echo "  rm -rf .venv && /opt/homebrew/bin/python3.11 -m venv .venv --without-pip"
echo "  source .venv/bin/activate"
echo "  curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py && python /tmp/get-pip.py"
echo "  python -m pip install -U pip && python -m pip install -r requirements.txt torch TTS"
echo "  python -m pip install \"transformers==4.37.2\" \"tokenizers==0.15.2\""
exit 1
