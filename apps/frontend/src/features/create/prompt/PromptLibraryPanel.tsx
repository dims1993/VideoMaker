import { useEffect, useState } from "react";
import { Btn, ExpandableTextArea, Input, Label, Select } from "../../../components/ui";
import { PipelineSection as Section } from "../pipeline/PipelineSection";
import type { RunFn } from "../types";
import type { PromptLibraryStore } from "./usePromptLibrary";

// Section imported from PipelineSection.tsx (shared dark-themed collapsible)

// ── AI Prompt Generator ───────────────────────────────────────────────────
function AIPromptGenerator({ onGenerated }: { onGenerated: (t: Record<string, unknown>) => void }) {
  const [transcriptText, setTranscriptText] = useState("");
  const [fileName, setFileName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    const reader = new FileReader();
    reader.onload = (ev) => setTranscriptText((ev.target?.result as string) ?? "");
    reader.readAsText(file);
  };

  const handleGenerate = async () => {
    if (!transcriptText.trim()) { setError("Carga un documento o pega el contenido primero."); return; }
    setError("");
    setLoading(true);
    try {
      const res = await fetch("/api/prompt-templates/generate-from-transcript", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transcript_text: transcriptText }),
      });
      if (!res.ok) {
        const j = await res.json().catch(() => ({})) as { detail?: string };
        throw new Error(j.detail ?? `Error ${res.status}`);
      }
      const data = await res.json() as Record<string, unknown>;
      onGenerated(data);
      setTranscriptText("");
      setFileName("");
      if (fileRef.current) fileRef.current.value = "";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error desconocido");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-xl border border-slate-600 bg-slate-800 p-4 space-y-3">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold tracking-wider capitalize text-white">Generador De Prompt Con IA</div>
          <div className="text-[11px] text-slate-400 mt-0.5">
            Carga las transcripciones de un canal y Claude Sonnet analizará el estilo y rellenará todos los campos automáticamente.
          </div>
        </div>
        <span className="shrink-0 rounded-md border border-violet-500/40 bg-violet-950/40 px-2 py-0.5 text-[10px] font-mono text-violet-300">
          Claude Sonnet
        </span>
      </div>

      {/* File upload */}
      <div>
        <label className="block text-xs font-medium text-slate-400 mb-1">Documento de transcripciones</label>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            className="rounded-lg border border-slate-600 bg-slate-700 px-3 py-1.5 text-xs text-slate-200 hover:bg-slate-600 transition-colors"
          >
            Seleccionar archivo
          </button>
          {fileName ? (
            <>
              <span className="text-xs text-slate-400 truncate max-w-[180px]" title={fileName}>{fileName}</span>
              <button type="button" onClick={() => { setFileName(""); setTranscriptText(""); if (fileRef.current) fileRef.current.value = ""; }} className="text-slate-500 hover:text-slate-300 text-xs">✕</button>
            </>
          ) : (
            <span className="text-xs text-slate-500">.json, .txt o .md</span>
          )}
          <input ref={fileRef} type="file" accept=".json,.txt,.md" className="hidden" onChange={handleFile} />
        </div>
      </div>

      {/* Or paste */}
      <div>
        <label className="block text-xs font-medium text-slate-400 mb-1">
          O pega el contenido directamente
          {transcriptText && <span className="ml-2 text-slate-500">({transcriptText.length.toLocaleString()} chars)</span>}
        </label>
        <textarea
          value={transcriptText}
          onChange={(e) => { setTranscriptText(e.target.value); setFileName(""); }}
          placeholder="Pega aquí las transcripciones del canal…"
          rows={4}
          className="w-full rounded-lg border border-slate-600 bg-slate-700 px-3 py-2 text-xs text-slate-200 placeholder:text-slate-500 focus:border-slate-400 focus:outline-none focus:bg-slate-700 focus:text-slate-100 resize-none"
        />
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-rose-500/40 bg-rose-950/30 px-3 py-2 text-xs text-rose-400">{error}</div>
      )}

      {/* Actions */}
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] text-slate-500">Requiere <code className="rounded bg-slate-700 px-1">ANTHROPIC_API_KEY</code> en .env</span>
        <div className="flex items-center gap-2">
          {loading && <span className="text-xs text-violet-400 animate-pulse">Claude analizando…</span>}
          <Btn
            type="button"
            className="bg-violet-600 text-white hover:bg-violet-500 disabled:opacity-50"
            disabled={loading || !transcriptText.trim()}
            onClick={handleGenerate}
          >
            {loading ? "Analizando…" : "Analizar y generar template"}
          </Btn>
        </div>
      </div>
    </div>
  );
}

// ── Main panel ────────────────────────────────────────────────────────────
export function PromptLibraryPanel({
  run,
  locked,
  promptStepState,
  library,
}: {
  run: RunFn;
  locked: boolean;
  promptStepState: string;
  library: PromptLibraryStore;
  provider?: string;
  model?: string;
}) {
  const lib = library;

  const lockReason =
    promptStepState === "running"
      ? "Ejecutando paso Prompt…"
      : locked
        ? "Este prompt queda fijado para esta ejecución (paso Prompt ya ejecutado)."
        : null;

  // Preview JSON
  const previewJson = JSON.stringify(
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
    2,
  );

  const isNewTemplate = !lib.promptTemplateId;
  const [previewFullscreen, setPreviewFullscreen] = useState(false);

  useEffect(() => {
    if (!previewFullscreen) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") setPreviewFullscreen(false); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [previewFullscreen]);

  return (
    <div className={`rounded-2xl bg-slate-900 p-4 space-y-3 ${locked ? "opacity-95" : ""}`}>
      {lockReason && (
        <div className="rounded-xl border border-amber-500/40 bg-amber-950/30 px-3 py-2 text-xs text-amber-300">
          <span className="font-semibold">Bloqueado.</span> {lockReason} Para editar usa{" "}
          <strong>Reset</strong> en la pipeline (arriba).
        </div>
      )}

      <fieldset disabled={locked} className="min-w-0 space-y-3 border-0 p-0">

        {/* ── Template selector ── SIEMPRE VISIBLE PRIMERO */}
        <div className="flex flex-wrap items-end justify-between gap-2 rounded-xl border border-slate-600 bg-gradient-to-r from-slate-800 to-slate-700 px-4 py-3 shadow-md">
          <div className="min-w-[200px] flex-1">
            <label className="mb-1 block text-[10px] font-semibold uppercase tracking-widest text-slate-400">
              Template
            </label>
            <select
              value={lib.promptTemplateId}
              onChange={async (e) => {
                const id = e.target.value;
                if (!id) { lib.clearTemplate(); return; }
                lib.setPromptTemplateId(id);
                await lib.applyTemplateFromApi(id);
              }}
              className="w-full rounded-lg border border-slate-600 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-200 focus:border-slate-400 focus:outline-none"
            >
              <option value="">(nuevo template)</option>
              {lib.promptTemplates.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>
          <div className="flex flex-wrap gap-2">
            <Btn
              className="border border-slate-500 bg-slate-700 text-slate-200 hover:bg-slate-600"
              onClick={() => run("Recargar templates", async () => { await lib.loadPromptTemplates(); })}
            >
              Reload
            </Btn>
            <Btn
              className="bg-white text-slate-900 hover:bg-slate-100"
              disabled={!lib.promptName.trim() && !lib.promptTopic.trim()}
              onClick={() => run("Guardar template", async () => { await lib.saveTemplate(); })}
            >
              Save
            </Btn>
            <Btn
              className="border border-rose-500/50 bg-rose-950/40 text-rose-400 hover:bg-rose-950/70 disabled:opacity-40"
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

        {/* ── Generador con IA: solo en modo nuevo template ── */}
        {isNewTemplate && !locked && (
          <AIPromptGenerator
            onGenerated={(data) => {
              lib.applyTemplateFields(data as Parameters<typeof lib.applyTemplateFields>[0]);
            }}
          />
        )}

        {/* ── Campos del formulario ── */}
        {/* ── Nombre + estilo básico ── */}
        <Section
          id="nombre-estilo"
          title="Nombre y estilo"
          description="Identifica el template y define el tono general, el tipo de gancho y el estilo visual del vídeo."
        >
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
              <Input value={lib.promptVisualStyle} onChange={(e) => lib.setPromptVisualStyle(e.target.value)} placeholder="B-roll / motion graphics / minimal..." />
            </div>
            <div>
              <Label>Tone</Label>
              <Input value={lib.promptTone} onChange={(e) => lib.setPromptTone(e.target.value)} placeholder="Dinámico / Reflexivo / Humor..." />
            </div>
          </div>
        </Section>

        {/* ── Parámetros extra ── */}
        <Section
          id="parametros-extra"
          title="Parámetros extra"
          description="Audiencia objetivo, idioma, estructura narrativa y ratio visual. El LLM los usa para adaptar el guion al canal."
        >
          <div className="grid gap-3 md:grid-cols-2">
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
        </Section>

        {/* ── System instructions ── */}
        <Section
          id="system-instructions"
          title="System instructions"
          description="Rol y reglas permanentes del modelo (personalidad, restricciones, formato de salida). Se envía como mensaje system."
        >
          <ExpandableTextArea
            value={lib.promptSystem}
            onChange={lib.setPromptSystem}
            placeholder="Instrucciones de sistema para el LLM…"
            modalTitle="System instructions"
          />
        </Section>

        {/* ── User instructions ── */}
        <Section
          id="user-instructions"
          title="User instructions"
          description="Instrucciones específicas del vídeo: estructura del guion, ejemplos de estilo, referencias del canal o restricciones de contenido."
        >
          <ExpandableTextArea
            value={lib.promptUser}
            onChange={lib.setPromptUser}
            placeholder="Instrucciones de usuario para el LLM…"
            modalTitle="User instructions"
          />
        </Section>

        {/* ── Tema del vídeo ── */}
        <Section
          id="tema-video"
          title="Tema del vídeo"
          description="El tema concreto del vídeo de hoy. Se pasa al Script Writer como contexto de sesión."
        >
          <div>
            <Label>Tema / input del usuario</Label>
            <Input
              value={lib.promptTopic}
              onChange={(e) => lib.setPromptTopic(e.target.value)}
              placeholder="Ej: Ciudades nómadas 2026"
            />
          </div>
        </Section>

      </fieldset>

      {/* ── Preview (Merger) ── fuera del fieldset, estilo Salida */}
      <div className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="text-sm font-semibold tracking-wider capitalize text-white">Preview · Merger JSON</div>
          <div role="button" tabIndex={0}
            className="cursor-pointer rounded-lg border border-slate-600 bg-slate-800 px-2 py-1 text-xs font-medium text-slate-200 hover:bg-slate-700"
            onClick={() => setPreviewFullscreen(true)}
            onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setPreviewFullscreen(true); } }}>
            Pantalla completa
          </div>
        </div>
        <div
          role="button"
          tabIndex={0}
          aria-label="Ver preview a pantalla completa"
          onClick={() => setPreviewFullscreen(true)}
          onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setPreviewFullscreen(true); } }}
          className={`min-h-[120px] w-full cursor-pointer rounded-xl border border-slate-600 bg-slate-800 px-3 py-2 text-left font-mono text-xs leading-relaxed shadow-inner outline-none transition hover:border-slate-500 ${previewJson.trim() ? "text-slate-300" : "text-slate-500"}`}
        >
          <span className="block max-h-[200px] overflow-y-auto whitespace-pre-wrap">
            {previewJson.trim()
              ? previewJson.slice(0, 600) + (previewJson.length > 600 ? "\n…" : "")
              : "El JSON del merger aparecerá aquí al rellenar los campos. Pulsa para ver completo."}
          </span>
        </div>
      </div>

      {previewFullscreen && (
        <div
          className="fixed inset-y-0 left-[280px] right-0 z-[200] flex items-stretch justify-center bg-slate-950/55 p-2 sm:p-4"
          role="dialog"
          aria-modal="true"
          aria-label="Preview Merger JSON a pantalla completa"
        >
          <div className="flex h-[min(calc(100vh-1rem),920px)] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
            <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
              <span className="text-sm font-semibold text-slate-900">Preview · Merger JSON</span>
              <div className="flex flex-wrap gap-2">
                <Btn
                  type="button"
                  className="bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"
                  onClick={async () => {
                    await navigator.clipboard.writeText(previewJson);
                  }}
                >
                  Copiar
                </Btn>
                <Btn
                  type="button"
                  className="bg-slate-900 text-white hover:bg-slate-800"
                  onClick={() => setPreviewFullscreen(false)}
                >
                  Cerrar
                </Btn>
              </div>
            </div>
            <pre className="min-h-0 flex-1 overflow-auto whitespace-pre-wrap px-4 py-3 font-mono text-sm leading-relaxed text-slate-800">
              {previewJson}
            </pre>
            <p className="shrink-0 border-t border-slate-100 px-4 py-2 text-[11px] leading-snug text-slate-500">
              <kbd className="rounded bg-slate-100 px-1 font-mono text-[10px]">Esc</kbd> cierra esta ventana.
              {previewJson.length > 0 && <span> · {previewJson.length.toLocaleString()} caracteres</span>}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
