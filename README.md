# Videomaker (Analyze + Create)

Plataforma local (desktop-first) para **analizar canales/vídeos de YouTube** y ejecutar una **pipeline de creación** para producir vídeos (guion, assets, voz, render draft).

## Qué hace

- **Analyse** (YouTube):
  - Buscar canales por nombre y filtrar por métricas (subs/views).
  - Guardar canales en un **directorio interno** (Postgres).
  - Sincronizar un canal (sync) para traer vídeos + métricas y generar insights.
  - Descargar ZIPs:
    - `thumbnails.zip` (thumbnails de vídeos)
    - `scripts.zip` (transcripciones, si existen)
- **Create** (pipeline):
  - Pipeline por pasos (Prompt → ScriptWriter → … → Voiceovers) con estado y reintentos.

## Estructura del repo

Monorepo organizado:

```
apps/
  backend/
    videomaker/            # paquete python (FastAPI, Celery, lógica)
    migrations/            # SQL migrations para Postgres
    requirements.txt       # deps Python
    Dockerfile             # imagen para celery-worker
  frontend/
    src/                   # React (Vite)
    package.json
scripts/
  dev.sh                   # arranca FastAPI + Vite
  dev_all.sh               # docker compose up -d + dev.sh
docker-compose.yml         # redis + celery-worker
output/                    # artefactos (ignorados por git)
```

## Componentes (cómo se conectan)

- **Backend**: FastAPI (`apps/backend/videomaker/web/…`) expone `/api/*`.
- **Frontend**: Vite/React (`apps/frontend`) consume `/api/*` (proxy en dev).
- **Postgres (Neon)**: guarda directorio de canales, vídeos y snapshots (migraciones en `apps/backend/migrations`).
- **Redis**:
  - caché 24h de llamadas a YouTube Data API v3 (reduce cuota).
  - broker/backend para Celery.
- **Celery worker**: ejecuta tareas largas (por ejemplo `Sync now`) sin bloquear la UI.
- **Almacenamiento de ficheros (local dev)**: `output/` (ZIPs, media, logs). En producción se puede mover a S3/GCS.

## Requisitos

- Python 3.11 (recomendado)
- Node 18+ (para frontend)
- Docker Desktop (para Redis + Celery)

## Configuración (.env)

```bash
cp .env.example .env
```

Variables importantes:

- **YouTube**:
  - `YOUTUBE_API_KEY` (YouTube Data API v3) — necesario para búsqueda/enriquecimiento de canales.
- **DB**:
  - `NEON_DATABASE_URL` — Postgres en Neon (se aplican migrations al arrancar backend).
- **Redis/Celery**:
  - `REDIS_URL=redis://localhost:6379/0` (cuando usas docker compose)
- **LLM**:
  - `OPENAI_API_KEY` (OpenAI-compatible) o `VIDEOMAKER_LLM_PROVIDER=ollama`.

## Instalación (Python + Frontend)

```bash
bash scripts/setup_venv.sh
source .venv/bin/activate
python -m pip install -r apps/backend/requirements.txt
```

El frontend se instala automáticamente la primera vez que ejecutas `scripts/dev.sh`.

## Ejecutar (modo desarrollo)

### Opción A (recomendada): todo con un comando

```bash
bash scripts/dev_all.sh
```

Esto levanta:
- `docker compose up -d` (Redis + celery-worker)
- `scripts/dev.sh` (FastAPI + Vite)

### Opción B: paso a paso

Primera vez (o si cambias deps/backend Dockerfile):

```bash
docker compose up -d --build
```

Luego día a día:

```bash
docker compose up -d
bash scripts/dev.sh
```

## Notas de diseño

- **Migrations**: `apps/backend/migrations/*.sql` definen el esquema de Postgres y se aplican automáticamente al arrancar el backend (tabla `schema_migrations`).  
- **Binarios en DB**: no se guardan. ZIPs y media van a `output/` (en DB solo rutas/URLs).  
- **Sync**: si `REDIS_URL` está configurado y el worker está levantado, `Sync now` usa Celery; si no, cae a fallback (background task).  

