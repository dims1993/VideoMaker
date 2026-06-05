"""Cola de imágenes vía Gemini web (Google AI Pro) — misma conversación, Playwright + CDP."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

GEMINI_APP_URL = "https://gemini.google.com/app"
_JOB_LOCK = threading.Lock()
_ACTIVE_WORK: str | None = None
_CANCEL_EVENTS: dict[str, threading.Event] = {}

LogFn = Callable[[str], None]


class GeminiBatchCancelled(Exception):
    """Cola interrumpida por el usuario."""


def _work_slug(work_dir: Path, job: dict[str, Any] | None = None) -> str:
    j = job if job is not None else (read_job(work_dir) or {})
    w = str(j.get("work") or "").strip()
    return w or work_dir.name


def is_cancel_requested(work_dir: Path) -> bool:
    slug = _work_slug(work_dir)
    ev = _CANCEL_EVENTS.get(slug)
    if ev and ev.is_set():
        return True
    job = read_job(work_dir)
    return bool(isinstance(job, dict) and job.get("cancel_requested"))


def _try_stop_gemini_generation(page: Any) -> None:
    """Intenta pulsar Stop en Gemini para cortar la generación en curso."""
    selectors = (
        'button[aria-label*="Stop"]',
        'button[aria-label*="Detener"]',
        'button[aria-label*="Cancel"]',
        'button[aria-label*="Cancelar"]',
        'button[data-tooltip*="Stop"]',
        'button[mattooltip*="Stop"]',
        'button[mattooltip*="Detener"]',
    )
    for sel in selectors:
        try:
            btn = page.locator(sel).last
            if btn.count() > 0 and btn.is_visible(timeout=400):
                btn.click(timeout=2000, force=True)
                page.wait_for_timeout(250)
                return
        except Exception:
            continue


def _abort_if_cancelled(work_dir: Path, page: Any | None = None, *, log: LogFn | None = None) -> None:
    if not is_cancel_requested(work_dir):
        return
    if page is not None:
        _try_stop_gemini_generation(page)
    if log:
        log("Cola cancelada por el usuario.")
    raise GeminiBatchCancelled()


def _wait_ms(page: Any, work_dir: Path, ms: int, *, chunk_ms: int = 400) -> None:
    remaining = max(0, int(ms))
    while remaining > 0:
        _abort_if_cancelled(work_dir, page)
        step = min(chunk_ms, remaining)
        page.wait_for_timeout(step)
        remaining -= step


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def cdp_url() -> str:
    return (os.getenv("GEMINI_WEB_CDP_URL") or "http://127.0.0.1:9222").strip()


def delay_between_sec() -> float:
    try:
        return max(5.0, float(os.getenv("GEMINI_WEB_DELAY_SEC", "28")))
    except ValueError:
        return 28.0


def response_timeout_sec() -> float:
    try:
        return max(30.0, float(os.getenv("GEMINI_WEB_RESPONSE_TIMEOUT_SEC", "120")))
    except ValueError:
        return 120.0


def post_ready_settle_ms() -> int:
    """Pausa tras detectar imagen lista, antes de Descargar (archivo full-res)."""
    try:
        return max(0, int(os.getenv("GEMINI_WEB_POST_READY_MS", "2500")))
    except ValueError:
        return 2500


def min_saved_file_bytes() -> int:
    """Rechaza previews del chat (~1 MB); descarga manual suele ser varios MB."""
    try:
        return max(50_000, int(os.getenv("GEMINI_WEB_MIN_FILE_BYTES", "1500000")))
    except ValueError:
        return 1_500_000


def min_saved_side_px() -> int:
    try:
        return max(256, int(os.getenv("GEMINI_WEB_MIN_SAVED_PX", "1200")))
    except ValueError:
        return 1200


def allow_preview_fallback() -> bool:
    return os.getenv("GEMINI_WEB_ALLOW_PREVIEW_FALLBACK", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def job_path(work_dir: Path) -> Path:
    return work_dir / "pipeline" / "gemini_web_job.json"


def read_job(work_dir: Path) -> dict[str, Any] | None:
    p = job_path(work_dir)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def write_job(work_dir: Path, data: dict[str, Any]) -> None:
    p = job_path(work_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = _utc_now()
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _cdp_port_reachable(url: str, timeout_s: float = 2.0) -> bool:
    """True si el puerto CDP responde (sin Playwright)."""
    import urllib.error
    import urllib.request

    version_url = url.rstrip("/") + "/json/version"
    try:
        with urllib.request.urlopen(version_url, timeout=timeout_s) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def check_cdp_available() -> dict[str, Any]:
    """Comprueba si Chrome con depuración remota está accesible."""
    url = cdp_url()
    port_open = _cdp_port_reachable(url)
    base: dict[str, Any] = {
        "cdp_url": url,
        "port_open": port_open,
    }

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        if port_open:
            detail = (
                "El puerto 9222 responde, pero Playwright no está en el venv del proyecto. "
                "Ejecuta: .venv/bin/python -m pip install playwright && .venv/bin/playwright install chromium "
                "y reinicia dev.sh"
            )
        else:
            detail = (
                "Chrome no escucha en 9222. Ábrelo con el comando de abajo. "
                "Playwright: .venv/bin/python -m pip install playwright"
            )
        return {
            **base,
            "playwright_installed": False,
            "cdp_connected": False,
            "detail": detail,
        }

    if not port_open:
        return {
            **base,
            "playwright_installed": True,
            "cdp_connected": False,
            "detail": "El puerto 9222 no responde. Cierra Chrome y ábrelo con --remote-debugging-port=9222.",
        }

    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(url, timeout=8000)
            contexts = browser.contexts
            return {
                **base,
                "playwright_installed": True,
                "cdp_connected": True,
                "contexts": len(contexts),
                "detail": "Chrome conectado. Abre gemini.google.com en ese Chrome antes de iniciar la cola.",
            }
    except Exception as e:
        return {
            **base,
            "playwright_installed": True,
            "cdp_connected": False,
            "detail": str(e)[:300],
        }


def _find_input(page: Any) -> Any | None:
    selectors = [
        "div.ql-editor[contenteditable='true']",
        "rich-textarea div[contenteditable='true']",
        "[contenteditable='true'][aria-label]",
        "textarea",
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).last
            if loc.count() > 0 and loc.is_visible(timeout=2000):
                return loc
        except Exception:
            continue
    return None


def downloads_dir() -> Path:
    raw = (os.getenv("GEMINI_WEB_DOWNLOADS_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / "Downloads"


def _newest_image_since(folder: Path, since: float) -> Path | None:
    if not folder.is_dir():
        return None
    best: Path | None = None
    best_mtime = since
    for pattern in ("*.png", "*.PNG", "*.jpg", "*.jpeg", "*.JPG", "*.JPEG", "*.webp", "*.WEBP"):
        for p in folder.glob(pattern):
            try:
                m = p.stat().st_mtime
            except OSError:
                continue
            if m >= since and m >= best_mtime:
                best = p
                best_mtime = m
    return best


def _file_size_stable(path: Path, wait_ms: int = 400) -> bool:
    try:
        a = path.stat().st_size
        time.sleep(wait_ms / 1000.0)
        b = path.stat().st_size
        return a > 0 and a == b
    except OSError:
        return False


def _copy_image_as_png(src: Path, dest: Path) -> None:
    """Copia o convierte a PNG en dest (p. ej. pipeline/images/001.png)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    suffix = src.suffix.lower()
    if suffix == ".png":
        shutil.copy2(src, dest)
        return
    try:
        from PIL import Image

        with Image.open(src) as im:
            im.convert("RGB").save(dest, format="PNG")
        return
    except Exception:
        pass
    shutil.copy2(src, dest)


def _wait_for_download_file(
    folder: Path,
    since: float,
    timeout_s: float,
    *,
    work_dir: Path | None = None,
) -> Path | None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if work_dir is not None:
            _abort_if_cancelled(work_dir)
        candidate = _newest_image_since(folder, since - 2.0)
        if candidate and _file_size_stable(candidate):
            return candidate
        time.sleep(0.35)
    return None


def append_job_log(work_dir: Path, job: dict[str, Any], msg: str) -> None:
    lines = job.setdefault("log_lines", [])
    if not isinstance(lines, list):
        lines = []
        job["log_lines"] = lines
    line = f"{_utc_now()} {msg}"
    lines.append(line)
    job["log_lines"] = lines[-40:]
    job["last_log"] = msg
    write_job(work_dir, job)


# Solo imágenes del ÚLTIMO turno del modelo (evita reutilizar imágenes anteriores).
_LAST_TURN_ROOT_JS = """
() => {
  const turnSels = [
    'model-response',
    'message-content',
    '[data-message-author="model"]',
    '.response-container',
    'response-container',
  ];
  for (const sel of turnSels) {
    const nodes = document.querySelectorAll(sel);
    if (nodes.length) return nodes[nodes.length - 1];
  }
  const chat = document.querySelector('infinite-scroller')
    || document.querySelector('[role="main"]')
    || document.querySelector('main');
  if (!chat) return null;
  const blocks = chat.querySelectorAll(
    '[class*="model-response"], [class*="message-content"], [class*="response-container"]'
  );
  if (blocks.length) return blocks[blocks.length - 1];
  return chat;
}
"""

_LAST_TURN_SIGNATURE_JS = """
() => {
  const isAvatar = (src) => {
    if (!src) return true;
    const s = src.toLowerCase();
    if (/avatar|profile|accountphoto/.test(s)) return true;
    if (s.includes('googleusercontent.com/a/')) return true;
    return false;
  };
  const turnSels = ['model-response', 'message-content', '[data-message-author="model"]'];
  let lastTurn = null;
  for (const sel of turnSels) {
    const nodes = document.querySelectorAll(sel);
    if (nodes.length) lastTurn = nodes[nodes.length - 1];
  }
  if (!lastTurn) return { turnCount: 0, sig: '' };
  const turnCount = document.querySelectorAll('model-response').length
    || document.querySelectorAll('message-content').length;
  const parts = [];
  for (const img of lastTurn.querySelectorAll('img, picture img')) {
    const src = img.currentSrc || img.src || '';
    if (isAvatar(src)) continue;
    const w = img.naturalWidth || img.clientWidth || 0;
    const h = img.naturalHeight || img.clientHeight || 0;
    parts.push(`${src}@${w}x${h}`);
  }
  for (const canvas of lastTurn.querySelectorAll('canvas')) {
    parts.push(`canvas@${canvas.width}x${canvas.height}`);
  }
  return { turnCount, sig: parts.join('|'), htmlLen: (lastTurn.innerHTML || '').length };
}
"""

_FIND_BEST_IN_LAST_TURN_META_JS = """
(minSide) => {
  const isAvatar = (src) => {
    if (!src) return true;
    const s = src.toLowerCase();
    if (/avatar|profile|accountphoto/.test(s)) return true;
    if (s.includes('googleusercontent.com/a/')) return true;
    if (/=s(32|40|48|56|64|96)-/.test(s)) return true;
    return false;
  };
  const turnSels = ['model-response', 'message-content', '[data-message-author="model"]'];
  let lastTurn = null;
  for (const sel of turnSels) {
    const nodes = document.querySelectorAll(sel);
    if (nodes.length) lastTurn = nodes[nodes.length - 1];
  }
  if (!lastTurn) return null;
  let best = null;
  let bestArea = 0;
  for (const img of lastTurn.querySelectorAll('img, picture img')) {
    const src = img.currentSrc || img.src || '';
    if (isAvatar(src)) continue;
    if (!img.complete) continue;
    const w = img.naturalWidth || 0;
    const h = img.naturalHeight || 0;
    if (Math.max(w, h) < minSide) continue;
    const area = w * h;
    if (area >= bestArea) {
      bestArea = area;
      best = { kind: 'img', src, w, h };
    }
  }
  if (best) return best;
  for (const canvas of lastTurn.querySelectorAll('canvas')) {
    const w = canvas.width || 0;
    const h = canvas.height || 0;
    if (Math.max(w, h) >= minSide) {
      return { kind: 'canvas', w, h };
    }
  }
  return null;
}
"""

_FIND_BEST_IN_LAST_TURN_ELEMENT_JS = """
(minSide) => {
  const isAvatar = (src) => {
    if (!src) return true;
    const s = src.toLowerCase();
    if (/avatar|profile|accountphoto/.test(s)) return true;
    if (s.includes('googleusercontent.com/a/')) return true;
    if (/=s(32|40|48|56|64|96)-/.test(s)) return true;
    return false;
  };
  const turnSels = ['model-response', 'message-content', '[data-message-author="model"]'];
  let lastTurn = null;
  for (const sel of turnSels) {
    const nodes = document.querySelectorAll(sel);
    if (nodes.length) lastTurn = nodes[nodes.length - 1];
  }
  if (!lastTurn) return null;
  let best = null;
  let bestArea = 0;
  for (const img of lastTurn.querySelectorAll('img, picture img')) {
    const src = img.currentSrc || img.src || '';
    if (isAvatar(src)) continue;
    if (!img.complete) continue;
    const w = img.naturalWidth || 0;
    const h = img.naturalHeight || 0;
    if (Math.max(w, h) < minSide) continue;
    const area = w * h;
    if (area >= bestArea) {
      bestArea = area;
      best = img;
    }
  }
  if (best) return best;
  const canvases = lastTurn.querySelectorAll('canvas');
  if (canvases.length) return canvases[canvases.length - 1];
  return null;
}
"""


def _file_md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _image_state_changed(prev: dict[str, Any], curr: dict[str, Any]) -> bool:
    """True si el último turno tiene una imagen distinta a la capturada antes del prompt."""
    prev_sig = str(prev.get("sig") or "")
    curr_sig = str(curr.get("sig") or "")
    if curr_sig and prev_sig and curr_sig != prev_sig:
        return True
    if int(curr.get("turnCount") or 0) > int(prev.get("turnCount") or 0):
        return True
    if int(curr.get("htmlLen") or 0) > int(prev.get("htmlLen") or 0) + 400:
        return True
    return False


def _image_src_from_state(state: dict[str, Any]) -> str:
    sig = str(state.get("sig") or "")
    if not sig:
        return ""
    return sig.split("@", 1)[0].split("|", 1)[0].strip()


def _last_turn_state(page: Any) -> dict[str, Any]:
    try:
        state = page.evaluate(_LAST_TURN_SIGNATURE_JS)
        return state if isinstance(state, dict) else {"turnCount": 0, "sig": ""}
    except Exception:
        return {"turnCount": 0, "sig": ""}


def _find_best_in_last_turn_meta(page: Any, min_side: int) -> dict[str, Any] | None:
    try:
        meta = page.evaluate(_FIND_BEST_IN_LAST_TURN_META_JS, min_side)
        if isinstance(meta, dict) and (meta.get("src") or meta.get("kind") == "canvas"):
            return meta
    except Exception:
        pass
    return None


def _image_presence_signature(page: Any) -> str:
    state = _last_turn_state(page)
    return str(state.get("sig") or "")


def ready_min_side_px() -> int:
    try:
        return max(256, int(os.getenv("GEMINI_WEB_READY_MIN_PX", "400")))
    except ValueError:
        return 400


def min_image_side_px() -> int:
    return ready_min_side_px()


# Estado del último turno: generando vs imagen real lista.
_LAST_TURN_STATUS_JS = """
(readyMin) => {
  const isAvatar = (src) => {
    if (!src) return true;
    const s = src.toLowerCase();
    if (/avatar|profile|accountphoto/.test(s)) return true;
    if (s.includes('googleusercontent.com/a/')) return true;
    if (/=s(32|40|48|56|64|96)-/.test(s)) return true;
    return false;
  };
  const turnSels = ['model-response', 'message-content', '[data-message-author="model"]'];
  let lastTurn = null;
  for (const sel of turnSels) {
    const nodes = document.querySelectorAll(sel);
    if (nodes.length) lastTurn = nodes[nodes.length - 1];
  }
  if (!lastTurn) {
    return { generating: false, ready: false, hasDownload: false, w: 0, h: 0, src: '' };
  }
  const text = (lastTurn.innerText || '').toLowerCase();
  const creatingText = /creating your image|creando tu imagen|creating image|generating image|generando imagen|working on it/.test(text);

  // Botón stop (círculo con cuadrado): visible mientras genera, desaparece al terminar.
  const stopSelectors = [
    'button[aria-label*="Stop"]',
    'button[aria-label*="Detener"]',
    'button[aria-label*="Cancel"]',
    'button[aria-label*="Cancelar"]',
    'button[data-tooltip*="Stop"]',
    'button[mattooltip*="Stop"]',
    'button[mattooltip*="Detener"]',
    '[aria-label*="Stop response"]',
    '[aria-label*="Detener respuesta"]',
  ].join(', ');
  const hasStopButton = !!document.querySelector(stopSelectors)
    || !!lastTurn.querySelector(stopSelectors);

  const generating =
    hasStopButton
    || creatingText
    || !!lastTurn.querySelector('[aria-busy="true"], mat-progress-spinner, [class*="spinner"], [class*="loading-indicator"]');

  let best = null;
  let bestArea = 0;
  for (const img of lastTurn.querySelectorAll('img, picture img')) {
    const src = img.currentSrc || img.src || '';
    if (isAvatar(src)) continue;
    if (!img.complete) continue;
    const w = img.naturalWidth || 0;
    const h = img.naturalHeight || 0;
    if (Math.max(w, h) < readyMin) continue;
    const area = w * h;
    if (area >= bestArea) {
      bestArea = area;
      best = { w, h, src };
    }
  }
  const hasDownload = !!lastTurn.querySelector(
    'button[aria-label*="Download"], button[aria-label*="Descargar"], [aria-label*="Download"], [aria-label*="Descargar"]'
  );
  const generationDone = !hasStopButton && !creatingText;
  const ready = generationDone && !!best && Math.max(best.w, best.h) >= readyMin;
  return {
    generating,
    generationDone,
    hasStopButton,
    creatingText,
    ready,
    hasDownload,
    w: best ? best.w : 0,
    h: best ? best.h : 0,
    src: best ? best.src : '',
  };
}
"""


def _last_turn_status(page: Any, ready_min: int | None = None) -> dict[str, Any]:
    side = ready_min if ready_min is not None else ready_min_side_px()
    try:
        st = page.evaluate(_LAST_TURN_STATUS_JS, side)
        return st if isinstance(st, dict) else {}
    except Exception:
        return {}


def _validate_saved_image(dest: Path, min_side: int | None = None, *, strict: bool = True) -> bool:
    side = min_side if min_side is not None else (min_saved_side_px() if strict else ready_min_side_px())
    min_bytes = min_saved_file_bytes() if strict else 20_000
    try:
        if not dest.is_file():
            return False
        size = dest.stat().st_size
        if size < min_bytes:
            return False
        from PIL import Image

        with Image.open(dest) as im:
            w, h = im.size
            if max(w, h) < side:
                return False
            # Rechazar PNG casi vacíos / placeholder gris uniforme
            thumb = im.convert("RGB").resize((32, 32))
            px = list(thumb.getdata())
            if len(px) < 2:
                return False
            r0, g0, b0 = px[0]
            uniform = sum(1 for r, g, b in px if abs(r - r0) < 8 and abs(g - g0) < 8 and abs(b - b0) < 8)
            if uniform / len(px) > 0.92 and max(r0, g0, b0) > 200:
                return False
        return True
    except Exception:
        return dest.is_file() and dest.stat().st_size > 80_000


def _wait_until_image_ready(
    page: Any,
    *,
    since: float,
    timeout_s: float,
    work_dir: Path,
    prev_state: dict[str, Any] | None = None,
    log: LogFn | None = None,
) -> bool:
    """Espera: generación real → imagen nueva distinta a prev_state → guardar."""
    deadline = time.time() + timeout_s
    ready_min = ready_min_side_px()
    stable_hits = 0
    stop_gone_hits = 0
    prev = prev_state or {}
    saw_generation = False

    def _log(msg: str) -> None:
        if log:
            log(msg)

    _log(f"Esperando fin de generación (botón stop + mín. {ready_min}px)…")
    while time.time() < deadline:
        _abort_if_cancelled(work_dir, page, log=_log)
        _scroll_page_to_bottom(page)

        curr_state = _last_turn_state(page)
        if _image_state_changed(prev, curr_state):
            saw_generation = True

        found = _newest_image_since(downloads_dir(), since)
        if found and _file_size_stable(found) and found.stat().st_size > 25_000:
            _log(f"Archivo nuevo en Descargas: {found.name}")
            return True

        st = _last_turn_status(page, ready_min)
        if st.get("hasStopButton") or st.get("creatingText"):
            stable_hits = 0
            stop_gone_hits = 0
            saw_generation = True
            if st.get("hasStopButton"):
                _log("Generando… (botón stop visible)")
            else:
                _log("Generando… (Creating your image)")
        elif st.get("generationDone"):
            stop_gone_hits += 1
            if stop_gone_hits == 1:
                _log("Botón stop desapareció — comprobando imagen final…")
            curr_src = str(st.get("src") or "")
            prev_src = _image_src_from_state(prev)
            unchanged = bool(curr_src and prev_src and curr_src == prev_src) and not _image_state_changed(
                prev, curr_state
            )
            if unchanged and not saw_generation:
                _log("Imagen anterior aún visible; esperando nueva generación…")
                stable_hits = 0
                _wait_ms(page, work_dir, 900)
                continue
            if unchanged and saw_generation:
                _log("Generación terminó pero la imagen no cambió; esperando…")
                stable_hits = 0
                _wait_ms(page, work_dir, 900)
                continue
            if st.get("ready"):
                stable_hits += 1
                w, h = int(st.get("w") or 0), int(st.get("h") or 0)
                _log(f"Imagen lista {w}×{h}px ({stable_hits}/2)")
                if stable_hits >= 2 and _image_state_changed(prev, curr_state):
                    _wait_ms(page, work_dir, 600)
                    return True
            elif st.get("hasDownload") and stop_gone_hits >= 2 and _image_state_changed(prev, curr_state):
                _log("Descargar visible tras fin de generación; esperando render…")
                _wait_ms(page, work_dir, 1500)
                st2 = _last_turn_status(page, ready_min)
                if st2.get("ready") or st2.get("hasDownload"):
                    return True
        elif st.get("generating"):
            stable_hits = 0
            stop_gone_hits = 0
            saw_generation = True
            _log("Gemini aún generando…")
        else:
            stable_hits = 0

        _wait_ms(page, work_dir, 900)

    _abort_if_cancelled(work_dir, page, log=_log)
    st = _last_turn_status(page, ready_min)
    curr_state = _last_turn_state(page)
    if (
        st.get("generationDone")
        and (st.get("ready") or st.get("hasDownload"))
        and _image_state_changed(prev, curr_state)
    ):
        _log("Imagen lista al límite del timeout.")
        return True
    return False


def _is_avatar_src(src: str) -> bool:
    """URLs típicas de foto de perfil Google (no imágenes generadas)."""
    s = (src or "").lower()
    if not s:
        return True
    if "avatar" in s or "profile" in s or "accountphoto" in s:
        return True
    # Avatares: googleusercontent.com/a/ACg8oc...
    if "googleusercontent.com/a/" in s:
        return True
    if "ggpht.com" in s and any(tok in s for tok in ("=s32-", "=s40-", "=s48-", "=s56-", "=s64-", "=s96-", "/s32-", "/s64-")):
        return True
    return False


def _image_dims(img: Any) -> tuple[int, int]:
    try:
        dims = img.evaluate(
            "el => ({ w: el.naturalWidth || el.clientWidth || el.width || 0, "
            "h: el.naturalHeight || el.clientHeight || el.height || 0 })"
        )
        return int(dims.get("w") or 0), int(dims.get("h") or 0)
    except Exception:
        return 0, 0


def _is_generated_candidate(img: Any, *, min_side: int) -> bool:
    try:
        src = img.get_attribute("src") or ""
        if _is_avatar_src(src):
            return False
        w, h = _image_dims(img)
        if max(w, h) < min_side:
            return False
        # Descartar iconos cuadrados minúsculos aunque pasen el filtro de URL
        if w > 0 and h > 0 and max(w, h) < 180 and abs(w - h) < 20:
            return False
        return True
    except Exception:
        return False


def _iter_response_scopes(page: Any) -> list[Any]:
    scopes: list[Any] = []
    for sel in ("model-response", "message-content", "[data-message-author='model']"):
        loc = page.locator(sel)
        try:
            if loc.count() > 0:
                scopes.append(loc.last)
        except Exception:
            continue
    return scopes


def _last_generated_image_locator(page: Any) -> Any | None:
    """Imagen/canvas del último turno del modelo."""
    min_side = min_image_side_px()
    for side in (min_side, min(150, min_side), 80, 48):
        try:
            handle = page.evaluate_handle(_FIND_BEST_IN_LAST_TURN_ELEMENT_JS, side)
            el = handle.as_element()
            if el is not None:
                return el
        except Exception:
            continue

    meta = _find_best_in_last_turn_meta(page, 48)
    if meta and meta.get("src"):
        src = str(meta["src"])
        for loc in (
            page.locator(f'img[src="{src}"]'),
            page.locator(f'img[src*="{src.split("?")[0][-40:]}"]'),
        ):
            try:
                if loc.count() > 0:
                    return loc.last
            except Exception:
                continue
    return None


def _count_generated_images(page: Any) -> int:
    return 1 if _find_best_in_last_turn_meta(page, 48) else 0


def _response_has_download_button(page: Any) -> bool:
    for sel in (
        "model-response button[aria-label*='Download']",
        "model-response button[aria-label*='Descargar']",
        "message-content button[aria-label*='Download']",
        "message-content button[aria-label*='Descargar']",
        "button[aria-label*='Download image']",
        "button[aria-label*='Descargar imagen']",
    ):
        try:
            if page.locator(sel).count() > 0:
                return True
        except Exception:
            continue
    return False


def _scroll_page_to_bottom(page: Any) -> None:
    """Desplaza la conversación al final sin depender de un locator concreto."""
    try:
        page.keyboard.press("End")
        page.wait_for_timeout(250)
    except Exception:
        pass
    try:
        page.evaluate(
            """() => {
              const main = document.querySelector('main') || document.body;
              main.scrollTop = main.scrollHeight;
              window.scrollTo(0, document.body.scrollHeight);
            }"""
        )
        page.wait_for_timeout(400)
    except Exception:
        pass


def _last_image_locator(page: Any) -> Any | None:
    return _last_generated_image_locator(page)


def _save_via_canvas_export(page: Any, img: Any, dest: Path) -> bool:
    """Exporta img o canvas del último turno a PNG."""
    try:
        data_url = img.evaluate(
            """(el) => {
              if (!el) return null;
              if (el.tagName === 'CANVAS') {
                try { return el.toDataURL('image/png'); } catch (e) { return null; }
              }
              const w = el.naturalWidth || el.width || el.clientWidth;
              const h = el.naturalHeight || el.height || el.clientHeight;
              if (!w || !h) return null;
              const c = document.createElement('canvas');
              c.width = w;
              c.height = h;
              const ctx = c.getContext('2d');
              if (!ctx) return null;
              try {
                ctx.drawImage(el, 0, 0);
                return c.toDataURL('image/png');
              } catch (e) {
                return null;
              }
            }"""
        )
        if not data_url or not str(data_url).startswith("data:image"):
            return False
        import base64

        raw = str(data_url).split(",", 1)[1]
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(base64.b64decode(raw))
        return dest.is_file() and dest.stat().st_size > 0
    except Exception:
        return False


def _save_via_last_turn_screenshot(page: Any, dest: Path) -> bool:
    """Evitado como fallback principal: captura placeholders de carga."""
    return False


def _commit_saved_image(
    dest: Path,
    *,
    reject_md5: set[str] | None = None,
    log: LogFn | None = None,
    strict: bool = True,
) -> bool:
    if not _validate_saved_image(dest, strict=strict):
        if dest.is_file():
            try:
                from PIL import Image

                with Image.open(dest) as im:
                    w, h = im.size
                    kb = dest.stat().st_size // 1024
                    detail = f"{w}×{h}px, {kb} KB"
            except Exception:
                detail = f"{dest.stat().st_size // 1024} KB"
            dest.unlink(missing_ok=True)
            if log:
                if strict:
                    log(
                        f"Archivo rechazado ({detail}): se espera descarga oficial "
                        f"(≥{min_saved_side_px()}px, ≥{min_saved_file_bytes() // 1024} KB)."
                    )
                else:
                    log("Archivo rechazado (placeholder o demasiado pequeño).")
        return False
    if reject_md5:
        digest = _file_md5(dest)
        if digest in reject_md5:
            dest.unlink(missing_ok=True)
            if log:
                log("Imagen duplicada (idéntica a una ya guardada en esta cola).")
            return False
    return True


def _save_from_downloads_folder(
    dest: Path,
    since: float,
    *,
    work_dir: Path | None = None,
    reject_md5: set[str] | None = None,
    log: LogFn | None = None,
) -> bool:
    downloads = downloads_dir()
    found = _newest_image_since(downloads, since)
    if not found:
        found = _wait_for_download_file(downloads, since, timeout_s=2.0, work_dir=work_dir)
    if not found:
        return False
    if not _file_size_stable(found):
        return False
    _copy_image_as_png(found, dest)
    if dest.is_file() and dest.stat().st_size > 0:
        if not _commit_saved_image(dest, reject_md5=reject_md5, log=log):
            return False
        if log:
            log(f"Movido desde Descargas: {found.name} → {dest.name}")
        return True
    return False


def _save_via_http_src(page: Any, img: Any, dest: Path) -> bool:
    try:
        src = img.get_attribute("src")
        if not src or not src.startswith("http"):
            return False
        resp = page.request.get(src, timeout=45_000)
        if not resp.ok:
            return False
        body = resp.body()
        if not body:
            return False
        tmp = dest.with_suffix(".part")
        tmp.write_bytes(body)
        _copy_image_as_png(tmp, dest)
        tmp.unlink(missing_ok=True)
        return dest.is_file() and dest.stat().st_size > 0
    except Exception:
        return False


def _click_download_in_last_turn(page: Any) -> bool:
    _scroll_page_to_bottom(page)
    scopes: list[Any] = []
    for sel in ("model-response", "message-content", "[data-message-author='model']"):
        loc = page.locator(sel).last
        try:
            if loc.count() > 0:
                scopes.append(loc)
        except Exception:
            pass
    if not scopes:
        return False

    img = _last_generated_image_locator(page)
    if img is not None:
        try:
            img.hover(timeout=2000)
        except Exception:
            pass
        page.wait_for_timeout(250)

    download_selectors = (
        "button[aria-label*='Download']",
        "button[aria-label*='Descargar']",
        "button[data-tooltip*='Download']",
        "button[data-tooltip*='Descargar']",
        "button[mattooltip*='Download']",
        "button[mattooltip*='Descargar']",
        "[aria-label*='Download']",
        "[aria-label*='Descargar']",
        "mat-icon[data-mat-icon-name='download']",
    )
    for scope in scopes:
        for sel in download_selectors:
            btn = scope.locator(sel).last
            try:
                if btn.count() > 0:
                    btn.click(timeout=4000, force=True)
                    return True
            except Exception:
                continue
    return False


def _click_download_for_latest_image(page: Any) -> bool:
    return _click_download_in_last_turn(page)


def _wait_for_download_button(page: Any, timeout_s: float = 12.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if _response_has_download_button(page):
            return True
        page.wait_for_timeout(350)
    return _response_has_download_button(page)


def _save_via_official_download(
    page: Any,
    dest: Path,
    *,
    since: float,
    work_dir: Path,
    reject_md5: set[str] | None = None,
    log: LogFn | None = None,
) -> bool:
    """Solo botón Descargar de Gemini + archivo en ~/Downloads (misma calidad que manual)."""
    downloads = downloads_dir()

    def _log(msg: str) -> None:
        if log:
            log(msg)

    _scroll_page_to_bottom(page)
    if not _wait_for_download_button(page, timeout_s=15.0):
        _log("Botón Descargar no visible aún.")
        return False

    img = _last_generated_image_locator(page)
    if img is not None:
        try:
            img.hover(timeout=3000)
            page.wait_for_timeout(500)
        except Exception:
            pass

    for attempt in range(1, 3):
        if attempt > 1:
            _log(f"Reintento descarga oficial ({attempt}/2)…")
            page.wait_for_timeout(800)

        try:
            with page.expect_download(timeout=25_000) as dl_info:
                if not _click_download_in_last_turn(page):
                    raise RuntimeError("No se pudo pulsar Descargar")
            download = dl_info.value
            tmp = dest.with_suffix(".part")
            download.save_as(str(tmp))
            if tmp.is_file() and tmp.stat().st_size > 0:
                if tmp.suffix.lower() != ".png":
                    _copy_image_as_png(tmp, dest)
                    tmp.unlink(missing_ok=True)
                else:
                    shutil.move(str(tmp), str(dest))
                if _commit_saved_image(dest, reject_md5=reject_md5, log=_log, strict=True):
                    kb = dest.stat().st_size // 1024
                    _log(f"Descarga oficial (Playwright) → {dest.name} ({kb} KB)")
                    return True
            if dest.is_file():
                dest.unlink(missing_ok=True)
        except Exception as e:
            _log(f"Playwright download: {str(e)[:120]}")
            if dest.is_file():
                dest.unlink(missing_ok=True)

        click_since = time.time()
        if _click_download_in_last_turn(page):
            _log(f"Esperando PNG en {downloads}…")
            found = _wait_for_download_file(downloads, click_since - 1.0, timeout_s=60.0, work_dir=work_dir)
            if not found:
                found = _wait_for_download_file(downloads, since, timeout_s=15.0, work_dir=work_dir)
            if found:
                _copy_image_as_png(found, dest)
                if _commit_saved_image(dest, reject_md5=reject_md5, log=_log, strict=True):
                    kb = dest.stat().st_size // 1024
                    _log(f"Descarga oficial (Descargas) → {dest.name} ({kb} KB)")
                    return True
        if dest.is_file():
            dest.unlink(missing_ok=True)

    return False


def _save_image_from_page(
    page: Any,
    dest: Path,
    *,
    work_dir: Path,
    since: float | None = None,
    prev_state: dict[str, Any] | None = None,
    reject_md5: set[str] | None = None,
    log: LogFn | None = None,
) -> bool:
    """Guarda la imagen del último turno en dest (001.png…). Prioriza descarga oficial (full-res)."""
    dl_since = since if since is not None else time.time()
    prev = prev_state or {}

    def _log(msg: str) -> None:
        if log:
            log(msg)

    def _reject_duplicate_src() -> bool:
        meta = _find_best_in_last_turn_meta(page, ready_min_side_px())
        if not meta:
            return False
        curr_src = str(meta.get("src") or "")
        prev_src = _image_src_from_state(prev)
        if curr_src and prev_src and curr_src == prev_src:
            _log(
                f"Rechazado: misma imagen que antes del prompt (src={curr_src[:60]}…). "
                "Gemini no generó una imagen nueva."
            )
            return True
        return False

    _abort_if_cancelled(work_dir, page, log=_log)
    _scroll_page_to_bottom(page)
    _log("Guardando con descarga oficial de Gemini (máxima calidad)…")

    if _reject_duplicate_src():
        return False

    if _last_generated_image_locator(page) is None:
        st = _last_turn_status(page)
        _log(f"Sin imagen en último turno (estado={st}).")
        return False

    if _reject_duplicate_src():
        return False

    if _save_via_official_download(
        page,
        dest,
        since=dl_since,
        work_dir=work_dir,
        reject_md5=reject_md5,
        log=log,
    ):
        return True

    if not allow_preview_fallback():
        _log(
            "No se obtuvo PNG de calidad suficiente. Comprueba el botón Descargar en Chrome "
            "o define GEMINI_WEB_ALLOW_PREVIEW_FALLBACK=1 para permitir preview (baja calidad)."
        )
        return False

    _log("AVISO: usando fallback preview (baja calidad). Activa solo si falla la descarga oficial.")
    img = _last_generated_image_locator(page)
    if img is None:
        return False

    if _save_via_canvas_export(page, img, dest) and _commit_saved_image(
        dest, reject_md5=reject_md5, log=_log, strict=False
    ):
        _log(f"Exportado desde DOM (preview) → {dest.name}")
        return True
    if dest.is_file():
        dest.unlink(missing_ok=True)

    if _save_via_http_src(page, img, dest) and _commit_saved_image(
        dest, reject_md5=reject_md5, log=_log, strict=False
    ):
        _log(f"Descargado por URL (preview) → {dest.name}")
        return True
    if dest.is_file():
        dest.unlink(missing_ok=True)

    try:
        img.screenshot(path=str(dest), timeout=30_000, force=True)
        if _commit_saved_image(dest, reject_md5=reject_md5, log=_log, strict=False):
            _log(f"Captura del elemento (preview) → {dest.name}")
            return True
    except Exception as e:
        _log(f"Captura elemento: {str(e)[:100]}")
    if dest.is_file():
        dest.unlink(missing_ok=True)

    return False


def _wait_for_new_image(
    page: Any,
    prev_state: dict[str, Any],
    timeout_s: float,
    *,
    work_dir: Path,
    since: float,
    log: LogFn | None = None,
) -> bool:
    """Espera imagen nueva distinta a prev_state (no reutilizar la anterior)."""
    return _wait_until_image_ready(
        page,
        since=since,
        timeout_s=timeout_s,
        work_dir=work_dir,
        prev_state=prev_state,
        log=log,
    )


def _submit_prompt(page: Any, prompt: str) -> None:
    box = _find_input(page)
    if box is None:
        raise RuntimeError("No se encontró el cuadro de texto en Gemini. ¿Estás en gemini.google.com/app?")
    try:
        box.scroll_into_view_if_needed(timeout=5000)
    except Exception:
        _scroll_page_to_bottom(page)
    try:
        box.click(timeout=5000)
    except Exception:
        box.click(timeout=5000, force=True)
    page.wait_for_timeout(300)
    mod = "Meta" if os.uname().sysname == "Darwin" else "Control"
    page.keyboard.press(f"{mod}+A")
    page.keyboard.press("Backspace")
    page.wait_for_timeout(200)
    chunk = 4000
    text = prompt.strip()
    for i in range(0, len(text), chunk):
        page.keyboard.insert_text(text[i : i + chunk])
        page.wait_for_timeout(100)
    page.wait_for_timeout(400)
    page.keyboard.press("Enter")


def _get_or_create_gemini_page(browser: Any) -> Any:
    for ctx in browser.contexts:
        for page in ctx.pages:
            if "gemini.google.com" in (page.url or ""):
                page.bring_to_front()
                return page
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()
    page.goto(GEMINI_APP_URL, wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_timeout(3500)
    return page


def _start_new_gemini_conversation(page: Any, browser: Any, *, log: LogFn | None = None) -> Any:
    """Abre un chat nuevo en Gemini (misma pestaña o pestaña nueva si hace falta)."""
    if log:
        log("Abriendo conversación nueva en Gemini…")
    try:
        page.bring_to_front()
        page.goto(GEMINI_APP_URL, wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(4500)
        if _find_input(page) is not None:
            return page
    except Exception:
        pass
    ctx = page.context if getattr(page, "context", None) else (browser.contexts[0] if browser.contexts else browser.new_context())
    new_page = ctx.new_page()
    new_page.goto(GEMINI_APP_URL, wait_until="domcontentloaded", timeout=120_000)
    new_page.wait_for_timeout(4500)
    return new_page


def resolve_gemini_queue_ids(
    work_dir: Path,
    image_ids: list[str],
    *,
    order_from: int | None = None,
    order_to: int | None = None,
    skip_generated: bool = True,
) -> list[str]:
    """Filtra IDs por rango de orden y estado pendiente."""
    from videomaker.pipeline.images_generation_runner import load_manifest

    manifest = load_manifest(work_dir)
    rows = [r for r in (manifest.get("images") or []) if isinstance(r, dict)]
    if order_from is not None or order_to is not None:
        lo = order_from if order_from is not None else 0
        hi = order_to if order_to is not None else 999_999
        rows = [r for r in rows if lo <= int(r.get("order") or 0) <= hi]
    if image_ids:
        wanted = {str(i) for i in image_ids}
        rows = [r for r in rows if str(r.get("id")) in wanted]
    if skip_generated:
        rows = [r for r in rows if r.get("status") != "generated"]
    rows = [r for r in rows if str(r.get("role") or "") != "thumbnail"]
    rows.sort(key=lambda r: int(r.get("order") or 0))
    return [str(r.get("id")) for r in rows if r.get("id")]


def run_gemini_web_batch(
    work_dir: Path,
    *,
    work_slug: str,
    image_ids: list[str],
    skip_generated: bool = True,
    batch_mode: bool = True,
    batch_size: int = 1,
    log: LogFn | None = None,
) -> dict[str, Any]:
    """
    Procesa la cola en Gemini web (Chrome CDP + sesión Pro).

    Sin batch_mode: una sola conversación para todas las imágenes.
    Con batch_mode: lotes de hasta batch_size imágenes; conversación nueva entre lotes.
    Por defecto batch_size=1 → una conversación por imagen (más variedad de escena).
    """
    from videomaker.engines.google_imagen import local_image_api_url
    from videomaker.pipeline.images_generation_runner import (
        _apply_selection_from_ids,
        _reset_stale_errors,
        images_dir,
        load_manifest,
        order_filename,
    )
    from videomaker.pipeline.runner import save_manual_images_generation_bundle
    from videomaker.scene_editor.scene_visual_settings_store import read_scene_visual_settings
    from videomaker.scene_editor.visual_prompt_compose import compose_gemini_queue_prompt

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RuntimeError(
            "Falta playwright. En el venv: pip install playwright && playwright install chromium"
        ) from e

    manifest = load_manifest(work_dir)
    wanted = set(str(i) for i in image_ids)
    _apply_selection_from_ids(manifest, image_ids)
    _reset_stale_errors(manifest, wanted)
    save_manual_images_generation_bundle(work_dir, manifest)

    rows = [r for r in (manifest.get("images") or []) if isinstance(r, dict) and str(r.get("id")) in wanted]
    if skip_generated:
        rows = [r for r in rows if r.get("status") != "generated"]
    rows.sort(key=lambda r: int(r.get("order") or 0))

    if not rows:
        raise ValueError("No hay imágenes seleccionadas pendientes.")

    items = [
        {
            "id": str(r.get("id")),
            "order": int(r.get("order") or 0),
            "status": "queued",
            "detail": "",
        }
        for r in rows
    ]

    batch_size_eff = max(1, int(batch_size)) if batch_mode else len(items)
    batches = [items[i : i + batch_size_eff] for i in range(0, len(items), batch_size_eff)]
    use_batches = batch_mode and len(batches) > 1

    job: dict[str, Any] = {
        "state": "running",
        "work": work_slug,
        "started_at": _utc_now(),
        "total": len(items),
        "done": 0,
        "failed": 0,
        "current_order": None,
        "current_id": None,
        "page_url": None,
        "cancel_requested": False,
        "batch_mode": use_batches,
        "batch_size": batch_size_eff if batch_mode else None,
        "batch_total": len(batches) if batch_mode else 1,
        "batch_index": 0,
        "items": items,
    }
    write_job(work_dir, job)

    visual_settings = read_scene_visual_settings(work_dir)
    prompts_path = work_dir / "pipeline" / "image_prompts.json"
    if prompts_path.is_file():
        try:
            bundle = json.loads(prompts_path.read_text(encoding="utf-8"))
            gs = bundle.get("global_style")
            if isinstance(gs, dict):
                for key in ("base_style_en", "protagonist_en", "avoid_en", "aspect_ratio", "output_spec"):
                    if gs.get(key):
                        visual_settings[key] = gs[key]
        except (OSError, json.JSONDecodeError):
            pass

    def _log(msg: str) -> None:
        append_job_log(work_dir, job, msg)
        if log:
            log(msg)

    generated = 0
    failed = 0
    out_dir = images_dir(work_dir)

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(cdp_url(), timeout=15_000)
        page = _get_or_create_gemini_page(browser)
        job["page_url"] = page.url
        write_job(work_dir, job)
        _log(f"Conversación: {page.url}")
        if use_batches:
            _log(f"Modo lotes: {len(batches)} conversaciones · {batch_size_eff} imágenes por lote")

        try:
            for batch_idx, batch_items in enumerate(batches):
                if batch_idx > 0:
                    _abort_if_cancelled(work_dir, page, log=_log)
                    _log(f"=== Lote {batch_idx + 1}/{len(batches)} — nueva conversación ===")
                    page = _start_new_gemini_conversation(page, browser, log=_log)
                    job["batch_index"] = batch_idx
                    job["page_url"] = page.url
                    write_job(work_dir, job)
                    _log(f"Conversación: {page.url}")
                    _wait_ms(page, work_dir, 5000)

                first_in_gemini_run = True
                previous_scene_summary: str | None = None
                saved_md5s: set[str] = set()

                if use_batches:
                    batch_orders = [it["order"] for it in batch_items]
                    _log(
                        f"Lote {batch_idx + 1}: #{batch_orders[0]}–#{batch_orders[-1]} "
                        f"({len(batch_items)} imágenes)"
                    )

                for item_idx, item in enumerate(batch_items):
                    _abort_if_cancelled(work_dir, page, log=_log)

                    order = item["order"]
                    row = next((r for r in rows if int(r.get("order") or 0) == order), None)
                    if not row:
                        continue

                    full_prompt = str(row.get("ai_prompt") or "").strip()
                    scene_prompt = str(row.get("scene_prompt_en") or "").strip()
                    prompt = compose_gemini_queue_prompt(
                        scene_prompt_en=scene_prompt,
                        full_prompt=full_prompt,
                        settings=visual_settings,
                        first_in_run=first_in_gemini_run,
                        previous_scene_summary=previous_scene_summary,
                    )
                    if not prompt:
                        item["status"] = "error"
                        item["detail"] = "Prompt vacío"
                        failed += 1
                        job["failed"] = failed
                        write_job(work_dir, job)
                        continue

                    dest = out_dir / order_filename(order)
                    item["status"] = "running"
                    job["current_order"] = order
                    job["current_id"] = item["id"]
                    job["done"] = generated
                    job["failed"] = failed
                    job["state"] = "running"
                    if batch_mode:
                        job["batch_index"] = batch_idx
                    write_job(work_dir, job)
                    _log(f"Generando #{order} ({order_filename(order)})…")

                    try:
                        prompt_started = time.time()
                        prev_state = _last_turn_state(page)
                        _log(f"Enviando prompt #{order}…")
                        _submit_prompt(page, prompt)
                        first_in_gemini_run = False
                        _abort_if_cancelled(work_dir, page, log=_log)
                        ready = _wait_for_new_image(
                            page,
                            prev_state,
                            response_timeout_sec(),
                            work_dir=work_dir,
                            since=prompt_started,
                            log=_log,
                        )
                        if not ready:
                            _log("Timeout en detección; intentando guardar igualmente…")

                        settle_ms = post_ready_settle_ms()
                        if settle_ms > 0 and ready:
                            _log(f"Esperando {settle_ms / 1000:.1f}s para archivo full-res…")
                            _wait_ms(page, work_dir, settle_ms)

                        _abort_if_cancelled(work_dir, page, log=_log)
                        if not _save_image_from_page(
                            page,
                            dest,
                            work_dir=work_dir,
                            since=prompt_started,
                            prev_state=prev_state,
                            reject_md5=saved_md5s,
                            log=_log,
                        ):
                            if not ready:
                                raise RuntimeError(
                                    "Tiempo de espera agotado esperando la imagen en Gemini "
                                    "(no se detectó en el chat ni se pudo guardar)."
                                )
                            raise RuntimeError(
                                "No se guardó PNG en calidad de descarga manual "
                                f"(≥{min_saved_file_bytes() // 1024} KB). "
                                "Comprueba Descargar en Gemini o baja GEMINI_WEB_MIN_FILE_BYTES. "
                                f"Reintenta #{order}."
                            )

                        saved_md5s.add(_file_md5(dest))

                        manifest = load_manifest(work_dir)
                        fn = order_filename(order)
                        for r in manifest.get("images") or []:
                            if isinstance(r, dict) and int(r.get("order") or 0) == order:
                                r["status"] = "generated"
                                r["filename"] = fn
                                r.pop("error", None)
                                r["local_url"] = local_image_api_url(work_slug, fn)
                                break
                        manifest["generator"] = "gemini_web_pro"
                        save_manual_images_generation_bundle(work_dir, manifest)
                        item["status"] = "done"
                        item["detail"] = order_filename(order)
                        generated += 1
                        if scene_prompt:
                            previous_scene_summary = scene_prompt[:180]
                        elif full_prompt:
                            previous_scene_summary = full_prompt[:180]
                        _log(f"✓ {order_filename(order)}")
                    except GeminiBatchCancelled:
                        item["status"] = "cancelled"
                        item["detail"] = "cancelled"
                        raise
                    except Exception as e:
                        item["status"] = "error"
                        item["detail"] = str(e)[:400]
                        failed += 1
                        manifest = load_manifest(work_dir)
                        for r in manifest.get("images") or []:
                            if isinstance(r, dict) and int(r.get("order") or 0) == order:
                                r["status"] = "error"
                                r["error"] = str(e)[:400]
                                break
                        save_manual_images_generation_bundle(work_dir, manifest)
                        _log(f"✗ #{order}: {e}")

                    job["done"] = generated
                    job["failed"] = failed
                    job["current_order"] = None
                    job["current_id"] = None
                    write_job(work_dir, job)

                    if item_idx < len(batch_items) - 1:
                        delay_ms = int(delay_between_sec() * 1000)
                        _log(f"Esperando {delay_between_sec():.0f}s antes del siguiente…")
                        _wait_ms(page, work_dir, delay_ms)
        except GeminiBatchCancelled:
            _log("Cola cancelada.")
            job = read_job(work_dir) or job
            job["state"] = "cancelled"
            job["current_order"] = None
            job["current_id"] = None
            job["finished_at"] = _utc_now()
            job["last_log"] = "Cola cancelada."
            for it in job.get("items") or []:
                if isinstance(it, dict) and it.get("status") == "running":
                    it["status"] = "cancelled"
                    it["detail"] = "cancelled"
            write_job(work_dir, job)

    job = read_job(work_dir) or job
    if job.get("state") != "cancelled":
        job["state"] = "done" if failed == 0 else ("done" if generated > 0 else "error")
    job["current_order"] = None
    job["current_id"] = None
    job["finished_at"] = _utc_now()
    write_job(work_dir, job)

    return {
        "generated": generated,
        "failed": failed,
        "total": len(items),
        "page_url": job.get("page_url"),
    }


def request_cancel(work_dir: Path) -> dict[str, Any]:
    job = read_job(work_dir) or {}
    slug = _work_slug(work_dir, job)
    with _JOB_LOCK:
        ev = _CANCEL_EVENTS.get(slug)
        if ev is not None:
            ev.set()
    job["cancel_requested"] = True
    job["state"] = "cancelled"
    job["current_order"] = None
    job["current_id"] = None
    job["finished_at"] = _utc_now()
    job["last_log"] = "Cancelación solicitada — deteniendo cola…"
    for item in job.get("items") or []:
        if isinstance(item, dict) and item.get("status") == "running":
            item["status"] = "cancelled"
            item["detail"] = "cancelled"
    write_job(work_dir, job)
    return job


def run_batch_in_background(
    work_dir: Path,
    work_slug: str,
    image_ids: list[str],
    skip_generated: bool,
    *,
    batch_mode: bool = True,
    batch_size: int = 1,
) -> None:
    global _ACTIVE_WORK

    cancel_ev = threading.Event()

    def _worker() -> None:
        global _ACTIVE_WORK
        try:
            run_gemini_web_batch(
                work_dir,
                work_slug=work_slug,
                image_ids=image_ids,
                skip_generated=skip_generated,
                batch_mode=batch_mode,
                batch_size=batch_size,
            )
        except GeminiBatchCancelled:
            pass
        except Exception as e:
            job = read_job(work_dir) or {
                "state": "error",
                "total": len(image_ids),
                "done": 0,
                "failed": 0,
                "items": [],
            }
            if job.get("state") != "cancelled":
                job["state"] = "error"
                job["error"] = str(e)[:500]
                job["finished_at"] = _utc_now()
                write_job(work_dir, job)
        finally:
            cancel_ev.clear()
            with _JOB_LOCK:
                _CANCEL_EVENTS.pop(work_slug, None)
                if _ACTIVE_WORK == work_slug:
                    _ACTIVE_WORK = None

    with _JOB_LOCK:
        if _ACTIVE_WORK:
            raise RuntimeError(f"Ya hay una cola Gemini activa: {_ACTIVE_WORK}")
        _ACTIVE_WORK = work_slug
        _CANCEL_EVENTS[work_slug] = cancel_ev

    t = threading.Thread(target=_worker, name=f"gemini-web-{work_slug}", daemon=True)
    t.start()


def chrome_launch_hint() -> str:
    profile = Path.home() / ".videomaker-chrome-profile"
    return (
        "Cierra Chrome por completo (⌘Q) y ábrelo así (macOS):\n\n"
        f'/Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome \\\n'
        f'  --remote-debugging-port=9222 \\\n'
        f'  --user-data-dir="{profile}"\n\n'
        "Inicia sesión, abre https://gemini.google.com/app y deja esa ventana abierta.\n"
        "Playwright (solo una vez, en el venv del repo):\n"
        "  .venv/bin/python -m pip install playwright\n"
        "  .venv/bin/playwright install chromium"
    )
