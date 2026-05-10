"""Fragmentación del guion por estructura (4 actos / 5 bloques) con estado en disco."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from videomaker.llm.narrative_presets import weights_for_narrative_preset

STRUCTURE_PRESETS = ("four_act", "default_five_blocks")

# ids estables para rutas y UI
FRAGMENT_PLANS: dict[str, list[tuple[str, str]]] = {
    "four_act": [
        ("hook", "Hook / tensión inicial"),
        ("promesa", "Acto 2 · Promesa"),
        ("desarrollo", "Acto 3 · Desarrollo"),
        ("cierre", "Acto 4 · Cierre"),
    ],
    "default_five_blocks": [
        ("intro", "Introducción"),
        ("pilar_1", "Pilar 1"),
        ("pilar_2", "Pilar 2"),
        ("pilar_3", "Pilar 3"),
        ("cierre", "Cierre"),
    ],
}

# Por defecto 4 actos = preset Finanzas / documental (15 / 25 / 45 / 15 % del tiempo total).
DEFAULT_MINUTE_WEIGHTS_FOUR_ACT: tuple[float, ...] = (0.15, 0.25, 0.45, 0.15)
# 5 bloques: intro corta, tres pilares equilibrados, cierre con algo más de room para CTA/reflexión.
DEFAULT_MINUTE_WEIGHTS_FIVE_BLOCKS: tuple[float, ...] = (0.10, 0.20, 0.22, 0.22, 0.26)

FragmentStatus = Literal["pending", "generated", "done"]

# Misma cadena que script_gen.compose_messages (evitar import circular).
_PROMPT_ADDON_TITLE = "--- Instrucciones adicionales (plantilla / editor) ---"


def normalize_structure_preset(raw: str | None) -> str:
    s = (raw or "").strip().lower()
    if s == "four_act":
        return "four_act"
    return "default_five_blocks"


def fragment_plan(structure_preset: str) -> list[tuple[str, str]]:
    sp = normalize_structure_preset(structure_preset)
    return list(FRAGMENT_PLANS.get(sp, FRAGMENT_PLANS["default_five_blocks"]))


def default_minute_weights(structure_preset: str) -> list[float]:
    sp = normalize_structure_preset(structure_preset)
    if sp == "four_act":
        return list(DEFAULT_MINUTE_WEIGHTS_FOUR_ACT)
    return list(DEFAULT_MINUTE_WEIGHTS_FIVE_BLOCKS)


def normalized_minute_weights(structure_preset: str, params_json: dict[str, Any]) -> list[float]:
    """
    Orden de precedencia:
    1) `fragment_minute_weights` manual (misma longitud que fragmentos).
    2) `narrative_preset` (solo 4 actos): Finanzas, Entretenimiento, Tutorial, Ventas.
    3) Defectos por estructura.
    """
    plan = fragment_plan(structure_preset)
    n = len(plan)
    raw = params_json.get("fragment_minute_weights")
    if isinstance(raw, list) and len(raw) == n:
        try:
            w = [max(0.0, float(x)) for x in raw]
        except (TypeError, ValueError):
            w = []
        if w and sum(w) > 0:
            s = sum(w)
            return [x / s for x in w]

    sp_norm = normalize_structure_preset(structure_preset)
    if sp_norm == "four_act" and n == 4:
        pid = str(params_json.get("narrative_preset") or "").strip().lower()
        pw = weights_for_narrative_preset(pid)
        if pw and len(pw) == n:
            return pw

    return default_minute_weights(structure_preset)


def minutes_for_sequential_fragment(
    *,
    pipeline_minutes: float,
    fragment_index: int,
    structure_preset: str,
    params_json: dict[str, Any],
) -> float:
    """Minutos objetivo del fragmento `fragment_index` según pesos (proporcional al tiempo total del pipeline)."""
    pm = max(1.0, float(pipeline_minutes))
    weights = normalized_minute_weights(structure_preset, params_json)
    if fragment_index < 0 or fragment_index >= len(weights):
        raise IndexError("Índice de fragmento fuera de rango para pesos")
    m = pm * weights[fragment_index]
    return max(0.5, m)


def state_path(work_dir: Path) -> Path:
    return work_dir / "pipeline" / "script_fragmentation.json"


def chunks_dir(work_dir: Path) -> Path:
    return work_dir / "pipeline" / "script_chunks"


def outline_path(work_dir: Path) -> Path:
    return work_dir / "pipeline" / "script_outline.txt"


def default_steps(structure_preset: str) -> list[dict[str, Any]]:
    plan = fragment_plan(structure_preset)
    return [
        {
            "id": fid,
            "label": label,
            "status": "pending",
        }
        for fid, label in plan
    ]


def load_state(work_dir: Path) -> dict[str, Any] | None:
    p = state_path(work_dir)
    if not p.is_file():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else None
    except Exception:
        return None


def save_state(work_dir: Path, state: dict[str, Any]) -> None:
    p = state_path(work_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def init_state(work_dir: Path, structure_preset: str) -> dict[str, Any]:
    sp = normalize_structure_preset(structure_preset)
    st = {
        "version": 1,
        "structure_preset": sp,
        "steps": default_steps(sp),
        "outline_text": "",
    }
    save_state(work_dir, st)
    return st


def ensure_state_matches_template(work_dir: Path, structure_preset: str) -> dict[str, Any]:
    """Si no hay estado o la estructura cambió, reinicia el progreso."""
    sp = normalize_structure_preset(structure_preset)
    cur = load_state(work_dir)
    if cur is None or cur.get("structure_preset") != sp:
        return init_state(work_dir, sp)
    return cur


def reset_fragmentation_artifacts(work_dir: Path) -> None:
    try:
        state_path(work_dir).unlink(missing_ok=True)
    except OSError:
        pass
    d = chunks_dir(work_dir)
    if d.is_dir():
        for ch in d.glob("*.txt"):
            try:
                ch.unlink()
            except OSError:
                pass
    try:
        outline_path(work_dir).unlink(missing_ok=True)
    except OSError:
        pass


def chunk_file(work_dir: Path, index: int) -> Path:
    return chunks_dir(work_dir) / f"{index:02d}.txt"


def extract_outline_and_script_body(full_text: str) -> tuple[str, str]:
    """
    Separa OUTLINE del cuerpo GUIÓN cuando vienen en una misma respuesta (fragmento 0).
    """
    t = (full_text or "").strip()
    if not t:
        return "", ""
    m = re.search(r"(?im)^\s*GUI[ÓO]N\s*$", t)
    if m:
        outline = t[: m.start()].strip()
        body = t[m.end() :].strip()
        return outline, body
    m2 = re.search(r"(?im)^\s*\[CATEGORIA\s*:", t)
    if m2:
        outline = t[: m2.start()].strip()
        body = t[m2.start() :].strip()
        return outline, body
    return "", t


FIN_MARKER_RE = re.compile(r"<<<\s*FIN_FRAGMENTO(?:_\d+)?\s*>>>")


def strip_fin_marker(text: str) -> str:
    return FIN_MARKER_RE.sub("", text or "").strip()


def assemble_guion(work_dir: Path, state: dict[str, Any]) -> str:
    parts: list[str] = []
    ot = str(state.get("outline_text") or "").strip()
    if ot:
        parts.append(ot)
    steps = state.get("steps") or []
    if isinstance(steps, list):
        for i in range(len(steps)):
            p = chunk_file(work_dir, i)
            if p.is_file() and p.stat().st_size > 0:
                parts.append(p.read_text(encoding="utf-8").strip())
    return "\n\n---\n\n".join(x for x in parts if x)


def default_fragment_index_to_generate(state: dict[str, Any]) -> int | None:
    """Primer paso aún sin generar (`pending`). Para regenerar un fragmento ya escrito, hay que pasar índice explícito."""
    steps = state.get("steps") or []
    if not isinstance(steps, list) or not steps:
        return None
    for i, s in enumerate(steps):
        if isinstance(s, dict) and s.get("status") == "pending":
            return i
    return None


def set_step_status(state: dict[str, Any], index: int, status: FragmentStatus) -> None:
    steps = state.get("steps")
    if not isinstance(steps, list) or index < 0 or index >= len(steps):
        raise IndexError("fragment index out of range")
    step = steps[index]
    if not isinstance(step, dict):
        raise ValueError("invalid step")
    step["status"] = status


def apply_fragment_review(work_dir: Path, index: int, *, complete: bool) -> dict[str, Any]:
    """
    complete=True → marca el paso como revisado (done) si hay chunk en disco.
    complete=False → vuelve a estado intermedio (generated si existe archivo).
    """
    st = load_state(work_dir)
    if not st:
        raise FileNotFoundError("No hay estado de fragmentación; ejecuta Script Writer al menos una vez.")
    steps = st.get("steps")
    if not isinstance(steps, list) or index < 0 or index >= len(steps):
        raise IndexError("Índice de fragmento inválido.")
    step = steps[index]
    if not isinstance(step, dict):
        raise ValueError("Estado de fragmentación corrupto.")
    ch = chunk_file(work_dir, index)
    has_ch = ch.is_file() and ch.stat().st_size > 0
    if complete:
        step["status"] = "done" if has_ch else "pending"
    else:
        step["status"] = "generated" if has_ch else "pending"
    save_state(work_dir, st)
    return st


@dataclass(frozen=True)
class FragmentLLMAddon:
    """Texto user adicional para una pasada de fragmento."""

    index: int
    total: int
    label: str
    outline_text: str
    prior_tail: str
    is_first: bool
    segment_minutes: float
    target_narrable_words: int
    total_pipeline_minutes: float
    fragment_labels: tuple[str, ...] = ()  # plan de fragmentación (p. ej. 4 actos / 5 bloques)


def _outline_shape_override_first(req: FragmentLLMAddon) -> str:
    if not req.fragment_labels:
        return ""
    lines = "\n".join(f"  {i + 1}. {lbl}" for i, lbl in enumerate(req.fragment_labels))
    return (
        "\n--- Forma del OUTLINE (prioridad sobre el prompt maestro) ---\n"
        "La plantilla del Catálogo Prompt puede pedir «cinco secciones» o «tres pilares» en el GUIÓN completo; "
        "en **esta sesión** manda la fragmentación del pipeline.\n"
        f"Tu **OUTLINE** debe repartir **todo el vídeo** en exactamente **{len(req.fragment_labels)}** partes "
        "con tiempos orientativos, una por cada línea siguiente (no añadas una Introducción extra ni tres pilares "
        "como secciones OUTLINE separadas si con eso pasas de ese número):\n"
        f"{lines}\n"
        "Si hay cuatro partes, los «tres pilares» van **dentro** de la parte de desarrollo en el OUTLINE, no como tres bloques del índice.\n"
    )


def _volume_budget_lines(req: FragmentLLMAddon) -> str:
    pm = req.total_pipeline_minutes
    sm = req.segment_minutes
    tw = req.target_narrable_words
    base = (
        "--- Cuota de volumen (orientativa; prioriza calidad y coherencia, no relleno) ---\n"
        f"- Duración total del vídeo en el pipeline: ~{pm:.1f} min (repartidos en {req.total} fragmentos).\n"
        f"- **Este fragmento** «{req.label}»: ~{sm:.1f} min de voz en off → "
        f"objetivo **~{tw} palabras narrables** en el texto hablado de este bloque"
    )
    if req.is_first:
        return (
            base
            + ".\n- El bloque 1) OUTLINE completo **no cuenta** hacia esas ~"
            + str(tw)
            + " palabras; la cuota aplica al GUIÓN del bloque actual en 2).\n"
        )
    return base + ".\n"


def build_fragment_user_addon(req: FragmentLLMAddon) -> str:
    n = req.total
    i = req.index
    marker = f"<<< FIN_FRAGMENTO_{i} >>>"
    vol = _volume_budget_lines(req)
    if req.is_first:
        shape = _outline_shape_override_first(req)
        return (
            _PROMPT_ADDON_TITLE
            + "\n\n"
            + "--- Fragmentación secuencial ---\n"
            + f"Estructura elegida: {n} partes numeradas de 0 a {n - 1}.\n"
            + vol
            + shape
            + "\n"
            + f"En esta respuesta debes entregar:\n"
            + "1) Un OUTLINE completo del vídeo (todas las partes), con tiempos orientativos por bloque.\n"
            + "2) El GUIÓN escrito **solo** para el bloque actual:\n"
            + f"   «{req.label}» (fragmento índice {i}).\n"
            + "No escribas todavía los bloques siguientes (índices mayores).\n"
            + "Usa el formato maestro (OUTLINE / GUIÓN, [CATEGORIA: …], [B-ROLL: …]).\n"
            + f"Cierra la respuesta con la línea exacta: {marker}\n"
        )
    tail = (req.prior_tail or "").strip()
    tail = tail[-3500:] if len(tail) > 3500 else tail
    outline = (req.outline_text or "").strip()
    return (
        _PROMPT_ADDON_TITLE
        + "\n\n"
        + "--- Fragmentación secuencial (continuación) ---\n"
        + vol
        + "\n"
        + "Ya existe un OUTLINE aprobado para esta sesión. **No lo reescribas completo** en esta respuesta.\n"
        + "Si necesitas referencia, usa solo el resumen siguiente:\n\n"
        + "--- OUTLINE (referencia, no repetir salvo un puente de una frase) ---\n"
        + (outline[:12000] if outline else "(vacío)")
        + "\n\n"
        + "--- Último contexto del GUIÓN ya generado (continuidad de tono) ---\n"
        + (tail if tail else "(vacío)")
        + "\n\n"
        + f"Ahora escribe **solo** el bloque «{req.label}» (fragmento índice {i} de {n}).\n"
        + "No repitas bloques anteriores ni adelantes los siguientes.\n"
        + f"Cierra con la línea exacta: {marker}\n"
    )
