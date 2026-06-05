"""Heuristic quality lint for generated scripts (no LLM).

Post-hoc checks for human editors in the UI only — never fed back into Script Writer prompts.
Measures template drift: meta-hooks, formulaic reversals, symbol stacking, cadence heuristics, B-roll tags.
Persists to `pipeline/script_quality.json` for the Editorial Analyzer step panel.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from videomaker.core.script_bundle import build_script_bundle
from videomaker.core.script_clean import (
    count_narrable_words,
    estimated_narrable_minutes,
    narrable_plain_text,
    narrable_wpm,
    script_text_for_metrics,
)
QUALITY_FILENAME = "script_quality.json"

Severity = Literal["info", "warn", "error"]


@dataclass
class LintFinding:
    id: str
    severity: Severity
    title: str
    detail: str
    count: int = 0
    examples: list[str] = field(default_factory=list)


@dataclass
class ScriptLintReport:
    ok: bool
    score: int
    metrics: dict[str, Any]
    findings: list[LintFinding]
    narrable_word_count: int
    estimated_minutes: float
    target_minutes: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "score": self.score,
            "metrics": self.metrics,
            "findings": [asdict(f) for f in self.findings],
            "narrable_word_count": self.narrable_word_count,
            "estimated_minutes": self.estimated_minutes,
            "target_minutes": self.target_minutes,
        }


_META_HOOK_RES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)\bhere'?s the thing\b"), "here's the thing"),
    (re.compile(r"(?i)\bnobody tells you\b"), "nobody tells you"),
    (re.compile(r"(?i)\bwhat no one tells you\b"), "what no one tells you"),
    (re.compile(r"(?i)\blo que nadie te cuenta\b"), "lo que nadie te cuenta"),
    (re.compile(r"(?i)\blo que nadie te dice\b"), "lo que nadie te dice"),
    (re.compile(r"(?i)\by sé lo que estás pensando\b"), "y sé lo que estás pensando"),
    (re.compile(r"(?i)\baquí va la cosa\b"), "aquí va la cosa"),
    (re.compile(r"(?i)\bthe truth is\b"), "the truth is"),
    (re.compile(r"(?i)\bla verdad es\b"), "la verdad es"),
    (re.compile(r"(?i)\bdemuestra que\b"), "demuestra que"),
    (re.compile(r"(?i)\bproves that\b"), "proves that"),
    (re.compile(r"(?i)\bthey want you to\b"), "they want you to"),
    (re.compile(r"(?i)\bellos quieren que\b"), "ellos quieren que"),
]

_FORMULAIC_REVERSAL_RES: list[re.Pattern[str]] = [
    re.compile(
        r"(?is)\b(?:you|we|everyone|people)\s+think[s]?\b.{0,140}?\b(?:but|actually|yet)\b"
    ),
    re.compile(r"(?is)\b(?:crees|piensas)\s+que\b.{0,140}?\b(?:pero|en\s+realidad)\b"),
    re.compile(r"(?i)\byou\s+think\b.{0,80}?\bbut\s+actually\b"),
    re.compile(r"(?i)\bcrees\s+que\b.{0,80}?\bpero\s+(?:en\s+realidad|lo\s+cierto)\b"),
]

_TRAILER_MOOD_RES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)\bin the shadows\b"), "in the shadows"),
    (re.compile(r"(?i)\ben las sombras\b"), "en las sombras"),
    (re.compile(r"(?i)\bweight of\b"), "weight of"),
    (re.compile(r"(?i)\bel peso de\b"), "el peso de"),
    (re.compile(r"(?i)\baesthetic\b"), "aesthetic"),
    (re.compile(r"(?i)\bestetiz"), "estetiz"),
]

_BROLL_TAG = re.compile(r"\[B-ROLL\s*:", re.IGNORECASE)
_CATEGORY_TAG = re.compile(r"(?im)^\[CATEGORIA:\s*([^\]]+)\]\s*$")

_DENSE_CUE = re.compile(
    r"(?i)\b(?:percent|%|incentive|incentivo|mechanism|mecanismo|data|datos|"
    r"study|estudio|according to|según|therefore|por tanto|therefore)\b"
)


def _read_target_minutes(work_dir: Path | None) -> float | None:
    if work_dir is None:
        return None
    p = work_dir / "pipeline" / "prompt.json"
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    from videomaker.pipeline.duration_policy import clamp_pipeline_minutes

    for key in ("minutes", "target_minutes"):
        v = data.get(key)
        if v is not None:
            try:
                m = float(v)
                if m > 0:
                    return clamp_pipeline_minutes(m)
            except (TypeError, ValueError):
                continue
    return None


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?…])\s+|\n+", text.strip())
    return [p.strip() for p in parts if len(p.strip()) > 12]


def _count_patterns(text: str, patterns: list[tuple[re.Pattern[str], str]]) -> tuple[int, list[str]]:
    total = 0
    examples: list[str] = []
    for rx, label in patterns:
        for m in rx.finditer(text):
            total += 1
            if len(examples) < 4:
                snippet = text[max(0, m.start() - 20) : m.end() + 40].replace("\n", " ")
                examples.append(f"{label}: …{snippet.strip()[:90]}…")
    return total, examples


def _count_regex_list(text: str, patterns: list[re.Pattern[str]]) -> tuple[int, list[str]]:
    total = 0
    examples: list[str] = []
    for rx in patterns:
        for m in rx.finditer(text):
            total += 1
            if len(examples) < 4:
                snippet = text[max(0, m.start() - 15) : m.end() + 55].replace("\n", " ")
                examples.append(f"…{snippet.strip()[:100]}…")
    return total, examples


def _broll_stats(raw: str) -> dict[str, Any]:
    tags = list(_BROLL_TAG.finditer(raw))
    narrable = narrable_plain_text(raw)
    sents = _sentences(narrable)
    n_sents = max(len(sents), 1)
    descriptions = [m.group(0) for m in re.finditer(r"\[B-ROLL\s*:\s*([^\]]*)", raw, re.I)]
    return {
        "broll_count": len(tags),
        "sentence_count": len(sents),
        "broll_per_10_sentences": round(len(tags) / n_sents * 10, 2),
        "broll_descriptions_sample": descriptions[:3],
    }


def _dense_without_release(narrable: str) -> tuple[int, list[str]]:
    """Paragraphs with ≥2 dense-cue sentences and no short mundane anchor in the next 2 sentences."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", narrable) if p.strip()]
    hits = 0
    examples: list[str] = []
    for para in paras:
        sents = _sentences(para)
        dense_idxs = [i for i, s in enumerate(sents) if _DENSE_CUE.search(s)]
        if len(dense_idxs) < 2:
            continue
        tail = " ".join(sents[dense_idxs[-1] + 1 : dense_idxs[-1] + 3]).lower()
        mundane = any(
            w in tail
            for w in (
                "phone",
                "móvil",
                "mobile",
                "app",
                "excel",
                "receipt",
                "ticket",
                "notification",
                "notificación",
                "kitchen",
                "cocina",
                "thumb",
                "pulgar",
            )
        )
        if not mundane:
            hits += 1
            if len(examples) < 3:
                examples.append(para[:160].replace("\n", " ") + "…")
    return hits, examples


def _repeated_broll_motifs(raw: str) -> tuple[int, list[str]]:
    words: list[str] = []
    for m in re.finditer(r"\[B-ROLL\s*:\s*([^\]]*)", raw, re.I):
        chunk = re.sub(r"[^a-záéíóúñü0-9\s]", " ", m.group(1).lower())
        words.extend(w for w in chunk.split() if len(w) > 4)
    if not words:
        return 0, []
    from collections import Counter

    common = Counter(words).most_common(5)
    repeats = [(w, c) for w, c in common if c >= 4]
    if not repeats:
        return 0, []
    examples = [f"«{w}» ×{c} en descripciones B-roll" for w, c in repeats[:3]]
    return len(repeats), examples


def lint_script(
    raw: str,
    *,
    target_minutes: float | None = None,
    work_dir: Path | None = None,
) -> ScriptLintReport:
    raw = (raw or "").replace("\r\n", "\n").strip()
    if not raw:
        return ScriptLintReport(
            ok=True,
            score=100,
            metrics={},
            findings=[],
            narrable_word_count=0,
            estimated_minutes=0.0,
            target_minutes=target_minutes,
        )

    tm = target_minutes
    if tm is None and work_dir is not None:
        tm = _read_target_minutes(work_dir)

    metrics_raw, length_source = script_text_for_metrics(work_dir, raw)
    narrable = narrable_plain_text(metrics_raw)
    word_count = count_narrable_words(metrics_raw)
    est_min = estimated_narrable_minutes(word_count)

    wpm = int(narrable_wpm())
    findings: list[LintFinding] = []
    metrics: dict[str, Any] = {
        "length_source": length_source,
        "words_per_minute": wpm,
        "category_blocks": len(_CATEGORY_TAG.findall(metrics_raw)),
        **_broll_stats(metrics_raw),
    }

    meta_n, meta_ex = _count_patterns(narrable, _META_HOOK_RES)
    metrics["meta_hook_count"] = meta_n
    if meta_n >= 2:
        findings.append(
            LintFinding(
                id="meta_hooks",
                severity="warn",
                title="Meta-hooks repetidos",
                detail="Muletillas tipo «lo que nadie te cuenta» o «the truth is» erosionan credibilidad.",
                count=meta_n,
                examples=meta_ex,
            )
        )
    elif meta_n == 1:
        findings.append(
            LintFinding(
                id="meta_hooks",
                severity="info",
                title="Meta-hook detectado",
                detail="Una aparición puede estar bien; evita repetir en el resto del guion.",
                count=1,
                examples=meta_ex,
            )
        )

    rev_n, rev_ex = _count_regex_list(narrable, _FORMULAIC_REVERSAL_RES)
    metrics["formulaic_reversal_count"] = rev_n
    rev_per_min = rev_n / est_min if est_min > 0.15 else float(rev_n)
    metrics["reversals_per_minute"] = round(rev_per_min, 2)
    if rev_n >= 3 or rev_per_min >= 1.2:
        findings.append(
            LintFinding(
                id="formulaic_reversals",
                severity="warn",
                title="Reversiones retóricas en exceso",
                detail="Patrón «crees que X… pero Y» suena a plantilla de retención. Máx. ~1 por vídeo.",
                count=rev_n,
                examples=rev_ex,
            )
        )
    elif rev_n == 2:
        findings.append(
            LintFinding(
                id="formulaic_reversals",
                severity="info",
                title="Dos reversiones detectadas",
                detail="Vigila que no se conviertan en tic cada pocos párrafos.",
                count=2,
                examples=rev_ex,
            )
        )

    trailer_n, trailer_ex = _count_patterns(narrable, _TRAILER_MOOD_RES)
    metrics["trailer_mood_hits"] = trailer_n
    if trailer_n >= 3:
        findings.append(
            LintFinding(
                id="trailer_mood",
                severity="info",
                title="Tono tráiler / melancólico",
                detail="Varias frases con peso estético; equilibra con detalle mundano (pantalla, ticket, gesto).",
                count=trailer_n,
                examples=trailer_ex,
            )
        )

    dense_hits, dense_ex = _dense_without_release(narrable)
    metrics["dense_blocks_without_release"] = dense_hits
    if dense_hits >= 2:
        findings.append(
            LintFinding(
                id="dense_pacing",
                severity="warn",
                title="Bloques densos sin alivio",
                detail="Tras datos/mecanismos falta escena mundana o momento humano antes del siguiente bloque denso.",
                count=dense_hits,
                examples=dense_ex,
            )
        )

    motif_n, motif_ex = _repeated_broll_motifs(raw)
    metrics["repeated_broll_motifs"] = motif_n
    if motif_n >= 1:
        findings.append(
            LintFinding(
                id="broll_motif_repeat",
                severity="info",
                title="Motivos visuales repetidos en B-roll",
                detail="El mismo objeto/palabra en muchos B-roll puede sentirse sobre-simbólico.",
                count=motif_n,
                examples=motif_ex,
            )
        )

    broll_count = int(metrics.get("broll_count") or 0)
    broll_ratio = float(metrics.get("broll_per_10_sentences") or 0)
    if broll_count == 0 and "[B-ROLL" in raw.upper():
        findings.append(
            LintFinding(
                id="broll_parse",
                severity="info",
                title="Etiquetas B-roll no estándar",
                detail="Usa exactamente [B-ROLL: descripción] para que el pipeline las detecte.",
                count=0,
            )
        )
    elif broll_ratio > 8:
        findings.append(
            LintFinding(
                id="broll_density",
                severity="info",
                title="Muchos cortes B-roll",
                detail="Más de ~8 etiquetas por 10 frases narrables; revisa si no suena a montaje frenético.",
                count=broll_count,
            )
        )

    if tm and est_min > 0:
        metrics["target_minutes"] = tm
        ratio = est_min / tm
        metrics["length_ratio_vs_target"] = round(ratio, 2)
        if ratio < 0.75:
            findings.append(
                LintFinding(
                    id="length_short",
                    severity="info",
                    title="Guion corto vs objetivo",
                    detail=f"~{est_min:.1f} min narrables vs ~{tm:.1f} min objetivo.",
                    count=0,
                )
            )
        elif ratio > 1.35:
            src_note = {
                "fragments": " (fragmentos Script Writer)",
                "guion_revised": " (guion reescrito, p. ej. tras Pacing Pass)",
                "guion_file": " (texto hablado, sin outline/plan)",
            }.get(length_source, "")
            findings.append(
                LintFinding(
                    id="length_long",
                    severity="info",
                    title="Guion largo vs objetivo",
                    detail=(
                        f"~{est_min:.1f} min narrables{src_note} vs ~{tm:.1f} min objetivo del pipeline. "
                        f"{word_count:,} palabras a ~{wpm} p/min."
                    ),
                    count=0,
                )
            )

    score = 100
    for f in findings:
        if f.severity == "warn":
            score -= min(18, 8 + f.count * 2)
        elif f.severity == "info":
            score -= min(8, 3 + f.count)
    score = max(0, min(100, score))
    ok = not any(f.severity == "warn" for f in findings)

    return ScriptLintReport(
        ok=ok,
        score=score,
        metrics=metrics,
        findings=findings,
        narrable_word_count=word_count,
        estimated_minutes=round(est_min, 2),
        target_minutes=tm,
    )


def quality_path(work_dir: Path) -> Path:
    return work_dir / "pipeline" / QUALITY_FILENAME


def persist_script_quality(
    work_dir: Path,
    raw: str,
    *,
    target_minutes: float | None = None,
) -> Path | None:
    """Write `pipeline/script_quality.json`; returns path or None if empty script."""
    raw = (raw or "").strip()
    if not raw:
        return None
    report = lint_script(raw, target_minutes=target_minutes, work_dir=work_dir)
    d = work_dir / "pipeline"
    d.mkdir(parents=True, exist_ok=True)
    path = quality_path(work_dir)
    payload = report.to_dict()
    payload["version"] = 1
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_script_quality(work_dir: Path) -> dict[str, Any] | None:
    path = quality_path(work_dir)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None
