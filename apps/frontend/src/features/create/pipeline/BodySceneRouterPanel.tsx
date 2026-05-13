import { useCallback, useEffect, useRef, useState } from "react";
import { Btn } from "../../../components/ui";
import { putJson } from "../../../services/api";
import type { RunFn } from "../types";
import { PipelineSection as Section } from "./PipelineSection";

export function BodySceneRouterPanel({
  run,
  workApplied,
  refreshPipeline,
  bodyStepState,
}: {
  run: RunFn;
  workApplied: string;
  refreshPipeline: () => Promise<void>;
  bodyStepState: string;
}) {
  const [artifactJson, setArtifactJson] = useState("");
  const [hasArtifact, setHasArtifact] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const modalRef = useRef<HTMLTextAreaElement>(null);
  const generationRunning = bodyStepState === "running";

  useEffect(() => {
    if (!fullscreen) return;
    modalRef.current?.focus();
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") setFullscreen(false); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [fullscreen]);

  const loadArtifact = useCallback(async () => {
    const r = await fetch(`/api/pipeline/body-router-artifact?work=${encodeURIComponent(workApplied)}`);
    if (!r.ok) return;
    const j = (await r.json()) as { exists?: boolean; artifact?: Record<string, unknown> | null };
    if (j.exists && j.artifact && typeof j.artifact === "object") {
      setArtifactJson(JSON.stringify(j.artifact, null, 2));
      setHasArtifact(true);
    } else {
      setArtifactJson(""); setHasArtifact(false);
    }
  }, [workApplied]);

  useEffect(() => { void loadArtifact(); }, [loadArtifact, bodyStepState, workApplied]);

  const saveArtifact = async () => {
    let parsed: Record<string, unknown>;
    try { parsed = JSON.parse(artifactJson) as Record<string, unknown>; }
    catch { alert("JSON no válido. Revisa el formato antes de guardar."); return; }
    await putJson("/api/pipeline/body-router-artifact", { work: workApplied, artifact: parsed });
    await loadArtifact();
    await refreshPipeline();
  };

  return (
    <div className="rounded-2xl bg-slate-900 p-4 space-y-3">

      {/* Info */}
      <div className="rounded-xl border border-slate-600 bg-slate-800 px-3 py-2 text-xs text-slate-400">
        <span className="font-semibold text-white">Body Scene Router</span> mapea los{" "}
        <strong className="text-slate-300">Actos 2-4</strong> a rutas visuales: paleta, scene_prompts por coste, B-ROLL
        sugerido y prompts para el Image Prompt Writer. Hereda el estilo visual del{" "}
        <strong className="text-slate-300">Hook Scene Router</strong>. El resultado se guarda en{" "}
        <code className="rounded bg-slate-700 px-1">pipeline/body_scene_router.json</code>.
      </div>

      {generationRunning && (
        <div className="rounded-xl border border-amber-500/40 bg-amber-950/30 px-3 py-2 text-xs text-amber-300">
          Ejecutando Body Scene Router…
        </div>
      )}

      {/* Structure reference */}
      <Section id="body-structure" title="Estructura Del JSON" description="Campos que genera el Body Scene Router en el artefacto de salida.">
        <ul className="list-disc pl-4 space-y-0.5 text-[11px] text-slate-400">
          <li><code className="rounded bg-slate-700 px-1">visual_style_inherited</code> — estilo heredado del Hook Router</li>
          <li><code className="rounded bg-slate-700 px-1">style_consistency</code> — fps, iluminación, paleta, tipografía, música</li>
          <li><code className="rounded bg-slate-700 px-1">acts[]</code> — Acto 2 (Promesa), Acto 3 con 5 costes, Acto 4 (Cierre)</li>
          <li><code className="rounded bg-slate-700 px-1">acts[].costs[].scene_prompts</code> — prompts IA por escena (inglés, Midjourney/SD)</li>
          <li><code className="rounded bg-slate-700 px-1">acts[].costs[].b_roll_suggestions</code> — descripciones de plano por escena</li>
          <li><code className="rounded bg-slate-700 px-1">acts[].costs[].data_overlay</code> — texto y tipografía de superposición</li>
          <li><code className="rounded bg-slate-700 px-1">full_body_image_prompts[]</code> — todos los prompts del cuerpo para Image Prompt Writer</li>
        </ul>
      </Section>

      {/* Output */}
      <div className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="text-sm font-semibold tracking-wider capitalize text-white">Salida · body_scene_router.json</div>
          <div className="flex gap-2">
            <Btn type="button" className="border border-slate-600 bg-slate-800 text-slate-200 hover:bg-slate-700" onClick={() => void loadArtifact()}>Recargar</Btn>
            <Btn type="button" className="bg-white text-slate-900 hover:bg-slate-100 disabled:opacity-40"
              disabled={generationRunning || !artifactJson.trim()}
              onClick={() => run("Guardar Body Scene Router", saveArtifact)}>
              Guardar y marcar listo
            </Btn>
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
            {artifactJson.trim() ? artifactJson.slice(0, 800) + (artifactJson.length > 800 ? "\n…" : "") : "Tras «Start step» verás acts[], scene_prompts por coste, B-ROLL y prompts para imágenes…"}
          </span>
        </div>
      </div>

      {fullscreen && (
        <div className="fixed inset-y-0 left-[280px] right-0 z-[200] flex items-stretch justify-center bg-slate-950/55 p-2 sm:p-4" role="dialog" aria-modal="true">
          <div className="flex h-[min(calc(100vh-1rem),920px)] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
            <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
              <span className="text-sm font-semibold text-slate-900">body_scene_router.json</span>
              <div className="flex gap-2">
                <Btn type="button" className="bg-slate-900 text-white hover:bg-slate-800" disabled={generationRunning}
                  onClick={() => run("Guardar Body Scene Router", saveArtifact)}>
                  Guardar y marcar listo
                </Btn>
                <Btn type="button" className="bg-white text-slate-800 ring-1 ring-slate-200 hover:bg-slate-50" onClick={() => setFullscreen(false)}>Cerrar</Btn>
              </div>
            </div>
            <textarea ref={modalRef} readOnly={generationRunning} value={artifactJson} onChange={(e) => setArtifactJson(e.target.value)} spellCheck={false}
              className={`min-h-0 flex-1 resize-none border-0 px-4 py-3 font-mono text-sm leading-relaxed outline-none focus:ring-0 ${generationRunning ? "cursor-wait bg-slate-100 text-slate-600" : "bg-white text-slate-900"}`} />
            <p className="shrink-0 border-t border-slate-100 px-4 py-2 text-[11px] text-slate-500">
              <kbd className="rounded bg-slate-100 px-1 font-mono text-[10px]">Esc</kbd> cierra sin guardar.
              {!hasArtifact && <span className="text-amber-700"> Aún no hay artefacto en disco.</span>}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
