from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from videomaker.core import config
from videomaker.scene_editor.audio_timeline import (
    build_audio_timeline,
    ensure_narration_wav,
    write_audio_timeline_artifact,
)
from videomaker.video.subtitles_whisper import segments_to_srt, transcribe_for_subtitles


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _density_to_number(v: str) -> int:
    t = (v or "").strip().lower()
    if not t:
        return 55
    if "high" in t or "alta" in t:
        return 85
    if "medium" in t or "media" in t:
        return 60
    if "low" in t or "baja" in t:
        return 35
    return 55


def _sections_with_absolute_times(
    sections: list[dict[str, Any]],
    total_s: float,
) -> list[dict[str, Any]]:
    if total_s <= 0:
        return sections
    out: list[dict[str, Any]] = []
    for s in sections:
        if not isinstance(s, dict):
            continue
        try:
            fp = float(s.get("from_pct", 0))
            tp = float(s.get("to_pct", 100))
        except (TypeError, ValueError):
            fp, tp = 0.0, 100.0
        row = dict(s)
        row["start_s"] = round(total_s * fp / 100.0, 3)
        row["end_s"] = round(total_s * tp / 100.0, 3)
        out.append(row)
    return out


def build_subtitles_plan(*, prompt_artifact: dict[str, Any], script_text: str, minutes: float) -> dict[str, Any]:
    sp = prompt_artifact if isinstance(prompt_artifact, dict) else {}
    ssf = sp.get("scroll_stop_factors") if isinstance(sp.get("scroll_stop_factors"), list) else []
    ec = sp.get("energy_curve") if isinstance(sp.get("energy_curve"), list) else []
    vd = sp.get("visual_density") if isinstance(sp.get("visual_density"), dict) else {}
    cr = sp.get("credibility_rules") if isinstance(sp.get("credibility_rules"), dict) else {}
    ident = sp.get("identity_transformation") if isinstance(sp.get("identity_transformation"), dict) else {}
    trig = sp.get("psychological_triggers") if isinstance(sp.get("psychological_triggers"), list) else []

    hook_density = str(vd.get("hook") or "high")
    mid_density = str(vd.get("middle_explanation") or "medium")
    reveal_density = str(vd.get("emotional_reveal") or "low + intimate")

    sections = [
        {
            "id": "hook",
            "from_pct": 0,
            "to_pct": 18,
            "density_label": hook_density,
            "subtitle_aggressiveness": _density_to_number(hook_density),
        },
        {
            "id": "middle",
            "from_pct": 18,
            "to_pct": 78,
            "density_label": mid_density,
            "subtitle_aggressiveness": _density_to_number(mid_density),
        },
        {
            "id": "reveal_end",
            "from_pct": 78,
            "to_pct": 100,
            "density_label": reveal_density,
            "subtitle_aggressiveness": _density_to_number(reveal_density),
        },
    ]

    scroll_stop = [str(x).strip() for x in ssf if str(x).strip()][:10]
    energy_curve = [str(x).strip() for x in ec if str(x).strip()][:12]
    trigger_phrases = [str(x).strip() for x in trig if str(x).strip()][:10]
    identity_phrases: list[str] = []
    if isinstance(ident, dict):
        fr = str(ident.get("from") or "").strip()
        to = str(ident.get("to") or "").strip()
        if fr and to:
            identity_phrases.append(f"de {fr} a {to}")
        elif to:
            identity_phrases.append(to)
        elif fr:
            identity_phrases.append(fr)
    pause_moments: list[dict[str, str]] = []
    for b in energy_curve:
        if any(x in b.lower() for x in ("relief", "validation", "intimate")):
            pause_moments.append({"beat": b, "hint": "brief pause / exhale"})
    credibility_rules = {}
    for k, v in cr.items():
        kk = str(k).strip()
        if not kk:
            continue
        if isinstance(v, bool):
            credibility_rules[kk] = v
        else:
            sv = str(v).strip().lower()
            if sv in ("true", "1", "yes", "y", "si", "sí"):
                credibility_rules[kk] = True
            elif sv in ("false", "0", "no", "n"):
                credibility_rules[kk] = False

    return {
        "version": 1,
        "generated_at": _now_iso(),
        "source": "subtitle_engine",
        "inputs": {
            "minutes": float(minutes or 0) if minutes else None,
            "script_chars": len((script_text or "").strip()),
        },
        "spine": {
            "scroll_stop_factors": scroll_stop,
            "energy_curve": energy_curve,
            "visual_density": {str(k): str(v) for k, v in vd.items()} if isinstance(vd, dict) else {},
            "credibility_rules": credibility_rules,
            "identity_phrases": identity_phrases,
            "trigger_phrases": trigger_phrases,
        },
        "plan": {
            "sections": sections,
            "emphasis": {
                "scroll_stop_factors": scroll_stop,
                "emotional_emphasis_words": (scroll_stop + trigger_phrases)[:16],
                "identity_phrases": identity_phrases,
                "trigger_phrases": trigger_phrases,
                "pause_moments": pause_moments,
                "rules": [
                    "Punch key words on energy spikes; soften on relief/intimate beats.",
                    "Use pattern-interrupt styling for scroll-stop factors (contrast color / pop-in / shake) but avoid ragebait framing.",
                ],
                "anti_ragebait": {
                    "avoid_totalizing_claims": bool(credibility_rules.get("avoid_totalizing_claims", False)),
                    "include_counterarguments": bool(credibility_rules.get("include_counterarguments", False)),
                },
            },
        },
    }


def run_subtitle_engine_step(work_dir: Path, *, minutes: float = 10.0) -> Path:
    """
    Plan de estilo (prompt) + alineación Whisper sobre ``narracion.wav`` real.
    """
    timeline = build_audio_timeline(work_dir)
    write_audio_timeline_artifact(work_dir, timeline)
    total_s = float(timeline.get("total_duration_s") or 0)

    gap_ms = timeline.get("chunk_gap_ms")
    wav = ensure_narration_wav(
        work_dir,
        chunk_gap_ms=int(gap_ms) if isinstance(gap_ms, (int, float)) else None,
    )

    pj = work_dir / "pipeline" / "prompt.json"
    sp = _read_json(pj)
    script_path = work_dir / "pipeline" / "script.txt"
    if not script_path.is_file():
        alt = work_dir / "guion.txt"
        script_path = alt if alt.is_file() else script_path
    if not script_path.is_file():
        raise RuntimeError("Falta guion (guion.txt / pipeline/script.txt) para Subtitle Engine.")
    script_text = script_path.read_text(encoding="utf-8")

    lang = (sp.get("lang") or sp.get("output_language") or "").strip() or None
    if isinstance(lang, str) and len(lang) > 2:
        lang = lang[:2].lower()

    word_ts = config.whisper_word_timestamps_enabled()
    alignment = transcribe_for_subtitles(
        wav,
        language=lang,
        word_timestamps=word_ts,
    )

    srt_path = work_dir / "pipeline" / "subtitles.srt"
    srt_path.parent.mkdir(parents=True, exist_ok=True)
    srt_path.write_text(segments_to_srt(alignment.get("segments") or []), encoding="utf-8")

    blob = build_subtitles_plan(prompt_artifact=sp, script_text=script_text, minutes=minutes)
    plan = blob.get("plan")
    if isinstance(plan, dict) and isinstance(plan.get("sections"), list):
        plan["sections"] = _sections_with_absolute_times(plan["sections"], total_s)

    blob["source"] = "subtitle_engine+audio"
    blob["inputs"] = {
        **(blob.get("inputs") if isinstance(blob.get("inputs"), dict) else {}),
        "audio_source": "narracion.wav",
        "total_duration_s": total_s,
        "audio_timeline": "pipeline/audio_timeline.json",
    }
    blob["alignment"] = {
        "engine": "whisper",
        "model": config.WHISPER_MODEL,
        "word_timestamps": word_ts,
        "language": alignment.get("language"),
        "segments": alignment.get("segments") or [],
        "words": alignment.get("words") or [],
        "srt_path": "pipeline/subtitles.srt",
    }

    out = work_dir / "pipeline" / "subtitles_plan.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(blob, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
