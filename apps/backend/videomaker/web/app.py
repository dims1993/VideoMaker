from __future__ import annotations

from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from videomaker.core import config  # noqa: F401 — carga PROJECT_ROOT/.env al importar
from videomaker.core.db import run_migrations
from videomaker.core.models import ScriptBlueprint
from videomaker.llm.script_gen import compose_messages
from videomaker.tts.voice_reference import REFERENCE_SUFFIXES, normalize_reference_for_xtts

from . import jobs
from .api_router import router as api_router
from .io_util import build_session_state, parse_locale, read_status, safe_work_dir

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="Videomaker")


@app.on_event("startup")
def _startup():
    import logging
    import os

    from videomaker.web.server_boot import SERVER_BOOT_AT, SERVER_BOOT_ID

    logging.getLogger("videomaker").info(
        "Server boot id=%s at=%s", SERVER_BOOT_ID, SERVER_BOOT_AT
    )
    # DB opcional: solo se activa si hay NEON_DATABASE_URL configurada.
    # Si hay URL pero falla la migración, preferimos fallar rápido para no dar 500s raros más tarde.
    has_db = bool(os.environ.get("NEON_DATABASE_URL", "").strip() or os.environ.get("DATABASE_URL", "").strip() or os.environ.get("NEON_DATABASE_PATH", "").strip())
    if not has_db:
        return
    try:
        run_migrations()
    except Exception as e:
        logging.getLogger("videomaker").exception("DB migrations failed: %s", e)
        raise

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

static_dir = BASE_DIR / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

_CLONE_UPLOAD_MAX_BYTES = 25 * 1024 * 1024


@app.get("/", response_class=HTMLResponse)
def index(request: Request, work: str = "output/ui_session"):
    # Legacy HTML UI removed in favor of the SPA frontend.
    # Redirect to the SPA entry point; the SPA uses the JSON API under /api.
    return RedirectResponse(url="/ui", status_code=303)


@app.get("/status")
def status(work: str = "output/ui_session"):
    work_dir = safe_work_dir(work)
    return read_status(work_dir)


@app.get("/view-script", response_class=HTMLResponse)
def view_script(request: Request, work: str = "output/ui_session"):
    # Legacy endpoint disabled. Use the SPA or /api/script to fetch the script.
    return HTMLResponse("Legacy view-script disabled. Use the SPA at /ui.", status_code=410)


@app.api_route("/work-file", methods=["GET", "HEAD"])
def work_file(request: Request, work: str, name: str):
    work_dir = safe_work_dir(work)
    safe = Path(name).name
    p = (work_dir / safe).resolve()
    try:
        p.relative_to(work_dir.resolve())
    except ValueError:
        return Response(status_code=404)
    if not p.is_file():
        return Response(status_code=404)
    if request.method == "HEAD":
        media = "video/mp4" if p.suffix.lower() == ".mp4" else "application/octet-stream"
        return Response(
            status_code=200,
            headers={
                "Content-Length": str(p.stat().st_size),
                "Content-Type": media,
            },
        )
    return FileResponse(str(p))


@app.post("/voice-preview")
def voice_preview(
    background: BackgroundTasks,
    work: str = Form("output/ui_session"),
    preset: str = Form("xtts_v2_es"),
    text: str = Form("Hola, esta es una prueba de voz antes de narrar el vídeo."),
):
    # Legacy HTML form handler disabled. Use the SPA and the JSON API `/api/voice-preview` instead.
    return HTMLResponse("Legacy voice-preview disabled. Use the SPA at /ui.", status_code=410)


@app.post("/upload-voice-clone")
async def upload_voice_clone(
    work: str = Form("output/ui_session"),
    file: UploadFile | None = None,
):
    from fastapi.responses import HTMLResponse

    if file is None or not (file.filename or "").strip():
        return RedirectResponse(url=f"/?work={work}", status_code=303)
    work_dir = safe_work_dir(work)
    work_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename).suffix.lower()
    if suffix not in REFERENCE_SUFFIXES:
        return HTMLResponse(
            f"Formato no soportado: {suffix or '(sin extensión)'}. "
            f"Usa: {', '.join(sorted(REFERENCE_SUFFIXES))}",
            status_code=400,
        )
    data = await file.read()
    if len(data) > _CLONE_UPLOAD_MAX_BYTES:
        return HTMLResponse("Archivo demasiado grande (máx. 25 MB).", status_code=400)
    raw = work_dir / f"_clone_upload{suffix}"
    out = work_dir / "clone_reference.wav"
    # Legacy HTML upload disabled. Use the SPA and the JSON API `/api/voice-preview` or `/api` endpoints.
    return HTMLResponse("Legacy upload-voice-clone disabled. Use the SPA at /ui.", status_code=410)


@app.post("/clear-voice-clone")
def clear_voice_clone(work: str = Form("output/ui_session")):
    return HTMLResponse("Legacy clear-voice-clone disabled. Use the SPA at /ui.", status_code=410)


@app.post("/upload-script")
async def upload_script(work: str = Form(...), file: UploadFile | None = None):
    return HTMLResponse("Legacy upload-script disabled. Use the SPA at /ui.", status_code=410)


@app.post("/prompt-preview", response_class=HTMLResponse)
def prompt_preview(
    request: Request,
    work: str = Form("output/ui_session"),
    keywords: str = Form("motivación, hábitos, enfoque"),
    context: str = Form(""),
    lang: str = Form("es"),
    minutes: float = Form(8.0),
):
    return HTMLResponse("Legacy prompt-preview disabled. Use the SPA or /api/prompt-preview.", status_code=410)


@app.post("/generate-script")
def do_generate_script(
    background: BackgroundTasks,
    work: str = Form("output/ui_session"),
    keywords: str = Form("motivación, hábitos, enfoque"),
    context: str = Form(""),
    lang: str = Form("es"),
    minutes: float = Form(8.0),
    provider: str = Form(""),
    model: str = Form(""),
):
    return HTMLResponse("Legacy generate-script disabled. Use the SPA or /api/generate-script.", status_code=410)


@app.post("/speak-script")
def speak_script(
    background: BackgroundTasks,
    work: str = Form("output/ui_session"),
    preset: str = Form("xtts_v2_es"),
    max_chars: int = Form(900),
    max_segments: int = Form(0),
):
    return HTMLResponse("Legacy speak-script disabled. Use the SPA or /api/speak-script.", status_code=410)


@app.post("/render-draft")
def render_draft(background: BackgroundTasks, work: str = Form("output/ui_session"), no_music: bool = Form(False)):
    return HTMLResponse("Legacy render-draft disabled. Use the SPA or /api/render-draft.", status_code=410)


_UI_DIST = config.PROJECT_ROOT / "frontend" / "dist"
_UI_ASSETS = _UI_DIST / "assets"
_UI_INDEX = _UI_DIST / "index.html"
if _UI_ASSETS.is_dir() and _UI_INDEX.is_file():
    app.mount("/assets", StaticFiles(directory=str(_UI_ASSETS)), name="ui_assets")

    @app.get("/ui")
    def ui_react() -> FileResponse:
        """SPA React (tras `cd frontend && npm run build`). En desarrollo suele usarse Vite en :5173."""
        return FileResponse(_UI_INDEX, media_type="text/html")
