"""Plantillas del Script Writer (catálogo en Postgres)."""

from __future__ import annotations

import json
from typing import Any

from videomaker.core import db
from videomaker.llm.script_fragmentation import fragment_plan, normalize_structure_preset

CHUNKING_MODE_OUTLINE_ACT1 = "outline_act1_only"
CHUNKING_MODE_SEQUENTIAL = "sequential_fragments"

CHUNKING_OUTLINE_ACT1_ES = """\
--- Modo fragmentación (chunking) ---
En esta ejecución debes entregar SOLO:
1) OUTLINE completo del vídeo (todos los bloques previstos, con tiempos orientativos).
2) El GUIÓN correspondiente ÚNICAMENTE al primer segmento narrativo (aprox. 0–5 min de locución), con [CATEGORIA: …] y [B-ROLL: …] según el formato maestro.

NO escribas en esta misma respuesta los actos o bloques siguientes (ni Acto 2 en adelante, ni desarrollo medio completo, ni cierre largo, ni CTA final): detente tras el primer bloque de guión.
Cierra el documento con una línea exacta en una sola línea:
<<< FIN_FRAGMENTO_1 >>>

El usuario revisará este fragmento fuera del modelo (p. ej. en el editor); una pasada posterior continuará el guión. No simules chat interactivo ni pidas “confirmación” dentro del texto.
"""


def chunk_outline_act1_only(row: dict[str, Any] | None) -> bool:
    if not row:
        return False
    pj = row.get("params_json") or {}
    if not isinstance(pj, dict):
        return False
    return str(pj.get("chunking") or "").strip() == CHUNKING_MODE_OUTLINE_ACT1


def sequential_fragments_enabled(row: dict[str, Any] | None) -> bool:
    if not row:
        return False
    pj = row.get("params_json") or {}
    if not isinstance(pj, dict):
        return False
    return str(pj.get("chunking") or "").strip() == CHUNKING_MODE_SEQUENTIAL


def effective_chunk_target_minutes(row: dict[str, Any] | None, pipeline_minutes: float) -> float:
    """Ajusta minutos efectivos para metas de palabras (fragmento único o reparto por estructura)."""
    try:
        pm = float(pipeline_minutes)
    except (TypeError, ValueError):
        pm = 10.0
    pm = max(1.0, pm)
    if sequential_fragments_enabled(row):
        # El reparto por minutos lo hace `minutes_for_sequential_fragment` en el runner (pesos por fragmento).
        pj = row.get("params_json") or {}
        if not isinstance(pj, dict):
            pj = {}
        sp = normalize_structure_preset(str(pj.get("structure_preset") or ""))
        n = max(1, len(fragment_plan(sp)))
        return max(1.0, pm / n)
    if chunk_outline_act1_only(row):
        pj = row.get("params_json") or {}
        if not isinstance(pj, dict):
            pj = {}
        try:
            seg = float(pj.get("chunk_first_segment_minutes") or 5)
        except (TypeError, ValueError):
            seg = 5.0
        seg = max(1.0, min(seg, 45.0))
        return min(pm, seg)
    return pm


def list_script_writer_templates(*, limit: int = 200) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 500))
    return db.fetch_all(
        """
        select id::text as id, name, system_instructions, user_instructions,
               params_json,
               created_at, updated_at
        from script_writer_templates
        order by lower(name) asc
        limit %(limit)s
        """,
        {"limit": limit},
    )


def get_script_writer_template(template_id: str) -> dict[str, Any] | None:
    return db.fetch_one(
        """
        select id::text as id, name, system_instructions, user_instructions,
               params_json,
               created_at, updated_at
        from script_writer_templates
        where id = %(id)s::uuid
        """,
        {"id": template_id},
    )


def create_script_writer_template(
    *,
    name: str,
    system_instructions: str = "",
    user_instructions: str = "",
    params_json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    name = (name or "").strip()
    if not name:
        raise ValueError("name is required")
    row = db.fetch_one(
        """
        insert into script_writer_templates(name, system_instructions, user_instructions, params_json)
        values (%(name)s, %(system_instructions)s, %(user_instructions)s, %(params_json)s::jsonb)
        returning id::text as id
        """,
        {
            "name": name[:120],
            "system_instructions": system_instructions or "",
            "user_instructions": user_instructions or "",
            "params_json": json.dumps(params_json or {}, ensure_ascii=False),
        },
    )
    if not row:
        raise RuntimeError("failed to create script_writer template")
    out = get_script_writer_template(row["id"])
    if not out:
        raise RuntimeError("failed to read created script_writer template")
    return out


def update_script_writer_template(
    template_id: str,
    *,
    name: str | None = None,
    system_instructions: str | None = None,
    user_instructions: str | None = None,
    params_json: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    cur = get_script_writer_template(template_id)
    if not cur:
        return None

    next_row = {
        "name": (name if name is not None else cur.get("name") or "").strip(),
        "system_instructions": system_instructions if system_instructions is not None else (cur.get("system_instructions") or ""),
        "user_instructions": user_instructions if user_instructions is not None else (cur.get("user_instructions") or ""),
        "params_json": params_json if params_json is not None else (cur.get("params_json") or {}),
    }
    if not next_row["name"]:
        raise ValueError("name is required")

    db.execute(
        """
        update script_writer_templates
        set name=%(name)s,
            system_instructions=%(system_instructions)s,
            user_instructions=%(user_instructions)s,
            params_json=%(params_json)s::jsonb,
            updated_at=now()
        where id = %(id)s::uuid
        """,
        {
            "id": template_id,
            "name": next_row["name"][:120],
            "system_instructions": next_row["system_instructions"] or "",
            "user_instructions": next_row["user_instructions"] or "",
            "params_json": json.dumps(next_row["params_json"] or {}, ensure_ascii=False),
        },
    )
    return get_script_writer_template(template_id)


def delete_script_writer_template(template_id: str) -> bool:
    db.execute("delete from script_writer_templates where id = %(id)s::uuid", {"id": template_id})
    return True


def extras_from_template_row(row: dict[str, Any]) -> tuple[str, str]:
    """
    Devuelve (system_extra, user_extra) para concatenar al prompt maestro de guion.
    Los campos genéricos van en params_json: pacing, data_density, structure_preset.
    """
    sys_e = str(row.get("system_instructions") or "").strip()
    usr_e = str(row.get("user_instructions") or "").strip()
    pj = row.get("params_json") or {}
    if not isinstance(pj, dict):
        pj = {}

    pacing = str(pj.get("pacing") or "").strip().lower()
    density = str(pj.get("data_density") or "").strip().lower()
    structure = str(pj.get("structure_preset") or "").strip().lower()

    pacing_hints = {
        "short": "Ritmo VO: frases cortas y rápidas; prioriza impacto inmediato (estilo snackable).",
        "mixed": "Ritmo VO: alterna frases cortas con párrafos explicativos cuando el tema lo exija.",
        "long": "Ritmo VO: párrafos desarrollados y pausados; tono documental / profundo.",
    }
    density_hints = {
        "low": "Densidad de datos: baja; privilegia historia, metáforas y ejemplos; pocas cifras concretas.",
        "medium": "Densidad de datos: media; mezcla narrativa con datos cuando aporten claridad.",
        "high": "Densidad de datos: alta; incorpora referencias cuantitativas donde proceda y marca incertidumbre como [dato a verificar] si no está en el contexto.",
    }
    structure_hints = {
        "default_five_blocks": (
            "Estructura de escenas: usa las **cinco secciones** del formato por defecto "
            "([CATEGORIA: Introducción], tres pilares de cuerpo, [CATEGORIA: Cierre]) alineadas con OUTLINE."
        ),
        "four_act": (
            "Estructura de escenas (cuatro actos): "
            "(1) Hook / tensión inicial (~primer bloque), "
            "(2) Introducción + promesa clara de qué entenderá el espectador, "
            "(3) Cuerpo en bloques de desarrollo con datos/story según densidad pedida, "
            "(4) Cierre que suba de nivel (consecuencias prácticas / ‘freedom shift’, sin nuevo hook). "
            "Marca [CATEGORIA: …] para que cada acto sea editable por separado."
        ),
    }

    bullets: list[str] = []
    if pacing and pacing in pacing_hints:
        bullets.append(f"- {pacing_hints[pacing]}")
    if density and density in density_hints:
        bullets.append(f"- {density_hints[density]}")
    if structure and structure in structure_hints:
        bullets.append(f"- {structure_hints[structure]}")

    if bullets:
        block = "\n".join(bullets)
        usr_e = (
            usr_e
            + ("\n\n" if usr_e else "")
            + "--- Parámetros del template de Script Writer ---\n"
            + block
        ).strip()

    if chunk_outline_act1_only(row) and not sequential_fragments_enabled(row):
        sys_e = (sys_e + "\n\n" if sys_e else "") + CHUNKING_OUTLINE_ACT1_ES.strip()

    return sys_e, usr_e
