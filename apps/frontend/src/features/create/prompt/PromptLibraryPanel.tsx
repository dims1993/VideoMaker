import { Btn, Input, Label, Select, TextArea } from "../../../components/ui";
import type { RunFn } from "../types";
import type { PromptLibraryStore } from "./usePromptLibrary";

export function PromptLibraryPanel({
  run,
  locked,
  promptStepState,
  library,
}: {
  run: RunFn;
  /** Tras ejecutar el paso Prompt en la pipeline (o mientras corre), el template queda fijado. */
  locked: boolean;
  promptStepState: string;
  /** Estado compartido con el padre para enviar `prompt_template_id` al ejecutar el paso en la API. */
  library: PromptLibraryStore;
}) {
  const lib = library;

  const lockReason =
    promptStepState === "running"
      ? "Ejecutando paso Prompt…"
      : locked
        ? "Este prompt queda fijado para esta ejecución (paso Prompt ya ejecutado)."
        : null;

  return (
    <div className={`space-y-3 ${locked ? "opacity-95" : ""}`}>
      {lockReason ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-950">
          <span className="font-semibold">Bloqueado.</span> {lockReason} Para editar o cambiar de plantilla usa{" "}
          <strong>Reset</strong> en la pipeline (arriba).
        </div>
      ) : null}

      <fieldset disabled={locked} className="min-w-0 space-y-3 border-0 p-0">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div className="min-w-[260px] flex-1">
          <Label>Template</Label>
          <Select
            value={lib.promptTemplateId}
            onChange={async (e) => {
              const id = e.target.value;
              lib.setPromptTemplateId(id);
              if (!id) return;
              await lib.applyTemplateFromApi(id);
            }}
          >
            <option value="">(nuevo template)</option>
            {lib.promptTemplates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="flex flex-wrap gap-2">
          <Btn
            className="bg-white text-slate-900 ring-1 ring-slate-200 hover:bg-slate-50"
            onClick={() =>
              run("Recargar templates", async () => {
                await lib.loadPromptTemplates();
              })
            }
          >
            Reload
          </Btn>
          <Btn
            className="bg-slate-900 text-white hover:bg-slate-800"
            disabled={!lib.promptName.trim() && !lib.promptTopic.trim()}
            title="Guarda en el catálogo (Postgres). Hace falta al menos Nombre o Tema."
            onClick={() =>
              run("Guardar template", async () => {
                await lib.saveTemplate();
              })
            }
          >
            Save
          </Btn>
          <Btn
            className="bg-white text-rose-700 ring-1 ring-rose-200 hover:bg-rose-50 disabled:opacity-40"
            disabled={!lib.promptTemplateId}
            onClick={() =>
              run("Eliminar template", async () => {
                if (!lib.promptTemplateId) return;
                if (!confirm("¿Eliminar este template?")) return;
                await lib.deleteTemplate();
              })
            }
          >
            Delete
          </Btn>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <div>
          <Label>Nombre</Label>
          <Input value={lib.promptName} onChange={(e) => lib.setPromptName(e.target.value)} placeholder="SaaS Explainer / Curiosidades / Ventas..." />
        </div>
        <div>
          <Label>Hook style</Label>
          <Input value={lib.promptHookStyle} onChange={(e) => lib.setPromptHookStyle(e.target.value)} placeholder="Data / Question / Story..." />
        </div>
        <div>
          <Label>Visual style</Label>
          <Input
            value={lib.promptVisualStyle}
            onChange={(e) => lib.setPromptVisualStyle(e.target.value)}
            placeholder="B-roll stock / motion graphics / minimal..."
          />
        </div>
        <div>
          <Label>Tone</Label>
          <Input value={lib.promptTone} onChange={(e) => lib.setPromptTone(e.target.value)} placeholder="Dinámico / Reflexivo / Humor..." />
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Parámetros extra (del formato)</div>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <div className="md:col-span-2">
            <Label>Target audience</Label>
            <Input value={lib.promptTargetAudience} onChange={(e) => lib.setPromptTargetAudience(e.target.value)} placeholder="Remote workers aged 25-40" />
          </div>
          <div>
            <Label>Language code</Label>
            <Input value={lib.promptLangCode} onChange={(e) => lib.setPromptLangCode(e.target.value)} placeholder="es-ES" />
          </div>
          <div>
            <Label>Slang level</Label>
            <Select value={lib.promptSlangLevel} onChange={(e) => lib.setPromptSlangLevel(e.target.value as "low" | "medium" | "high")}>
              <option value="low">low</option>
              <option value="medium">medium</option>
              <option value="high">high</option>
            </Select>
          </div>
          <div>
            <Label>Narrative tone</Label>
            <Input value={lib.promptNarrTone} onChange={(e) => lib.setPromptNarrTone(e.target.value)} placeholder="Informative and energetic" />
          </div>
          <div>
            <Label>Hook type</Label>
            <Input value={lib.promptHookType} onChange={(e) => lib.setPromptHookType(e.target.value)} placeholder="Data-driven" />
          </div>
          <div>
            <Label>CTA type</Label>
            <Input value={lib.promptCtaType} onChange={(e) => lib.setPromptCtaType(e.target.value)} placeholder="Engagement (Comment)" />
          </div>
          <div>
            <Label>Aspect ratio</Label>
            <Input value={lib.promptAspectRatio} onChange={(e) => lib.setPromptAspectRatio(e.target.value)} placeholder="9:16" />
          </div>
          <div className="md:col-span-2">
            <Label>Visual identity style</Label>
            <Input value={lib.promptVisualStyle2} onChange={(e) => lib.setPromptVisualStyle2(e.target.value)} placeholder="Cinematic / Vibrant" />
          </div>
          <div className="md:col-span-2">
            <Label>Key points (comma separated)</Label>
            <Input value={lib.promptKeyPoints} onChange={(e) => lib.setPromptKeyPoints(e.target.value)} placeholder="Lisbon, Chiang Mai, Mexico City" />
          </div>
        </div>
      </div>

      <div>
        <Label>System instructions</Label>
        <TextArea value={lib.promptSystem} onChange={(e) => lib.setPromptSystem(e.target.value)} />
      </div>
      <div>
        <Label>User instructions</Label>
        <TextArea value={lib.promptUser} onChange={(e) => lib.setPromptUser(e.target.value)} />
      </div>

      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
        <Label>Tema / input del usuario</Label>
        <Input value={lib.promptTopic} onChange={(e) => lib.setPromptTopic(e.target.value)} placeholder="Ej: Ciudades nómadas 2026" />
        <div className="mt-3 text-xs font-semibold uppercase tracking-wide text-slate-500">Preview (Merger)</div>
        <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded-xl bg-white p-3 text-xs text-slate-800 ring-1 ring-slate-200">
          {JSON.stringify(
            {
              template: {
                id: lib.promptTemplateId || null,
                name: lib.promptName,
                hook_style: lib.promptHookStyle,
                visual_style: lib.promptVisualStyle,
                tone: lib.promptTone,
                system_instructions: lib.promptSystem,
                user_instructions: lib.promptUser,
                params_json: {
                  target_audience: lib.promptTargetAudience,
                  language_context: { code: lib.promptLangCode, slang_level: lib.promptSlangLevel },
                  narrative_structure: {
                    tone: lib.promptNarrTone,
                    hook_type: lib.promptHookType,
                    cta_type: lib.promptCtaType,
                  },
                  visual_identity: { style: lib.promptVisualStyle2, aspect_ratio: lib.promptAspectRatio },
                  key_points: lib.promptKeyPoints
                    .split(",")
                    .map((x) => x.trim())
                    .filter(Boolean),
                },
              },
              topic: lib.promptTopic,
            },
            null,
            2
          )}
        </pre>
      </div>
      </fieldset>
    </div>
  );
}
