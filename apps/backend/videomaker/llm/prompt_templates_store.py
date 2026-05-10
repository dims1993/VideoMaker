"""Prompt templates stored in Postgres (prompt library)."""

from __future__ import annotations

import json
from typing import Any

from videomaker.core import db


def list_prompt_templates(*, limit: int = 200) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 500))
    return db.fetch_all(
        """
        select id::text as id, name, hook_style, visual_style, tone,
               system_instructions, user_instructions,
               params_json,
               created_at, updated_at
        from prompt_templates
        order by lower(name) asc
        limit %(limit)s
        """,
        {"limit": limit},
    )


def get_prompt_template(template_id: str) -> dict[str, Any] | None:
    return db.fetch_one(
        """
        select id::text as id, name, hook_style, visual_style, tone,
               system_instructions, user_instructions,
               params_json,
               created_at, updated_at
        from prompt_templates
        where id = %(id)s::uuid
        """,
        {"id": template_id},
    )


def create_prompt_template(
    *,
    name: str,
    hook_style: str = "",
    visual_style: str = "",
    tone: str = "",
    system_instructions: str = "",
    user_instructions: str = "",
    params_json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    name = (name or "").strip()
    if not name:
        raise ValueError("name is required")
    row = db.fetch_one(
        """
        insert into prompt_templates(name, hook_style, visual_style, tone, system_instructions, user_instructions, params_json)
        values (%(name)s, %(hook_style)s, %(visual_style)s, %(tone)s, %(system_instructions)s, %(user_instructions)s, %(params_json)s::jsonb)
        returning id::text as id
        """,
        {
            "name": name[:120],
            "hook_style": (hook_style or "")[:80],
            "visual_style": (visual_style or "")[:120],
            "tone": (tone or "")[:80],
            "system_instructions": system_instructions or "",
            "user_instructions": user_instructions or "",
            "params_json": json.dumps(params_json or {}, ensure_ascii=False),
        },
    )
    if not row:
        raise RuntimeError("failed to create prompt template")
    out = get_prompt_template(row["id"])
    if not out:
        raise RuntimeError("failed to read created prompt template")
    return out


def update_prompt_template(
    template_id: str,
    *,
    name: str | None = None,
    hook_style: str | None = None,
    visual_style: str | None = None,
    tone: str | None = None,
    system_instructions: str | None = None,
    user_instructions: str | None = None,
    params_json: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    cur = get_prompt_template(template_id)
    if not cur:
        return None

    next_row = {
        "name": (name if name is not None else cur.get("name") or "").strip(),
        "hook_style": hook_style if hook_style is not None else (cur.get("hook_style") or ""),
        "visual_style": visual_style if visual_style is not None else (cur.get("visual_style") or ""),
        "tone": tone if tone is not None else (cur.get("tone") or ""),
        "system_instructions": system_instructions if system_instructions is not None else (cur.get("system_instructions") or ""),
        "user_instructions": user_instructions if user_instructions is not None else (cur.get("user_instructions") or ""),
        "params_json": params_json if params_json is not None else (cur.get("params_json") or {}),
    }
    if not next_row["name"]:
        raise ValueError("name is required")

    db.execute(
        """
        update prompt_templates
        set name=%(name)s,
            hook_style=%(hook_style)s,
            visual_style=%(visual_style)s,
            tone=%(tone)s,
            system_instructions=%(system_instructions)s,
            user_instructions=%(user_instructions)s,
            params_json=%(params_json)s::jsonb,
            updated_at=now()
        where id = %(id)s::uuid
        """,
        {
            "id": template_id,
            "name": next_row["name"][:120],
            "hook_style": (next_row["hook_style"] or "")[:80],
            "visual_style": (next_row["visual_style"] or "")[:120],
            "tone": (next_row["tone"] or "")[:80],
            "system_instructions": next_row["system_instructions"] or "",
            "user_instructions": next_row["user_instructions"] or "",
            "params_json": json.dumps(next_row["params_json"] or {}, ensure_ascii=False),
        },
    )
    return get_prompt_template(template_id)


def delete_prompt_template(template_id: str) -> bool:
    db.execute("delete from prompt_templates where id = %(id)s::uuid", {"id": template_id})
    return True

