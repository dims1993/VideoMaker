"""Plantillas de sistema para guiones largos (tres actos, B-roll, coherencia)."""

from __future__ import annotations

from textwrap import dedent

from videomaker.core.models import Locale, ScriptBlueprint


def build_categories_placeholder(blueprint: ScriptBlueprint) -> str:
    if blueprint.categories:
        lines = []
        for c in blueprint.categories:
            beats = "\n".join(f"  - {b}" for b in c.beats)
            lines.append(f"### {c.title}\n{beats}")
        return "\n".join(lines)
    return dedent(
        """
        ### 1 · Introducción (~1:30) — Plantear problema o reflexión; el gancho
        - Promesa clara; por qué importa ahora

        ### 2–4 · Cuerpo — Tres pilares (~2:00 cada uno; ~6:00 total)
        - Pilar A: primera historia o argumento con ejemplo
        - Pilar B: segundo punto; contraste o profundización
        - Pilar C: tercer punto; matiz o consecuencia

        ### 5 · Conclusión y cierre (~2:30)
        - Resumen breve, moraleja, CTA reflexiva (sin venta agresiva)
        """
    ).strip()


def master_script_system_prompt(locale: Locale, target_minutes: float) -> str:
    lang = "español neutro" if locale == Locale.ES else "English (clear, neutral)"
    return dedent(
        f"""
        Eres guionista de canal educativo/motivacional en {lang}.
        Producción pensada para **voz en off (TTS)** y vídeo con B-roll: frases claras,
        ritmo oral; evita listas densas de números.

        **Extensión y profundidad**
        - Objetivo: **mínimo 1 500 palabras narrables** (cuenta solo el texto del guion; **no cuentan**
          `[B-ROLL: …]`, `[CATEGORIA: …]`, OUTLINE, ni la línea de keywords). No resumas: desarrolla cada idea con
          profundidad. Usa **anécdotas**, **metáforas** y ejemplos concretos.
        - Referencia de tiempo total del vídeo hablado: **~{target_minutes:.1f} min** (orientativo).
          La estructura por actos reparte el tiempo; si el tema lo pide, puedes acercarte a **~10 min**
          de narración hablada sin recortar ideas importantes.

        **Estructura de tres actos (regla narrativa)**
        1. **Introducción (~1:30 min):** plantea el problema o la reflexión; el **gancho**.
        2. **Cuerpo — tres pilares (~6:00 min total):** tres puntos o historias relacionadas;
           **~2 minutos por pilar** (desarrollo pausado, no superficial).
        3. **Conclusión y cierre (~2:30 min):** resumen, moraleja y una **llamada a la acción (CTA)
           reflexiva** (invitar a pensar o un hábito pequeño), sin CTA comercial agresiva.

        **Cinco secciones claras en el GUIÓN**
        Marca el guion en **5 bloques** con encabezado `[CATEGORIA: …]` alineados con lo anterior, por ejemplo:
        `[CATEGORIA: Introducción]`, `[CATEGORIA: Pilar 1]`, `[CATEGORIA: Pilar 2]`,
        `[CATEGORIA: Pilar 3]`, `[CATEGORIA: Cierre]`.

        **CRÍTICO — etiquetas [B-ROLL] (cambio de plano)**
        - Inserta **`[B-ROLL: descripción detallada]` exactamente cada dos frases** del texto narrable.
          Si escribes 10 frases en un bloque, debes tener ~5 etiquetas intercaladas.
        - Coloca cada etiqueta **justo en el punto donde debe cambiar la imagen** (entre la segunda y
          la tercera frase del bloque, etc.), no agrupes todas al final del párrafo ni al final de una sección.
        - La descripción debe ser **concreta** (acción, lugar, luz, encuadre; puede incluir términos en
          inglés útiles para stock: *slow motion coffee steam*, *aerial forest at sunrise*).
        - **Prohibido** acumular etiquetas solo al final del bloque o del guion; reparte el ritmo visual
          a lo largo del discurso.
        - Son solo para producción: el TTS **no** las lee.

        **Corchetes y TTS**
        - Usa `[CATEGORIA: …]` por bloque y `[B-ROLL: …]` como se indica.
        - No uses otros corchetes de nota ([PUENTE], [TÉCNICA N], secciones “ETIQUETAS DE B-ROLL” al final, etc.).

        **Salida**
        - Primero un **OUTLINE** con tiempos aproximados por bloque/acto.
        - Luego el **GUIÓN** completo con `[CATEGORIA: …]` y `[B-ROLL: …]` según las reglas.
        - Al final, **8–12 palabras clave en inglés** separadas por comas para Pexels (stock).
        """
    ).strip()


def build_user_prompt_from_blueprint(blueprint: ScriptBlueprint) -> str:
    kw = ", ".join(blueprint.keywords) if blueprint.keywords else "(sin palabras clave)"
    cats = build_categories_placeholder(blueprint)
    ctx = blueprint.extra_context.strip() or "(sin contexto adicional)"
    parts = [
        f"Palabras clave / tema: {kw}",
        "",
        "Contexto adicional del creador:",
        ctx,
        "",
        "Esquema narrativo (tres actos / cinco secciones):",
        cats,
        "",
        "Instrucciones explícitas:",
        "- Genera un guion de **aproximadamente 1 500 palabras**. No resumas; profundiza.",
        "- Divide el contenido en **5 secciones** claramente marcadas con [CATEGORIA: …].",
        "- **CRÍTICO:** etiqueta **`[B-ROLL: descripción detallada]` cada dos frases**, colocada exactamente "
        "donde debe cambiar la imagen; **no** las pongas solo al final del párrafo o al final del guion.",
        "",
        f"Duración orientativa total de narración: ~{blueprint.target_minutes:.1f} min (referencia; "
        "prioriza completar los tres actos y ~1 500 palabras).",
    ]
    return "\n".join(parts).strip()


def prompt_builder_button_payload(blueprint: ScriptBlueprint) -> dict:
    """Forma serializable para una futura UI (botón 'generar prompt')."""
    return {
        "system": master_script_system_prompt(blueprint.locale, blueprint.target_minutes),
        "user": build_user_prompt_from_blueprint(blueprint),
    }
