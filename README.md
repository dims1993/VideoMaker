# Videomaker (Analyze + Create)

Plataforma local (desktop-first) para **analizar canales/vídeos de YouTube** y ejecutar una **pipeline de creación** para producir vídeos (guion, assets, voz, render draft).

## Qué hace

- **Analyse** (YouTube):
  - Buscar canales por nombre y filtrar por métricas (subs/views).
  - Guardar canales en un **directorio interno** (Postgres).
  - Sincronizar un canal (sync) para traer vídeos + métricas y generar insights.
  - **Transcripts → sesión**: normalizar subtítulos a `transcripts_session.json` (por vídeo: título, duración, texto) y, con ≥3 transcripts, **analizar con IA** para rellenar la plantilla Prompt del canal (sin reenviar todo el corpus en cada paso Create).
  - Descargar ZIPs:
    - `thumbnails.zip` (thumbnails de vídeos)
    - `scripts.zip` (transcripciones, si existen)
- **Create** (pipeline):
  - Pipeline por pasos con estado y reintentos. Diagrama y clasificación imprescindible/opcional: [`docs/PIPELINE.md`](docs/PIPELINE.md).

## Funcionamiento (pipeline Create)

### Sesiones y UI

- Cada vídeo vive en una carpeta **`output/<sesión>/`** (por defecto `output/ui_session`; la URL lleva `?work=…`).
- La **barra lateral** y **Start pipeline** siguen el mismo orden de producción (`PIPELINE_STEPS` / `PIPELINE_RUN_ORDER` en `pipeline/models.py`): guion pulido → routers → prompts de imagen → **voiceovers (TTS real)** → **images** → publicación/render.
- El botón **Start step** de cada panel ejecuta **solo ese paso** (recomendado para control y depuración).
- Paneles con tema **claro** (blanco): Topic, Narrative Angle, Packaging, Prompt, Script Writer, Hook Scene Router, Body Scene Router, Metadata, etc. Image Prompt Writer y otros pasos pueden seguir en tema oscuro.

### Entradas de sesión

| Origen | Qué aporta |
|--------|------------|
| Formulario Create | `keywords` (tema), `context` (ángulo), `lang`, `minutes`, `provider`/`model` (Claude en guion), restricciones de vídeo, IDs de plantillas Prompt / Script Writer |
| Analyse | `pipeline/transcripts_session.json` + `prompt_analysis` slim en la misma sesión o copiados al spawn |
| Topic Generator | `pipeline/topic_generator.json` — título, ángulo, `output_language`, tema seleccionado |

### Leyenda de las tablas

Columna **«Poco útil / sin efecto hoy»**: artefactos o UI que **no cambian** `draft.mp4` ni el flujo crítico si los omites (diagnóstico, SEO manual, planes JSON no consumidos).

**Globales que confunden**

- `provider` / `model` del formulario Create **no** gobiernan Metadata (OpenAI por defecto ahí).
- **Start pipeline** completa: Images Generation suele crear manifest vacío sin PNG; mejor generar imágenes desde su panel.
- Carpeta **`stock/`**: solo si no hay `pipeline/images/` (legacy).

---

### 1. Topic Generator

| | |
|---|---|
| **Recibe** | Texto de transcripciones (sesión Analyse o pegado manual), `niche_trends`, número de temas, idioma de canal/sesión, keywords/context de Create. |
| **Genera** | `pipeline/topic_generator.json` — lista de ideas (`topics[]`), `selected_index`, `output_language`, duración sugerida. |
| **Envía a** | **Narrative Angle** (tema seleccionado), **Prompt** (título/ángulo vía sesión), **Metadata** (título canónico y SEO). |
| **Poco útil / sin efecto hoy** | Ideas generadas sin pulsar «Usar este tema» (el resto del pipeline puede seguir con keywords sueltas). `niche_trends` vacío. Duración sugerida si luego fijas minutos a mano en Create y no re-sincronizas. |

**Banco de temas → varios vídeos (sin re-LLM):** en la carpeta de investigación (p. ej. `output/research`) genera la lista una vez. En cada idea, **Producir vídeo →** crea `output/v01_<slug>/` con el mismo `topic_generator.json` + `transcripts_session.json`; la pipeline completa en la hija **no** vuelve a llamar al Topic Generator (`topic_bank` en el JSON). Sigue con **Narrative Angle** en la sesión nueva.

### 2. Narrative Angle

| | |
|---|---|
| **Recibe** | Tema elegido en Topic Generator, audiencia/estilo de canal (transcripts session), duración e idioma de sesión. |
| **Genera** | `pipeline/narrative_angle.json` — ángulo narrativo (tensión, promesa, tono, etc.). |
| **Envía a** | **Packaging**, **Prompt** (como `narrative_angle`), **Editorial Analyzer** (contexto opcional). |
| **Poco útil / sin efecto hoy** | Todo el paso si **no** vuelves a ejecutar **Prompt** después (el ángulo solo se copia a `prompt.json` en ese «Start step»). No llega a Script Writer por sí solo sin Packaging. |

### 3. Packaging (Título + Miniatura) — hook-first

| | |
|---|---|
| **Recibe** | Tema + **Narrative Angle** (sin guion). Keywords/contexto de sesión, plataforma en metadata-settings. |
| **Genera** | `pipeline/packaging.json` — título, variantes, `thumbnail_ideas`, `hook_summary`, `thumbnail_hook_text`, `thumbnail_narrative` (imagen mental del clic). |
| **Envía a** | **Prompt** (`packaging` + `context`), **Script Writer** (promesa de miniatura en instrucciones), **Hook Scene Router**, **Metadata** (se fusiona al generar descripción/tags), miniaturas PNG (vía Metadata). |
| **Poco útil / sin efecto hoy** | Omitir el paso: Metadata legacy sigue pudiendo generar título+miniaturas desde el guion (paradigma antiguo). Sin Narrative Angle previo falla la generación. |

### 4. Prompt

| | |
|---|---|
| **Recibe** | Tema/ángulo de sesión, restricciones de vídeo (solo sesión), plantilla del catálogo (opcional), `narrative_angle.json`, `packaging.json` (contexto). Desde Analyse: análisis de transcripts que rellena **system instructions** + narrativa. |
| **Genera** | `pipeline/prompt.json` — brief creativo: tema, spines (`energy_curve`, `visual_density`, `scroll_stop_factors`, etc.). En catálogo: `system_instructions` + `user_instructions` (narrativa) + `params_json.output_structure` (modelo base OUTLINE/GUIÓN/B-ROLL con placeholders `{{TEMA}}`, `{{LANGUAGE_CODE}}`, `{{DURACION_MINUTOS}}`, …). |
| **Envía a** | **Script Writer** (fusiona modelo base + narrativa + placeholders + capa Guionista), engines de plan (Subtitle/Music/Voiceover), Image Prompt Writer, routers. |
| **Poco útil / sin efecto hoy** | **Start step** del paso **no llama al LLM**: persiste catálogo + defaults legacy. Preview JSON ≠ guion generado (muestra instrucciones, no salida de Script Writer). Sin re-ejecutar Prompt tras cambiar tema, `prompt.json` puede quedar desfasado. `provider`/`model` aquí no controlan Metadata. |

### 5. Script Writer

| | |
|---|---|
| **Recibe** | `prompt.json`, plantilla Script Writer (catálogo), minutos, idioma, extras de plantillas Prompt + Script; contexto de **Packaging** si existe. |
| **Genera** | `guion.txt`, `pipeline/script.txt`, `pipeline/script.json` (TTS/outline/sections). Con **fragmentación secuencial**: chunks en `pipeline/script_chunks/` + `script_fragmentation.json` → ensamblado en `guion.txt`. |
| **Envía a** | Editorial, Pacing, Hook/Body routers, Image Prompt Writer, Metadata, Scene Editor, Voiceover Engine. |
| **UI** | **Salida · Guion** = lectura de `guion.txt`. **Guardar en sesión** sincroniza pipeline. **Guardar en…** exporta copia donde elijas (diálogo del sistema). **Abrir carpeta** revela la sesión en Finder. |
| **Poco útil / sin efecto hoy** | `script_writer_debug.json`. Tags `[B-ROLL]` en salida (`include_broll=False`). Modo «solo OUTLINE + acto 1» si luego quieres guion completo en un pase. |

### 6. Editorial Analyzer

| | |
|---|---|
| **Recibe** | Guion (`guion.txt` / `script.txt`), tema desde `prompt.json`, contexto de `narrative_angle` (si existe). |
| **Genera** | `pipeline/editorial_analysis.json` — diagnóstico editorial (ritmo, claridad, riesgos, sugerencias). |
| **Envía a** | **Narrative Pacing Pass** (entrada principal para reescritura). |
| **Poco útil / sin efecto hoy** | **Casi todo el artefacto** si no ejecutas **Narrative Pacing Pass** después. Lint / `ScriptQualityBanner` son avisos, no bloquean el pipeline. |

### 7. Narrative Pacing Pass

| | |
|---|---|
| **Recibe** | Guion actual + `editorial_analysis.json` (recomendado), idioma y tema de sesión. |
| **Genera** | Guion revisado (sobrescribe `guion.txt` / `script.txt` y bundle). |
| **Envía a** | Hook/Body routers, Image Prompt Writer, Voiceovers, Metadata, etc. |
| **Poco útil / sin efecto hoy** | Omisible si el primer guion ya vale. Si reescribes después de TTS/imágenes, vuelve a ejecutar routers y reconciliación. |

### 8. Hook Scene Router

| | |
|---|---|
| **Recibe** | Guion (Acto 1 / gancho), `prompt.json`, settings (plataforma, energía visual, talking-head delay), opcional `metadata.json`. |
| **Genera** | `pipeline/hook_scene_router.json` — `micro_beats[]` (retención, `narrator_visible`, tiempos **estimados** por texto). |
| **Envía a** | **Image Prompt Writer** (avatar híbrido o merge solo inserts). |
| **Poco útil / sin efecto hoy** | Gran parte del JSON es diagnóstico; el merge usa beats + `narrator_visible`. Ejecutar **después** de Pacing para que el gancho coincida con el guion final. |

### 9. Body Scene Router

| | |
|---|---|
| **Recibe** | Guion (actos 2–4 / cuerpo), estilo heredado del Hook Router, settings de router. |
| **Genera** | `pipeline/body_scene_router.json` — **`macro_beats[]`** (`track`: avatar \| insert, `text_anchor`, `ai_prompt` en inserts). Aplica **max_hold** en bloques largos. |
| **Envía a** | **Image Prompt Writer** (con Hook Router, `VIDEOMAKER_IPW_ROUTER_DRIVEN=1` por defecto). Scene Editor ya no parte chunks si hay macro_beats. |
| **Poco útil / sin efecto hoy** | `scene_prompts` legacy en `llm_enrichment` (sustituido por macro_beats). Desactiva router-driven con `VIDEOMAKER_IPW_ROUTER_DRIVEN=0` para volver a `secs_per_image`. |

### 10. Image Prompt Writer

| | |
|---|---|
| **Recibe** | `hook_scene_router.json` + `body_scene_router.json` (`macro_beats`). **Modo avatar:** preset / `scene_visual_settings` solo en filas `track: avatar`. |
| **Genera** | `pipeline/image_prompts.json` — `source: router_driven`; timing relativo hasta reconciliar con TTS. |
| **Envía a** | **Voiceovers** (reconciliación tras audio) → **Images Generation**. |
| **Poco útil / sin efecto hoy** | `avatar_secs_per_image` ignorado con router-driven (default). `VIDEOMAKER_IPW_ROUTER_DRIVEN=0` → flujo legacy por segundos. |

**Flujo unificado:** Hook Router + Body Router → **Start step** en IPW (modo avatar ON si hay presentador). Volcar hook manual sigue disponible si regeneras solo el gancho.

**Sincronía:** tras **unificar narracion.wav** (paso 11), reconciliación automática con audio real; mínimo **0,8 s** por plano (inserts cortos roban tiempo al avatar vecino). API: `POST /api/pipeline/image-prompts/reconcile-timing`.

### 11. Voiceovers Generation (+ Scene Editor)

| | |
|---|---|
| **Recibe** | Guion; opcionalmente `pipeline/voiceover_plan.json`. TTS: ElevenLabs (`.env`) por bloque en Scene Editor. |
| **Genera** | `scene_editor.json`, audio en `scene_audio/`, `narracion.wav` al unificar; dispara **reconciliación** de `image_prompts.json` si ya existe. |
| **Envía a** | **Images Generation** (manifest con `duration_ms` real), **Render draft**, Music/Subtitle engines. |
| **Poco útil / sin efecto hoy** | «Start step» legacy XTTS monolítico vs. ElevenLabs por bloque en la UI. Sin **Unificar → narracion.wav**, el render falla. |

> **Scene Editor** vive dentro de este paso (`ELEVENLABS_VOICE_ID`, `eleven_turbo_v2_5` por defecto).

### 12. Images Generation

| | |
|---|---|
| **Recibe** | `image_prompts.json` → manifest `pipeline/images_generation.json`; imágenes existentes en `pipeline/images/`. Motores: Gemini Web (escenas), Google Imagen o OpenAI (miniaturas desde Metadata). |
| **Genera** | PNG numerados (`001.png`…), miniaturas `thumb_01.png`…, manifest actualizado (`status`, `filename`, `selected`). |
| **Envía a** | **Render draft** (imágenes seleccionadas + duraciones), **Metadata** (previews de miniaturas ya generadas). |
| **Poco útil / sin efecto hoy** | **Start step** del paso en pipeline completa: escribe manifest **placeholder** sin generar PNG (`_run_step_images_generation`). Miniaturas con `role=thumbnail` **no** entran en el render (excluidas). Estado `selected` sin PNG. Barra de audio bajo tarjeta si no hay chunk en Scene Editor. Quitar marca de agua Gemini no afecta si no usaste Gemini. |

### 13. Music Engine (después de Voiceovers)

| | |
|---|---|
| **Recibe** | `pipeline/audio_timeline.json` (huecos entre bloques TTS + duraciones medidas); `prompt.json` (`energy_curve`). |
| **Genera** | `pipeline/music_plan.json` — beats con `start_s`/`end_s` anclados a pausas y bloques reales. |
| **Envía a** | **Render draft** (cortes sugeridos cuando no hay sync por chunk de imágenes). |
| **Poco útil / sin efecto hoy** | Con **`render_no_music`** o sin librería en proyecto, el plan no se oye. No genera archivo de música; solo sugiere. Si las imágenes ya traen duración por chunk, el montaje prioriza ese timing sobre los beats. |

### 14. Metadata (publicación)

| | |
|---|---|
| **Recibe** | Guion; `packaging.json` si existe (hook-first); Topic Generator; keywords SEO; `metadata_settings`. |
| **Genera** | `pipeline/metadata.json` — con Packaging: solo **descripción, tags, capítulos** + merge del empaquetado; sin Packaging: metadata completa (legacy). |
| **Envía a** | Copiar descripción YouTube; **miniaturas PNG** (ideas desde `packaging.json`); Hook Router lee pistas si `metadata.json` existe. |
| **Poco útil / sin efecto hoy** | Regenerar **título/miniaturas** aquí si ya tienes Packaging (se conservan del merge). **`description_short`**, **`title_variants`** en copiar YouTube. **`production`** no automatiza render. Subida a YouTube no automatizada. |

### 15. Subtitle Engine (después de Voiceovers)

| | |
|---|---|
| **Recibe** | Audio real: `scene_editor.json` + `scene_audio/` → `narracion.wav`; estilo desde `prompt.json` + guion. |
| **Genera** | `pipeline/audio_timeline.json`, `pipeline/subtitles.srt`, `pipeline/subtitles_plan.json` (Whisper: segmentos y palabras con `start`/`end` en segundos). |
| **Envía a** | Montaje/post (referencia editorial; integración automática en render limitada hoy). |
| **Poco útil / sin efecto hoy** | **No quema subtítulos en `draft.mp4`**. Omisible si subtitulas en CapCut/Premiere. Whisper puede tardar en la primera ejecución (descarga del modelo). |

### 16. Render draft

| | |
|---|---|
| **Recibe** | `narracion.wav`, imágenes seleccionadas de `images_generation.json`, duraciones desde Scene Editor/manifest, opcional música (`stock/`, plan). |
| **Genera** | `draft.mp4`, progreso en `pipeline/render_draft.json` / checkpoints `pipeline/render/`. |
| **Envía a** | Revisión humana / export final (fuera de la pipeline). |
| **Poco útil / sin efecto hoy** | Contenido de `subtitles_plan` en el artefacto JSON (no en el vídeo). Modo **`stock/`** si ya tienes imágenes en pipeline. `render_draft.json` es resumen; no es entrada obligatoria para otro paso. Preview corto / `fast_preview` no sustituye el draft final. |

---

### Paso auxiliar (final del sidebar): Voiceover Engine

| | |
|---|---|
| **Recibe** | `prompt.json` (tono, credibilidad, curva de energía), guion. |
| **Genera** | `pipeline/voiceover_plan.json`, opcional `pipeline/script_for_tts.txt` (guion adaptado a TTS). |
| **Envía a** | Voiceovers / Scene Editor (pausas y texto TTS) si usas esos campos. |
| **Poco útil / sin efecto hoy** | Opcional si ElevenLabs lee el guion directo por chunk. No configura la voz ElevenLabs automáticamente. |

---

### Flujo de producción (referencia)

La barra lateral y **Start pipeline** siguen este orden (pasos 1–16; **Voiceover Engine** al final, auxiliar).

```text
 1. Topic Generator
 2. Narrative Angle
 3. Packaging (Título + Miniatura)
 4. Prompt
 5. Script Writer
 6. Editorial Analyzer
 7. Narrative Pacing Pass
 8. Hook Scene Router          ← micro_beats, narrator_visible
 9. Body Scene Router          ← opcional; sub-planos en Scene Editor
10. Image Prompt Writer        ← modo avatar ON → avatar híbrido
11. Voiceovers Generation      ← TTS + Unificar narracion.wav (reconcilia tiempos)
12. Images Generation          ← Enviar a Images + generar PNG + seleccionar
13. Music Engine               ← opcional
14. Metadata
15. Subtitle Engine            ← opcional
16. Render draft
```

#### Reglas (no desincronizar)

| Regla | Motivo |
|--------|--------|
| **Pacing (7) antes de Hook (8)** | El router debe leer el guion del gancho definitivo. |
| **Hook (8) antes de Image Prompt Writer (10)** | Sin beats no hay pista `insert` ni pesos relativos. |
| **Image Prompt Writer (10) antes de Voiceovers (11)** | Primero prompts; luego audio real y reconciliación. |
| **Voiceovers (11) antes de Images Generation (12)** | El manifest necesita `duration_ms` medido, no WPM estimado. |
| **Unificar `narracion.wav`** | Dispara reconciliación (mín. 0,8 s/plano; inserts roban tiempo al avatar vecino). |
| **No usar `start_sec` del Hook en montaje** | Son estimaciones; manda `audio_timeline` + reconciliación. |
| Si regeneras Hook tras avatar | «Fusionar inserts del Hook (híbrido)» → voiceovers/reconciliar de nuevo. |

#### Checklist antes del render

- [ ] `hook_scene_router.json` coherente  
- [ ] `image_prompts.json` con `timing_reconciled: true` (tras unificar narración)  
- [ ] `narracion.wav` unificado  
- [ ] PNG generados y **seleccionados** en Images Generation  

#### Atajos según objetivo

**Producción completa (Alex + gancho + sync audio)** — usa los 16 pasos de la tabla anterior.

**Mínimo publicable** (sin Alex ni hook fino):

```text
Topic Generator → Prompt → Script Writer
  → Image Prompt Writer (sin avatar)
  → Voiceovers → Images Generation
  → Metadata → Render draft
```

**Guion ya importado** — salta Topic/Packaging si no aplica; conserva **Pacing → Hook → IPW → Voiceovers → Images → Render**.

**Varios vídeos desde banco de temas** (`output/research`):

1. Topic Generator una vez en la carpeta padre.  
2. Por idea: **Producir vídeo →** (`POST /api/pipeline/sessions/spawn`) → sesión hija con `topic_generator.json` + transcripts (sin re-LLM de temas).  
3. En la hija: **Prompt** (Start step) y el flujo de producción de arriba.

Diagrama y artefactos: [`docs/PIPELINE.md`](docs/PIPELINE.md).

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
  - `YOUTUBE_API_KEY` (YouTube Data API v3) — metadatos de canales/vídeos.
  - `YOUTUBE_OAUTH_*` — transcripciones propias vía `captions.list` / `captions.download` (`youtube_oauth_setup.py` en la raíz).
  - `VIDEOMAKER_TRANSCRIPT_PROVIDER=auto` (recomendado) — Data API → **Cloudflare Worker** → scrape.
  - `YOUTUBE_TRANSCRIPT_WORKER_URL` — Worker en `workers/youtube-transcript-proxy` (subtítulos públicos sin usar tu IP; ver su README).
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

