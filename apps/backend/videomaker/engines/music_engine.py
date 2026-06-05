from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from videomaker.scene_editor.audio_timeline import (
    build_audio_timeline,
    write_audio_timeline_artifact,
)


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


def _energy_to_intensity(label: str) -> int:
    t = (label or "").strip().lower()
    if not t:
        return 55
    if "hook" in t or "tension" in t:
        return 82
    if "rage" in t or "spike" in t:
        return 92
    if "reveal" in t or "data" in t:
        return 72
    if "relief" in t or "validation" in t:
        return 48
    if "empower" in t or "agency" in t:
        return 68
    return 55


def _is_relief_beat(label: str) -> bool:
    t = (label or "").lower()
    return any(x in t for x in ("relief", "validation", "intimate"))


def _beats_from_audio_timeline(
    timeline: dict[str, Any],
    energy_curve: list[str],
) -> list[dict[str, Any]]:
    """Mapea curva de energía a huecos y bloques reales (start_s / end_s)."""
    total = float(timeline.get("total_duration_s") or 0)
    events = [e for e in (timeline.get("events") or []) if isinstance(e, dict)]
    chunks = [e for e in events if e.get("kind") == "chunk"]
    gaps = [e for e in events if e.get("kind") == "gap"]
    labels = [str(x).strip() for x in energy_curve if str(x).strip()]
    if not labels:
        labels = ["hook_tension", "explanation", "relief_empowerment"]

    beats: list[dict[str, Any]] = []
    for i, label in enumerate(labels):
        relief = _is_relief_beat(label)
        ev: dict[str, Any] | None = None
        if relief and gaps:
            ev = gaps[i % len(gaps)]
        elif chunks:
            pos = (i + 0.5) / max(1, len(labels))
            ci = min(int(pos * len(chunks)), len(chunks) - 1)
            ev = chunks[ci]
        if not ev:
            continue
        start_s = float(ev.get("start_s") or 0)
        end_s = float(ev.get("end_s") or start_s)
        intensity = 38 if relief else _energy_to_intensity(label)
        beats.append(
            {
                "beat": label,
                "start_s": round(start_s, 3),
                "end_s": round(end_s, 3),
                "from_pct": int(round(100 * start_s / total)) if total > 0 else 0,
                "to_pct": int(round(100 * end_s / total)) if total > 0 else 100,
                "intensity": intensity,
                "anchor": ev.get("kind"),
                "chunk_id": ev.get("chunk_id"),
            }
        )
    return beats


def build_music_plan(*, prompt_artifact: dict[str, Any], minutes: float) -> dict[str, Any]:
    sp = prompt_artifact if isinstance(prompt_artifact, dict) else {}
    ec = sp.get("energy_curve") if isinstance(sp.get("energy_curve"), list) else []
    arc = sp.get("emotional_arc") if isinstance(sp.get("emotional_arc"), dict) else {}
    vsa = sp.get("viewer_state_after_video") if isinstance(sp.get("viewer_state_after_video"), dict) else {}
    vd = sp.get("visual_density") if isinstance(sp.get("visual_density"), dict) else {}

    energy_curve = [str(x).strip() for x in ec if str(x).strip()][:12]
    beats_pct = []
    if energy_curve:
        step = 100 / max(1, len(energy_curve))
        for i, b in enumerate(energy_curve):
            beats_pct.append(
                {
                    "beat": b,
                    "from_pct": int(round(i * step)),
                    "to_pct": int(round((i + 1) * step)),
                    "intensity": _energy_to_intensity(b),
                }
            )
    else:
        beats_pct = [
            {"beat": "hook_tension", "from_pct": 0, "to_pct": 18, "intensity": 82},
            {"beat": "explanation", "from_pct": 18, "to_pct": 78, "intensity": 60},
            {"beat": "relief_empowerment", "from_pct": 78, "to_pct": 100, "intensity": 52},
        ]

    palette = {
        "hook": "tense, minimal, heartbeat or low pulse",
        "middle": "steady, understated, low-mid energy bed",
        "ending": "warm lift, hopeful, controlled triumph",
    }
    if isinstance(vd, dict) and str(vd.get("emotional_reveal") or "").lower().find("intimate") >= 0:
        palette["ending"] = "intimate resolve, airy, human, no bombast"

    end_targets = []
    for k, v in vsa.items():
        kk = str(k).strip()
        if not kk:
            continue
        try:
            n = int(float(v))  # type: ignore[arg-type]
        except Exception:
            continue
        n = max(0, min(100, n))
        end_targets.append((kk, n))
    end_targets.sort(key=lambda x: x[1], reverse=True)

    rage = sum(1 for b in energy_curve if "rage" in b.lower())
    hope = sum(1 for b in energy_curve if any(x in b.lower() for x in ("relief", "empower", "validation")))
    rage_hope_ratio = round(rage / max(1, hope), 3)

    pacing_shifts = []
    if isinstance(vd, dict) and vd:
        for k, v in vd.items():
            kk = str(k).strip()
            vv = str(v).strip()
            if kk and vv:
                pacing_shifts.append({"segment": kk, "visual_density": vv})

    return {
        "version": 1,
        "generated_at": _now_iso(),
        "source": "music_engine",
        "spine": {
            "energy_curve": energy_curve,
            "emotional_arc": {
                "start": str(arc.get("start") or "").strip() or None,
                "mid": str(arc.get("mid") or "").strip() or None,
                "end": str(arc.get("end") or "").strip() or None,
            }
            if isinstance(arc, dict)
            else {},
            "viewer_state_after_video": {k: n for k, n in end_targets[:8]},
        },
        "plan": {
            "palette": palette,
            "beats": beats_pct,
            "emotional_transition_map": {
                "start": str(arc.get("start") or "").strip() if isinstance(arc, dict) else "",
                "mid": str(arc.get("mid") or "").strip() if isinstance(arc, dict) else "",
                "end": str(arc.get("end") or "").strip() if isinstance(arc, dict) else "",
            },
            "rage_hope_ratio": rage_hope_ratio,
            "pacing_shifts": pacing_shifts,
            "notes": [
                "Use energy spikes for transitions/cuts; carve silence/air on relief/intimate moments.",
                "Ending must land on the target after-state (clarity/agency/motivation) without ragebait escalation.",
            ],
        },
        "inputs": {"minutes": float(minutes or 0) if minutes else None},
    }


def run_music_engine_step(work_dir: Path, *, minutes: float = 10.0) -> Path:
    """
    Genera ``music_plan.json`` anclado al audio real (Scene Editor + narracion.wav).
    """
    timeline = build_audio_timeline(work_dir)
    write_audio_timeline_artifact(work_dir, timeline)

    pj = work_dir / "pipeline" / "prompt.json"
    sp = _read_json(pj)
    blob = build_music_plan(prompt_artifact=sp, minutes=minutes)

    energy = blob.get("spine", {}).get("energy_curve") if isinstance(blob.get("spine"), dict) else []
    if not isinstance(energy, list):
        energy = []
    timed_beats = _beats_from_audio_timeline(timeline, energy)
    gaps = [e for e in timeline.get("events", []) if isinstance(e, dict) and e.get("kind") == "gap"]

    plan = blob.setdefault("plan", {})
    if isinstance(plan, dict):
        plan["beats"] = timed_beats or plan.get("beats")
        plan["pause_moments"] = [
            {
                "start_s": g.get("start_s"),
                "end_s": g.get("end_s"),
                "hint": "hueco entre bloques TTS — subir intensidad o silencio dramático",
            }
            for g in gaps
        ]

    blob["source"] = "music_engine+audio"
    blob["inputs"] = {
        **(blob.get("inputs") if isinstance(blob.get("inputs"), dict) else {}),
        "minutes": float(minutes or 0) if minutes else None,
        "total_duration_s": timeline.get("total_duration_s"),
        "audio_timeline": "pipeline/audio_timeline.json",
        "timing_mode": "scene_editor_audio",
    }

    out = work_dir / "pipeline" / "music_plan.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(blob, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
