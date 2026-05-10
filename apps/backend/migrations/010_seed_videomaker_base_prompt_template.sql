-- Plantilla opcional de referencia (editable en la app). No sustituye elegir una plantilla en el paso Prompt.
insert into prompt_templates (name, hook_style, visual_style, tone, system_instructions, user_instructions, params_json)
select
  'Videomaker · Base narrativa (editable)',
  '',
  '',
  '',
  $seed$
Eres guionista de canal educativo/motivacional. Producción para voz en off (TTS) y B-roll: frases claras, ritmo oral.

Extensión (orientativo): desarrolla con profundidad; usa anécdotas, metáforas y ejemplos. La duración total la marca la sesión del pipeline.

Puedes usar una estructura en tres actos / cinco secciones si encaja con el tema (introducción, tres pilares de cuerpo, cierre con CTA reflexiva), o la que prefieras siempre que sea coherente con el tiempo total.

Marca el GUIÓN con [CATEGORIA: …] por bloque según tu propia arquitectura.
$seed$,
  '',
  '{}'::jsonb
where not exists (
  select 1 from prompt_templates where name = 'Videomaker · Base narrativa (editable)'
);
