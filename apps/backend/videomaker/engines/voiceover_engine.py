from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


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


def _tone_from_credibility(cr: dict[str, Any]) -> str:
    avoid_total = bool(cr.get("avoid_totalizing_claims", False))
    include_ctr = bool(cr.get("include_counterarguments", False))
    if avoid_total and include_ctr:
        return "grounded, nuanced, anti-ragebait"
    if avoid_total:
        return "measured, careful, anti-overclaim"
    return "confident"


def _infer_archetype(prompt_artifact: dict[str, Any]) -> str:
    de = str(prompt_artifact.get("dominant_emotion") or "").lower()
    if "anxiety" in de or "ansiedad" in de:
        return "empathetic_confessor"
    if "rage" in de or "rabia" in de or "anger" in de:
        return "controlled_prosecutor"
    if "clarity" in de or "claridad" in de:
        return "calm_mentor"
    return "human_analyst"


def _pause_profile(energy_curve: list[str], visual_density: dict[str, Any]) -> dict[str, Any]:
    hook = str(visual_density.get("hook") or "high")
    reveal = str(visual_density.get("emotional_reveal") or "low + intimate")
    base = 1.8
    if "high" in hook.lower():
        base = 1.2
    if "intimate" in reveal.lower() or "low" in reveal.lower():
        end = 2.6
    else:
        end = 2.0
    # If there is an explicit relief beat, encourage a slightly longer pause there.
    has_relief = any("relief" in b.lower() for b in energy_curve)
    return {"paragraph_pause_s": round(end if has_relief else base, 2)}


def _script_for_tts(script_text: str, *, energy_curve: list[str], visual_density: dict[str, Any]) -> str:
    """
    We can't control XTTS prosody directly here; we exploit paragraph boundaries:
    `build_narration_wav` adds real silence between paragraphs.
    """
    txt = (script_text or "").strip()
    if not txt:
        return ""
    paras = [p.strip() for p in txt.split("\n\n") if p.strip()]
    if not paras:
        return txt
    out: list[str] = []
    # Insert an "exhale pocket" roughly near the end if the density suggests intimacy.
    reveal = str(visual_density.get("emotional_reveal") or "")
    wants_intimate = "intimate" in reveal.lower() or "low" in reveal.lower()
    reliefish = any("relief" in b.lower() for b in energy_curve)
    exhale_idx = max(0, min(len(paras) - 1, int(round(len(paras) * 0.78))))
    for i, p in enumerate(paras):
        out.append(p)
        if (wants_intimate or reliefish) and i == exhale_idx:
            # Extra paragraph break = longer silence between blocks.
            out.append("...")
    return "\n\n".join(out).strip()


def build_voiceover_plan(*, prompt_artifact: dict[str, Any], minutes: float, script_text: str) -> dict[str, Any]:
    sp = prompt_artifact if isinstance(prompt_artifact, dict) else {}
    ec = sp.get("energy_curve") if isinstance(sp.get("energy_curve"), list) else []
    vd = sp.get("visual_density") if isinstance(sp.get("visual_density"), dict) else {}
    cr = sp.get("credibility_rules") if isinstance(sp.get("credibility_rules"), dict) else {}
    arc = sp.get("emotional_arc") if isinstance(sp.get("emotional_arc"), dict) else {}

    energy_curve = [str(x).strip() for x in ec if str(x).strip()][:12]
    trust_level = _tone_from_credibility(cr)
    archetype = _infer_archetype(sp)
    pause_profile = _pause_profile(energy_curve, vd)

    return {
        "version": 1,
        "generated_at": _now_iso(),
        "source": "voiceover_engine",
        "spine": {
            "emotional_arc": arc,
            "energy_curve": energy_curve,
            "visual_density": vd,
            "credibility_rules": cr,
        },
        "plan": {
            "narration_archetype": archetype,
            "trust_level": trust_level,
            "emotional_pacing": {
                "start": str(arc.get("start") or "").strip(),
                "mid": str(arc.get("mid") or "").strip(),
                "end": str(arc.get("end") or "").strip(),
            }
            if isinstance(arc, dict)
            else {},
            "tension_intensity": [b for b in energy_curve if any(x in b.lower() for x in ("tension", "rage", "spike"))],
            "tts_controls": pause_profile,
            "script_for_tts_preview_chars": len((script_text or "").strip()),
        },
        "inputs": {"minutes": float(minutes or 0) if minutes else None},
    }


def run_voiceover_engine_step(work_dir: Path, *, minutes: float = 10.0) -> Path:
    pj = work_dir / "pipeline" / "prompt.json"
    sp = _read_json(pj)
    script_path = work_dir / "pipeline" / "script.txt"
    if not script_path.is_file():
        alt = work_dir / "guion.txt"
        script_path = alt if alt.is_file() else script_path
    if not script_path.is_file():
        raise RuntimeError("Falta guion (guion.txt / pipeline/script.txt) para Voiceover Engine.")
    script_text = script_path.read_text(encoding="utf-8")

    ec = sp.get("energy_curve") if isinstance(sp.get("energy_curve"), list) else []
    vd = sp.get("visual_density") if isinstance(sp.get("visual_density"), dict) else {}
    script_for_tts = _script_for_tts(script_text, energy_curve=[str(x) for x in ec], visual_density=vd)

    out_dir = work_dir / "pipeline"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "script_for_tts.txt").write_text(script_for_tts, encoding="utf-8")

    blob = build_voiceover_plan(prompt_artifact=sp, minutes=minutes, script_text=script_for_tts)
    out = out_dir / "voiceover_plan.json"
    out.write_text(json.dumps(blob, ensure_ascii=False, indent=2), encoding="utf-8")
    return out

