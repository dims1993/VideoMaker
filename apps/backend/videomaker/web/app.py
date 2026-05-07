from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from videomaker.core import config
from videomaker.core.db import run_migrations
from videomaker.core.models import ScriptBlueprint
from videomaker.llm.script_gen import compose_messages
from videomaker.tts.voice_reference import REFERENCE_SUFFIXES, normalize_reference_for_xtts

from . import jobs
from .api_router import router as api_router
from .io_util import build_session_state, parse_locale, read_status, safe_work_dir

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

load_dotenv()

app = FastAPI(title="Videomaker")


@app.on_event("startup")
def _startup():
    # DB opcional: solo se activa si hay NEON_DATABASE_URL configurada.
    try:
        run_migrations()
    except Exception:
        # No bloqueamos el arranque del backend legacy.
        pass

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
    try:
        ctx = build_session_state(work)
    except ValueError as e:
        return HTMLResponse(str(e), status_code=400)
    return templates.TemplateResponse(request, "index.html", ctx)


@app.get("/status")
def status(work: str = "output/ui_session"):
    work_dir = safe_work_dir(work)
    return read_status(work_dir)


@app.get("/view-script", response_class=HTMLResponse)
def view_script(request: Request, work: str = "output/ui_session"):
    work_dir = safe_work_dir(work)
    p = work_dir / "guion.txt"
    text = p.read_text(encoding="utf-8") if p.is_file() else ""
    return templates.TemplateResponse(
        request,
        "script.html",
        {"work": work, "text": text},
    )


@app.get("/work-file")
def work_file(work: str, name: str):
    from fastapi.responses import FileResponse

    work_dir = safe_work_dir(work)
    safe = Path(name).name
    p = (work_dir / safe).resolve()
    if not p.is_file():
        return HTMLResponse("Not found", status_code=404)
    return FileResponse(str(p))


@app.post("/voice-preview")
def voice_preview(
    background: BackgroundTasks,
    work: str = Form("output/ui_session"),
    preset: str = Form("xtts_v2_es"),
    text: str = Form("Hola, esta es una prueba de voz antes de narrar el vídeo."),
):
    background.add_task(jobs.run_voice_preview, work, preset, text)
    return RedirectResponse(url=f"/?work={work}", status_code=303)


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
    try:
        raw.write_bytes(data)
        if out.is_file():
            out.unlink()
        normalize_reference_for_xtts(raw, out)
    except Exception as e:
        raw.unlink(missing_ok=True)
        out.unlink(missing_ok=True)
        return HTMLResponse(str(e), status_code=400)
    finally:
        raw.unlink(missing_ok=True)
    return RedirectResponse(url=f"/?work={work}", status_code=303)


@app.post("/clear-voice-clone")
def clear_voice_clone(work: str = Form("output/ui_session")):
    work_dir = safe_work_dir(work)
    (work_dir / "clone_reference.wav").unlink(missing_ok=True)
    return RedirectResponse(url=f"/?work={work}", status_code=303)


@app.post("/upload-script")
async def upload_script(work: str = Form(...), file: UploadFile | None = None):
    work_dir = safe_work_dir(work)
    work_dir.mkdir(parents=True, exist_ok=True)
    if file is None:
        return RedirectResponse(url=f"/?work={work}", status_code=303)
    data = await file.read()
    (work_dir / "guion.txt").write_bytes(data)
    return RedirectResponse(url=f"/?work={work}", status_code=303)


@app.post("/prompt-preview", response_class=HTMLResponse)
def prompt_preview(
    request: Request,
    work: str = Form("output/ui_session"),
    keywords: str = Form("motivación, hábitos, enfoque"),
    context: str = Form(""),
    lang: str = Form("es"),
    minutes: float = Form(8.0),
):
    bp = ScriptBlueprint(
        keywords=[k.strip() for k in keywords.split(",") if k.strip()],
        extra_context=context or "",
        locale=parse_locale(lang),
        target_minutes=float(minutes),
    )
    system, user = compose_messages(bp)
    return templates.TemplateResponse(
        request,
        "prompt.html",
        {"work": work, "system": system, "user": user},
    )


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
    background.add_task(
        jobs.run_generate_script,
        work,
        keywords=keywords,
        context=context,
        lang=lang,
        minutes=float(minutes),
        provider=(provider.strip() or None),
        model=(model or None),
    )
    return RedirectResponse(url=f"/?work={work}", status_code=303)


@app.post("/speak-script")
def speak_script(
    background: BackgroundTasks,
    work: str = Form("output/ui_session"),
    preset: str = Form("xtts_v2_es"),
    max_chars: int = Form(900),
    max_segments: int = Form(0),
):
    work_dir = safe_work_dir(work)
    if not (work_dir / "guion.txt").is_file():
        return RedirectResponse(url=f"/?work={work}", status_code=303)
    background.add_task(
        jobs.run_speak_script,
        work,
        preset=preset,
        max_chars=int(max_chars),
        max_segments=int(max_segments),
    )
    return RedirectResponse(url=f"/?work={work}", status_code=303)


@app.post("/stock-fetch")
def stock_fetch(
    background: BackgroundTasks,
    work: str = Form("output/ui_session"),
    lang: str = Form("es"),
    max_clips: int = Form(25),
):
    work_dir = safe_work_dir(work)
    if not (work_dir / "guion.txt").is_file():
        return RedirectResponse(url=f"/?work={work}", status_code=303)
    background.add_task(
        jobs.run_stock_fetch,
        work,
        lang=lang,
        max_clips=int(max_clips),
    )
    return RedirectResponse(url=f"/?work={work}", status_code=303)


@app.post("/render-draft")
def render_draft(background: BackgroundTasks, work: str = Form("output/ui_session"), no_music: bool = Form(False)):
    work_dir = safe_work_dir(work)
    if not (work_dir / "narracion.wav").is_file() or not (work_dir / "stock").is_dir():
        return RedirectResponse(url=f"/?work={work}", status_code=303)
    background.add_task(jobs.run_render_draft, work, no_music=bool(no_music))
    return RedirectResponse(url=f"/?work={work}", status_code=303)


_UI_DIST = config.PROJECT_ROOT / "frontend" / "dist"
_UI_ASSETS = _UI_DIST / "assets"
_UI_INDEX = _UI_DIST / "index.html"
if _UI_ASSETS.is_dir() and _UI_INDEX.is_file():
    app.mount("/assets", StaticFiles(directory=str(_UI_ASSETS)), name="ui_assets")

    @app.get("/ui")
    def ui_react() -> FileResponse:
        """SPA React (tras `cd frontend && npm run build`). En desarrollo suele usarse Vite en :5173."""
        return FileResponse(_UI_INDEX, media_type="text/html")
