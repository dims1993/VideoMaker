# Videomaker (Analyze + Create)

## Qué es

App local para:

- **Analyze**: analizar un vídeo de YouTube (metadata + transcripción + comentarios) y generar insights con un LLM.
- **Create**: ejecutar una **pipeline** por pasos para crear assets (guion, escenas, prompts, voz).

## Setup rápido

1) Crea/activa el venv e instala deps:

```bash
bash scripts/setup_venv.sh
source .venv/bin/activate
python -m pip install -r apps/backend/requirements.txt
```

2) Crea tu `.env`:

```bash
cp .env.example .env
```

3) Variables necesarias:

- `PEXELS_API_KEY`: para stock (legacy).
- `YOUTUBE_API_KEY`: para **metadata/comentarios** en Analyze (YouTube Data API v3).
  - Si falta, el análisis funciona con transcript si existe, pero con metadata/comentarios limitados.
- `OPENAI_API_KEY` o `VIDEOMAKER_LLM_PROVIDER=ollama`: para el análisis y generación.

## Ejecutar

- Backend FastAPI (puerto 8000)
- Frontend (Vite, puerto 5173)

En este repo se usa `scripts/dev.sh` para levantar ambos.

Opcional (Redis + Celery via Docker):

```bash
docker compose up -d --build
bash scripts/dev.sh
```

O con un solo comando:

```bash
bash scripts/dev_all.sh
```

