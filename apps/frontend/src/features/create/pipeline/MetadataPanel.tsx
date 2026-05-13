import { useCallback, useEffect, useRef, useState } from "react";
import { Btn, Input, Label, Select, TextArea } from "../../../components/ui";
import { postJson, putJson } from "../../../services/api";
import type { RunFn } from "../types";
import { PipelineSection as Section } from "./PipelineSection";

type PlatformId = "youtube" | "tiktok" | "reels";

export function MetadataPanel({
  run,
  workApplied,
  lang,
  refreshPipeline,
  metadataStepState,
}: {
  run: RunFn;
  workApplied: string;
  lang: string;
  refreshPipeline: () => Promise<void>;
  metadataStepState: string;
}) {
  const [jsonText, setJsonText] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const modalRef = useRef<HTMLTextAreaElement>(null);
  const generationRunning = metadataStepState === "running";

  const [targetPlatform, setTargetPlatform] = useState<PlatformId>("youtube");
  const [targetKeywords, setTargetKeywords] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [defaultSystemPrompt, setDefaultSystemPrompt] = useState("");

  useEffect(() => {
    if (!fullscreen) return;
    modalRef.current?.focus();
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") setFullscreen(false); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [fullscreen]);

  const loadMetadata = useCallback(async () => {
    const r = await fetch(`/api/pipeline/metadata?work=${encodeURIComponent(workApplied)}`);
    if (!r.ok) return;
    const j = (await r.json()) as { exists?: boolean; metadata?: Record<string, unknown> | null };
    if (j.exists && j.metadata && typeof j.metadata === "object") {
      setJsonText(JSON.stringify(j.metadata, null, 2)); setLoaded(true);
    } else { setJsonText(""); setLoaded(false); }
  }, [workApplied]);

  const hydrateSettings = useCallback(async () => {
    const r = await fetch(`/api/pipeline/metadata-settings?work=${encodeURIComponent(workApplied)}&lang=${encodeURIComponent(lang)}`);
    if (!r.ok) return;
    const j = (await r.json()) as { target_platform?: string; target_keywords?: string; system_prompt?: string; default_system_prompt?: string };
    if (j.target_platform === "youtube" || j.target_platform === "tiktok" || j.target_platform === "reels") setTargetPlatform(j.target_platform);
    if (j.target_keywords !== undefined) setTargetKeywords(j.target_keywords);
    if (j.system_prompt !== undefined) setSystemPrompt(j.system_prompt);
    if (typeof j.default_system_prompt === "string") setDefaultSystemPrompt(j.default_system_prompt);
  }, [workApplied, lang]);

  const refreshDefaultPromptPreview = useCallback(async (p: PlatformId) => {
    const r = await fetch(`/api/pipeline/metadata-settings?work=${encodeURIComponent(workApplied)}&lang=${encodeURIComponent(lang)}&preview_platform=${encodeURIComponent(p)}`);
    if (!r.ok) return;
    const j = (await r.json()) as { default_system_prompt?: string };
    if (typeof j.default_system_prompt === "string") setDefaultSystemPrompt(j.default_system_prompt);
  }, [workApplied, lang]);

  useEffect(() => { void loadMetadata(); }, [loadMetadata, metadataStepState, workApplied]);
  useEffect(() => { void hydrateSettings(); }, [hydrateSettings]);

  const onPlatformChange = (p: PlatformId) => {
    setTargetPlatform(p);
    void refreshDefaultPromptPreview(p);
  };

  const handleSave = async () => {
    const trimmed = jsonText.trim();
    if (!trimmed) throw new Error("El cuadro está vacío. Usa «Start step» para generar o pega un objeto JSON antes de guardar.");
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(trimmed) as Record<string, unknown>;
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("El JSON debe ser un objeto en la raíz { … }, no un array.");
    } catch (e) {
      throw new Error(e instanceof SyntaxError ? "JSON inválido (revisa comillas, comas y llaves)." : e instanceof Error ? e.message : String(e));
    }
    await putJson(`/api/pipeline/metadata`, { work: workApplied, metadata: parsed });
    await loadMetadata();
    await refreshPipeline();
  };

  return (
    <div className="rounded-2xl bg-slate-900 p-4 space-y-3">

      {/* Info */}
      <div className="rounded-xl border border-slate-600 bg-slate-800 px-3 py-2 text-xs text-slate-400">
        <span className="font-semibold text-white">Metadata</span> prepara título,
        descripción con actos para SEO, capítulos con timestamps, hook_type/hook_summary,
        bloques production/marketing y <code className="rounded bg-slate-700 px-1">_gen</code>{" "}
        (modelo y truncado del guion). <strong className="text-slate-300">Start step</strong> usa el LLM y los ajustes de abajo.
        El JSON vive en <code className="rounded bg-slate-700 px-1">pipeline/metadata.json</code>.
      </div>

      {generationRunning && (
        <div className="rounded-xl border border-amber-500/40 bg-amber-950/30 px-3 py-2 text-xs text-amber-300">
          Generando metadata con el modelo… el editor va en solo lectura hasta que termine.
        </div>
      )}

      {/* Settings */}
      <Section id="meta-settings" title="Ajustes De Generación" description="Plataforma destino, palabras clave y system prompt para personalizar el LLM.">
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <Label>Plataforma destino</Label>
              <Select value={targetPlatform} onChange={(e) => onPlatformChange(e.target.value as PlatformId)} disabled={generationRunning}>
                <option value="youtube">YouTube</option>
                <option value="tiktok">TikTok</option>
                <option value="reels">Reels (Instagram)</option>
              </Select>
            </div>
            <div>
              <Label>Palabras clave objetivo</Label>
              <Input value={targetKeywords} onChange={(e) => setTargetKeywords(e.target.value)} disabled={generationRunning} placeholder='"comprar casa", fondos indexados' />
            </div>
          </div>
          <div>
            <Label>System prompt (opcional)</Label>
            <p className="mb-1 text-[11px] leading-snug text-slate-500">
              Vacío = se usa el prompt por defecto del servidor para la plataforma elegida.
            </p>
            <TextArea value={systemPrompt} onChange={(e) => setSystemPrompt(e.target.value)} disabled={generationRunning} className="min-h-[140px] font-mono text-xs" placeholder="Vacío = usar predeterminado." />
            <div className="mt-2 flex flex-wrap gap-2">
              <Btn type="button" className="border border-slate-500 bg-slate-700 text-slate-200 hover:bg-slate-600" disabled={generationRunning} onClick={() => setSystemPrompt(defaultSystemPrompt)}>
                Pegar prompt predeterminado
              </Btn>
              <Btn type="button" className="bg-white text-slate-900 hover:bg-slate-100" disabled={generationRunning}
                onClick={() => run("Guardar ajustes metadata", async () => {
                  await putJson(`/api/pipeline/metadata-settings`, { work: workApplied, target_platform: targetPlatform, target_keywords: targetKeywords, system_prompt: systemPrompt.trim() });
                  await hydrateSettings();
                })}>
                Guardar ajustes
              </Btn>
            </div>
          </div>
        </div>
      </Section>

      {/* Miniaturas action */}
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-600 bg-gradient-to-r from-slate-800 to-slate-700 px-3 py-2">
        <Btn type="button" className="bg-white text-slate-900 hover:bg-slate-100 disabled:opacity-40"
          disabled={generationRunning || !loaded}
          title={!loaded ? "Genera metadata antes para tener editorial.thumbnail_ideas" : undefined}
          onClick={() => run("Miniaturas → pipeline imágenes", async () => {
            await postJson(`/api/pipeline/metadata/push-thumbnails-to-images`, { work: workApplied });
            await refreshPipeline();
          })}>
          Generar miniaturas → pipeline de imágenes
        </Btn>
        <span className="text-[11px] text-slate-400">
          Copia <code className="rounded bg-slate-700 px-1">editorial.thumbnail_ideas</code> a <code className="rounded bg-slate-700 px-1">pipeline/image_prompts.json</code>.
        </span>
      </div>

      {/* Output */}
      <div className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="text-sm font-semibold tracking-wider capitalize text-white">Salida · metadata.json</div>
          <div className="flex gap-2">
            <Btn type="button" className="border border-slate-600 bg-slate-800 text-slate-200 hover:bg-slate-700" onClick={() => void loadMetadata()}>Recargar desde disco</Btn>
            <div role="button" tabIndex={0} className="cursor-pointer rounded-lg border border-slate-600 bg-slate-800 px-2 py-1 text-xs font-medium text-slate-200 hover:bg-slate-700"
              onClick={() => setFullscreen(true)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setFullscreen(true); } }}>
              Pantalla completa
            </div>
          </div>
        </div>
        <div role="button" tabIndex={0} aria-label="Abrir editor a pantalla completa"
          onClick={() => setFullscreen(true)}
          onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setFullscreen(true); } }}
          className={`min-h-[160px] w-full cursor-pointer rounded-xl border border-slate-600 bg-slate-800 px-3 py-2 text-left font-mono text-xs leading-relaxed shadow-inner outline-none transition hover:border-slate-500 ${jsonText.trim() ? "text-slate-200" : "text-slate-500"}`}>
          <span className="block max-h-[240px] overflow-y-auto whitespace-pre-wrap">
            {jsonText.trim() ? jsonText.slice(0, 800) + (jsonText.length > 800 ? "\n…" : "") : "Tras «Start step» aparecerá JSON (version, platform, editorial, production…)"}
          </span>
        </div>
        <div className="flex flex-wrap gap-2">
          <Btn className="bg-white text-slate-900 hover:bg-slate-100" disabled={generationRunning}
            onClick={() => run("Guardar metadata", handleSave)}>
            Guardar en sesión
          </Btn>
          <span className="self-center text-[11px] text-slate-500">
            Escribe <code className="rounded bg-slate-700 px-1">pipeline/metadata.json</code> y marca el paso como listo.
          </span>
        </div>
      </div>

      {!loaded && !generationRunning && (
        <p className="text-xs text-slate-500">
          Sin metadata en disco. Configura arriba, pulsa <strong className="text-slate-300">Guardar ajustes</strong> y luego <strong className="text-slate-300">Start step</strong>.
        </p>
      )}

      {fullscreen && (
        <div className="fixed inset-0 z-[200] flex items-stretch justify-center bg-slate-950/55 p-2 sm:p-4" role="dialog" aria-modal="true">
          <div className="flex h-[min(calc(100vh-1rem),920px)] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
            <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
              <span className="text-sm font-semibold text-slate-900">pipeline/metadata.json</span>
              <div className="flex gap-2">
                <Btn type="button" className="bg-slate-900 text-white hover:bg-slate-800" disabled={generationRunning}
                  onClick={() => run("Guardar metadata", handleSave)}>
                  Guardar en sesión
                </Btn>
                <Btn type="button" className="bg-white text-slate-800 ring-1 ring-slate-200 hover:bg-slate-50" onClick={() => setFullscreen(false)}>Cerrar</Btn>
              </div>
            </div>
            <textarea ref={modalRef} readOnly={generationRunning} value={jsonText} onChange={(e) => setJsonText(e.target.value)} spellCheck={false}
              className={`min-h-0 flex-1 resize-none border-0 px-4 py-3 font-mono text-sm leading-relaxed outline-none focus:ring-0 ${generationRunning ? "cursor-wait bg-slate-100 text-slate-600" : "bg-white text-slate-900"}`} />
            <p className="shrink-0 border-t border-slate-100 px-4 py-2 text-[11px] text-slate-500">
              <kbd className="rounded bg-slate-100 px-1 font-mono text-[10px]">Esc</kbd> cierra sin guardar.
              {generationRunning && <span className="font-medium text-amber-800"> Generando — solo lectura.</span>}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
