import { useCallback, useEffect, useRef, useState } from "react";
import { Btn, Label, Select, TextArea } from "../../../components/ui";
import { postJson, putJson } from "../../../services/api";
import type { RunFn } from "../types";
import { PipelineSection as Section } from "./PipelineSection";

type RouterMode = "template" | "llm";
type FinanceStyle =
  | "auto"
  | "deep_documentary"
  | "data_minimalist"
  | "financial_noir"
  | "intimate_pov";

export function HookSceneRouterPanel({
  run,
  workApplied,
  refreshPipeline,
  hookStepState,
}: {
  run: RunFn;
  workApplied: string;
  refreshPipeline: () => Promise<void>;
  hookStepState: string;
}) {
  const [mode, setMode] = useState<RouterMode>("template");
  const [financeStyle, setFinanceStyle] = useState<FinanceStyle>("auto");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [narrativePreset, setNarrativePreset] = useState<string | null>(null);
  const [recommendedHint, setRecommendedHint] = useState<string>("");
  const [artifactJson, setArtifactJson] = useState("");
  const [hasArtifact, setHasArtifact] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const modalRef = useRef<HTMLTextAreaElement>(null);
  const generationRunning = hookStepState === "running";

  useEffect(() => {
    if (!fullscreen) return;
    modalRef.current?.focus();
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") setFullscreen(false); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [fullscreen]);

  const loadSettings = useCallback(async () => {
    const r = await fetch(`/api/pipeline/hook-router-settings?work=${encodeURIComponent(workApplied)}`);
    if (!r.ok) return;
    const j = (await r.json()) as {
      mode?: string; finance_style?: string; system_prompt?: string;
      narrative_preset?: string | null; recommended_defaults?: { hint?: string };
    };
    if (j.mode === "template" || j.mode === "llm") setMode(j.mode);
    const fs = j.finance_style;
    if (fs === "auto" || fs === "deep_documentary" || fs === "data_minimalist" || fs === "financial_noir" || fs === "intimate_pov") setFinanceStyle(fs);
    if (j.system_prompt !== undefined) setSystemPrompt(j.system_prompt);
    setNarrativePreset(j.narrative_preset ?? null);
    setRecommendedHint(j.recommended_defaults?.hint ?? "");
  }, [workApplied]);

  const loadArtifact = useCallback(async () => {
    const r = await fetch(`/api/pipeline/hook-router-artifact?work=${encodeURIComponent(workApplied)}`);
    if (!r.ok) return;
    const j = (await r.json()) as { exists?: boolean; artifact?: Record<string, unknown> | null };
    if (j.exists && j.artifact && typeof j.artifact === "object") {
      setArtifactJson(JSON.stringify(j.artifact, null, 2));
      setHasArtifact(true);
    } else {
      setArtifactJson(""); setHasArtifact(false);
    }
  }, [workApplied]);

  useEffect(() => { void loadSettings(); }, [loadSettings]);
  useEffect(() => { void loadArtifact(); }, [loadArtifact, hookStepState, workApplied]);

  const applyRecommended = () => {
    void (async () => {
      const r = await fetch(`/api/pipeline/hook-router-settings?work=${encodeURIComponent(workApplied)}`);
      if (!r.ok) return;
      const j = (await r.json()) as { recommended_defaults?: { mode?: string; finance_style?: string } };
      const rd = j.recommended_defaults;
      if (rd?.mode === "template" || rd?.mode === "llm") setMode(rd.mode);
      const fs = rd?.finance_style;
      if (fs === "auto" || fs === "deep_documentary" || fs === "data_minimalist" || fs === "financial_noir" || fs === "intimate_pov") setFinanceStyle(fs);
    })();
  };

  return (
    <div className="rounded-2xl bg-slate-900 p-4 space-y-3">

      {/* Info */}
      <div className="rounded-xl border border-slate-600 bg-slate-800 px-3 py-2 text-xs text-slate-400">
        <span className="font-semibold text-white">Hook Scene Router</span> analiza el{" "}
        <strong className="text-slate-300">gancho (Acto 1)</strong>, elige una{" "}
        <strong className="text-slate-300">ruta visual</strong> (plantillas finanzas o IA) y alimenta{" "}
        <code className="rounded bg-slate-700 px-1">pipeline/image_prompts.json</code>.{" "}
        <strong className="text-slate-300">Start step</strong> genera{" "}
        <code className="rounded bg-slate-700 px-1">hook_scene_router.json</code>.
      </div>

      {narrativePreset && (
        <p className="text-xs text-slate-400">
          Categoría narrativa (Script Writer): <strong className="text-slate-200">{narrativePreset}</strong>
          {narrativePreset.toLowerCase() === "finanzas" ? " — recomendamos modo plantilla + estilo automático." : null}
        </p>
      )}
      {recommendedHint && <p className="text-[11px] text-violet-400">{recommendedHint}</p>}

      {generationRunning && (
        <div className="rounded-xl border border-amber-500/40 bg-amber-950/30 px-3 py-2 text-xs text-amber-300">
          Ejecutando router…
        </div>
      )}

      {/* Settings */}
      <Section id="hook-settings" title="Modo De Decisión" description="Elige entre plantillas de finanzas o análisis con IA del gancho.">
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <Label>Modo</Label>
              <Select value={mode} disabled={generationRunning} onChange={(e) => setMode(e.target.value as RouterMode)}>
                <option value="template">Plantillas (4 estilos finanzas + clasificador)</option>
                <option value="llm">IA analiza el gancho y devuelve JSON estructurado</option>
              </Select>
            </div>
            <div>
              <Label>Estilo finanzas (plantilla)</Label>
              <Select value={financeStyle} disabled={generationRunning} onChange={(e) => setFinanceStyle(e.target.value as FinanceStyle)}>
                <option value="auto">Automático (keywords en el gancho)</option>
                <option value="deep_documentary">Deep Documentary</option>
                <option value="data_minimalist">Data Minimalist</option>
                <option value="financial_noir">Financial Noir</option>
                <option value="intimate_pov">Intimate POV</option>
              </Select>
            </div>
          </div>
          <Btn type="button" className="border border-slate-500 bg-slate-700 text-slate-200 hover:bg-slate-600" disabled={generationRunning} onClick={applyRecommended}>
            Aplicar valores recomendados (según categoría)
          </Btn>
          <div>
            <Label>System prompt (solo modo IA)</Label>
            <TextArea value={systemPrompt} disabled={generationRunning} onChange={(e) => setSystemPrompt(e.target.value)} className="min-h-[120px] font-mono text-xs" placeholder="Vacío = usar instrucciones internas del router." />
          </div>
          <Btn type="button" className="bg-white text-slate-900 hover:bg-slate-100" disabled={generationRunning}
            onClick={() => run("Guardar ajustes Hook Router", async () => {
              await putJson(`/api/pipeline/hook-router-settings`, { work: workApplied, mode, finance_style: financeStyle, system_prompt: systemPrompt.trim() });
              await loadSettings();
            })}>
            Guardar ajustes
          </Btn>
        </div>
      </Section>

      {/* Push to image prompts */}
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-600 bg-gradient-to-r from-slate-800 to-slate-700 px-3 py-2">
        <Btn type="button" className="bg-white text-slate-900 hover:bg-slate-100 disabled:opacity-40"
          disabled={generationRunning || !hasArtifact}
          onClick={() => run("Router → image_prompts.json", async () => {
            await postJson(`/api/pipeline/hook-router/push-to-image-prompts`, { work: workApplied });
            await refreshPipeline();
          })}>
          Volcar ruta visual → Image Prompt Writer
        </Btn>
        <span className="text-[11px] text-slate-400">Copia keywords y paleta al archivo que consume el paso de imágenes.</span>
      </div>

      {/* Output */}
      <div className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="text-sm font-semibold tracking-wider capitalize text-white">Salida · hook_scene_router.json</div>
          <div className="flex gap-2">
            <Btn type="button" className="border border-slate-600 bg-slate-800 text-slate-200 hover:bg-slate-700" onClick={() => void loadArtifact()}>Recargar</Btn>
            <div role="button" tabIndex={0} className="cursor-pointer rounded-lg border border-slate-600 bg-slate-800 px-2 py-1 text-xs font-medium text-slate-200 hover:bg-slate-700"
              onClick={() => setFullscreen(true)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setFullscreen(true); } }}>
              Pantalla completa
            </div>
          </div>
        </div>
        <div role="button" tabIndex={0} aria-label="Abrir editor a pantalla completa"
          onClick={() => setFullscreen(true)}
          onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setFullscreen(true); } }}
          className={`min-h-[160px] w-full cursor-pointer rounded-xl border border-slate-600 bg-slate-800 px-3 py-2 text-left font-mono text-xs leading-relaxed shadow-inner outline-none transition hover:border-slate-500 ${artifactJson.trim() ? "text-slate-200" : "text-slate-500"}`}>
          <span className="block max-h-[240px] overflow-y-auto whitespace-pre-wrap">
            {artifactJson.trim() ? artifactJson.slice(0, 800) + (artifactJson.length > 800 ? "\n…" : "") : "Tras «Start step» aparecerá classification, visual_direction, bridge_to_images…"}
          </span>
        </div>
      </div>

      {fullscreen && (
        <div className="fixed inset-y-0 left-[280px] right-0 z-[200] flex items-stretch justify-center bg-slate-950/55 p-2 sm:p-4" role="dialog" aria-modal="true">
          <div className="flex h-[min(calc(100vh-1rem),920px)] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
            <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
              <span className="text-sm font-semibold text-slate-900">hook_scene_router.json</span>
              <div className="flex gap-2">
                <Btn type="button" className="bg-slate-900 text-white hover:bg-slate-800" disabled={generationRunning}
                  onClick={() => run("Guardar Hook Router", async () => {
                    let parsed: Record<string, unknown>;
                    try { parsed = JSON.parse(artifactJson) as Record<string, unknown>; }
                    catch { alert("JSON no válido."); return; }
                    await putJson("/api/pipeline/hook-router-artifact", { work: workApplied, artifact: parsed });
                    await loadArtifact(); await refreshPipeline();
                  })}>
                  Guardar
                </Btn>
                <Btn type="button" className="bg-white text-slate-800 ring-1 ring-slate-200 hover:bg-slate-50" onClick={() => setFullscreen(false)}>Cerrar</Btn>
              </div>
            </div>
            <textarea ref={modalRef} readOnly={generationRunning} value={artifactJson} onChange={(e) => setArtifactJson(e.target.value)} spellCheck={false}
              className={`min-h-0 flex-1 resize-none border-0 px-4 py-3 font-mono text-sm leading-relaxed outline-none focus:ring-0 ${generationRunning ? "cursor-wait bg-slate-100 text-slate-600" : "bg-white text-slate-900"}`} />
            <p className="shrink-0 border-t border-slate-100 px-4 py-2 text-[11px] text-slate-500">
              <kbd className="rounded bg-slate-100 px-1 font-mono text-[10px]">Esc</kbd> cierra sin guardar.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
