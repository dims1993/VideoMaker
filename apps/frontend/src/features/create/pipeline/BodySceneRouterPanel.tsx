import { useCallback, useEffect, useRef, useState } from "react";
import { Btn } from "../../../components/ui";
import { putJson } from "../../../services/api";
import type { RunFn } from "../types";
import { BodyRouterDiagnosticsPanel } from "./BodyRouterDiagnosticsPanel";
import { PipelineStepConfirmBar } from "./PipelineStepConfirmBar";
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
  const [diagRefresh, setDiagRefresh] = useState(0);
  const [fullscreen, setFullscreen] = useState(false);
  const modalRef = useRef<HTMLTextAreaElement>(null);
  const generationRunning = bodyStepState === "running";

  useEffect(() => {
    if (!fullscreen) return;
    modalRef.current?.focus();
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setFullscreen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [fullscreen]);

  const loadArtifact = useCallback(async () => {
    const r = await fetch(
      `/api/pipeline/body-router-artifact?work=${encodeURIComponent(workApplied)}`,
    );
    if (!r.ok) return;
    const j = (await r.json()) as {
      exists?: boolean;
      artifact?: Record<string, unknown> | null;
    };
    if (j.exists && j.artifact && typeof j.artifact === "object") {
      setArtifactJson(JSON.stringify(j.artifact, null, 2));
      setHasArtifact(true);
    } else {
      setArtifactJson("");
      setHasArtifact(false);
    }
  }, [workApplied]);

  useEffect(() => {
    void loadArtifact();
  }, [loadArtifact, bodyStepState, workApplied]);

  const saveArtifact = async () => {
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(artifactJson) as Record<string, unknown>;
    } catch {
      alert("JSON no válido. Revisa el formato antes de guardar.");
      return;
    }
    await putJson("/api/pipeline/body-router-artifact", {
      work: workApplied,
      artifact: parsed,
    });
    await loadArtifact();
    await refreshPipeline();
    setDiagRefresh((n) => n + 1);
  };

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-sky-100 bg-sky-50/80 px-3 py-2 text-xs text-slate-700">
        <span className="font-semibold text-sky-800">Body Scene Router</span> define{" "}
        <strong className="text-slate-800">macro_beats</strong> en Actos 2-4 (prioridad B-roll / insert).
        Aplica <strong>6 reglas visuales</strong>: zonas por pilar (cálido / pantallas / tensión), ancla vs
        soporte, ritmo lento (4–6 s soporte, 5–8 s ancla), subtexto emocional (no literal), composición para
        animación y paleta por zona. Hereda estilo del Hook Router. El Image Prompt Writer lee este JSON
        junto al hook. Guardado en{" "}
        <code className="rounded bg-white px-1 text-slate-700">pipeline/body_scene_router.json</code>.
      </div>

      <PipelineStepConfirmBar
        stepId="body_scene_router"
        stepLabel="Body Scene Router"
        workApplied={workApplied}
        stepState={bodyStepState}
        run={run}
        onAfterRun={async () => {
          await refreshPipeline();
          setDiagRefresh((n) => n + 1);
        }}
      />

      <BodyRouterDiagnosticsPanel
        workApplied={workApplied}
        refreshToken={`${bodyStepState}-${diagRefresh}-${hasArtifact}`}
      />

      {generationRunning && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          Ejecutando Body Scene Router…
        </div>
      )}

      <Section
        id="body-structure"
        title="Estructura del JSON"
        description="Campos que genera el Body Scene Router en el artefacto de salida."
        theme="light"
      >
        <ul className="list-disc space-y-0.5 pl-4 text-[11px] text-slate-600">
          <li>
            <code className="rounded bg-slate-100 px-1 text-slate-800">body_visual_plan</code> — pilares,
            anclas por pilar, ritmo y color
          </li>
          <li>
            <code className="rounded bg-slate-100 px-1 text-slate-800">visual_pillar</code> por beat —
            pillar_1 cálido · pillar_2 pantallas · pillar_3 contraste
          </li>
          <li>
            <code className="rounded bg-slate-100 px-1 text-slate-800">is_anchor_shot</code> — plano
            memorable (prompt rico) vs soporte (limpio)
          </li>
          <li>
            <code className="rounded bg-slate-100 px-1 text-slate-800">visual_style_inherited</code> —
            estilo heredado del Hook Router
          </li>
          <li>
            <code className="rounded bg-slate-100 px-1 text-slate-800">style_consistency</code> — fps,
            iluminación, paleta, tipografía, música
          </li>
          <li>
            <code className="rounded bg-slate-100 px-1 text-slate-800">macro_beats[]</code> — un plano por
            viñeta narrativa (<code className="text-[10px]">text_anchor</code>, <code className="text-[10px]">track</code>,{" "}
            <code className="text-[10px]">composition_hint</code>)
          </li>
          <li>
            <code className="rounded bg-slate-100 px-1 text-slate-800">macro_beat_track_summary</code> — conteo
            insert vs avatar
          </li>
          <li>
            <code className="rounded bg-slate-100 px-1 text-slate-800">diagnostics</code> — alertas de fragmentos,
            duplicados y densidad vs audio
          </li>
          <li>
            <code className="rounded bg-slate-100 px-1 text-slate-800">llm_enrichment</code> — salida cruda del LLM
            antes de finalizar beats
          </li>
        </ul>
      </Section>

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white p-4 shadow-sm shadow-slate-200/50 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="text-sm font-semibold tracking-wider capitalize text-slate-900">
            Salida · body_scene_router.json
          </div>
          <div className="flex flex-wrap gap-2">
            <Btn
              type="button"
              className="border border-slate-200 bg-slate-100 text-slate-900 hover:bg-slate-200"
              onClick={() => void loadArtifact()}
            >
              Recargar
            </Btn>
            <Btn
              type="button"
              className="bg-slate-900 text-white hover:bg-slate-800 disabled:opacity-40"
              disabled={generationRunning || !artifactJson.trim()}
              onClick={() => run("Guardar Body Scene Router", saveArtifact)}
            >
              Guardar y marcar listo
            </Btn>
            <div
              role="button"
              tabIndex={0}
              className="cursor-pointer rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50"
              onClick={() => setFullscreen(true)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setFullscreen(true);
                }
              }}
            >
              Pantalla completa
            </div>
          </div>
        </div>
        <div
          role="button"
          tabIndex={0}
          aria-label="Abrir editor a pantalla completa"
          onClick={() => setFullscreen(true)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              setFullscreen(true);
            }
          }}
          className={`min-h-[160px] w-full cursor-pointer rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-left font-mono text-xs leading-relaxed shadow-sm outline-none transition hover:border-slate-300 ${artifactJson.trim() ? "text-slate-900" : "text-slate-500"}`}
        >
          <span className="block max-h-[240px] overflow-y-auto whitespace-pre-wrap">
            {artifactJson.trim()
              ? artifactJson.slice(0, 800) + (artifactJson.length > 800 ? "\n…" : "")
              : "Tras «Start step» verás acts[], scene_prompts por coste, B-ROLL y prompts para imágenes…"}
          </span>
        </div>
      </div>

      {fullscreen && (
        <div
          className="fixed inset-y-0 left-[280px] right-0 z-[200] flex items-stretch justify-center bg-slate-950/55 p-2 sm:p-4"
          role="dialog"
          aria-modal="true"
        >
          <div className="flex h-[min(calc(100vh-1rem),920px)] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
            <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
              <span className="text-sm font-semibold text-slate-900">body_scene_router.json</span>
              <div className="flex gap-2">
                <Btn
                  type="button"
                  className="bg-slate-900 text-white hover:bg-slate-800"
                  disabled={generationRunning}
                  onClick={() => run("Guardar Body Scene Router", saveArtifact)}
                >
                  Guardar y marcar listo
                </Btn>
                <Btn
                  type="button"
                  className="bg-white text-slate-800 ring-1 ring-slate-200 hover:bg-slate-50"
                  onClick={() => setFullscreen(false)}
                >
                  Cerrar
                </Btn>
              </div>
            </div>
            <textarea
              ref={modalRef}
              readOnly={generationRunning}
              value={artifactJson}
              onChange={(e) => setArtifactJson(e.target.value)}
              spellCheck={false}
              className={`min-h-0 flex-1 resize-none border-0 px-4 py-3 font-mono text-sm leading-relaxed outline-none focus:ring-0 ${generationRunning ? "cursor-wait bg-slate-100 text-slate-600" : "bg-white text-slate-900"}`}
            />
            <p className="shrink-0 border-t border-slate-100 px-4 py-2 text-[11px] text-slate-500">
              <kbd className="rounded bg-slate-100 px-1 font-mono text-[10px]">Esc</kbd> cierra sin
              guardar.
              {!hasArtifact && (
                <span className="text-amber-700"> Aún no hay artefacto en disco.</span>
              )}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
