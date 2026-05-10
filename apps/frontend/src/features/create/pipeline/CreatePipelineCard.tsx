import { useEffect, useMemo, useRef, useState } from "react";
import { Btn, Card, StatusBadge } from "../../../components/ui";
import { postJson } from "../../../services/api";
import type { PipelineState } from "../../../types/pipeline";
import type { Session } from "../../../types/session";
import type { RunFn } from "../types";
import { PromptLibraryPanel } from "../prompt/PromptLibraryPanel";
import { usePromptLibrary } from "../prompt/usePromptLibrary";
import { useScriptWriterLibrary } from "../scriptWriter/useScriptWriterLibrary";
import { PipelineStepsAside } from "./PipelineStepsAside";
import { PipelineWorkspace } from "./PipelineWorkspace";
import { ScriptWriterPanel } from "./ScriptWriterPanel";
import { VoiceoversGenerationPanel } from "./VoiceoversGenerationPanel";

const PROMPT_STEP_ID = "prompt";
const SCRIPT_WRITER_STEP_ID = "script_writer";
const VOICE_STEP_ID = "voiceovers_generation";

export type CreatePipelineCardProps = {
  pipelineState: PipelineState | null;
  openPipelineStepId: string | null;
  onOpenStep: (stepId: string) => void;
  onCloseStep: () => void;
  workApplied: string;
  run: RunFn;
  refreshPipeline: () => Promise<void>;
  session: Session | null;
  busy: string | null;
  kw: string;
  setKw: (v: string) => void;
  ctx: string;
  setCtx: (v: string) => void;
  lang: string;
  setLang: (v: string) => void;
  minutes: number;
  setMinutes: (v: number) => void;
  provider: string;
  setProvider: (v: string) => void;
  model: string;
  setModel: (v: string) => void;
  preset: string;
  setPreset: (v: string) => void;
  previewText: string;
  setPreviewText: (v: string) => void;
  maxChars: number;
  setMaxChars: (v: number) => void;
  maxSeg: number;
  setMaxSeg: (v: number) => void;
};

export function CreatePipelineCard({
  pipelineState,
  openPipelineStepId,
  onOpenStep,
  onCloseStep,
  workApplied,
  run,
  refreshPipeline,
  session,
  busy,
  kw,
  setKw,
  ctx,
  setCtx,
  lang,
  setLang,
  minutes,
  setMinutes,
  provider,
  setProvider,
  model,
  setModel,
  preset,
  setPreset,
  previewText,
  setPreviewText,
  maxChars,
  setMaxChars,
  maxSeg,
  setMaxSeg,
}: CreatePipelineCardProps) {
  const promptLib = usePromptLibrary();
  const scriptLib = useScriptWriterLibrary();
  const [scriptFragmentIndex, setScriptFragmentIndex] = useState<number | null>(null);
  const { loadPromptTemplates, setPromptTemplateId, applyTemplateFromApi, setPromptTopic } = promptLib;
  const {
    loadScriptWriterTemplates,
    setScriptWriterTemplateId,
    applyTemplateFromApi: applyScriptWriterTemplateFromApi,
  } = scriptLib;
  const hydrateSigRef = useRef<string>("");

  const ps = pipelineState?.steps?.find((x) => x.id === PROMPT_STEP_ID);
  const promptStepStateVal = ps?.state ?? "";
  const promptStepUpdatedVal = ps?.updated_at ?? "";
  const pipelineUpdatedVal = pipelineState?.updated_at ?? "";
  const promptStepMeta = useMemo(
    () => `${promptStepStateVal}|${promptStepUpdatedVal}|${pipelineUpdatedVal}`,
    [promptStepStateVal, promptStepUpdatedVal, pipelineUpdatedVal]
  );

  useEffect(() => {
    hydrateSigRef.current = "";
  }, [workApplied]);

  /** Catálogos: una vez por carpeta de trabajo (evita tormenta de peticiones). */
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        await loadPromptTemplates();
        if (cancelled) return;
        await loadScriptWriterTemplates();
      } catch {
        /* red / backend caído */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [workApplied, loadPromptTemplates, loadScriptWriterTemplates]);

  /** Rehidratar desde prompt.json solo cuando cambia el paso Prompt o el manifest. */
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const r = await fetch(`/api/pipeline/prompt-artifact?work=${encodeURIComponent(workApplied)}`);
        if (!r.ok || cancelled) return;
        const j = (await r.json()) as { exists?: boolean; artifact?: Record<string, unknown> };
        if (!j.exists || !j.artifact || cancelled) return;
        const created = typeof j.artifact.created_at === "string" ? j.artifact.created_at : "";
        const cat = j.artifact.catalog;
        const tid =
          cat && typeof cat === "object" && cat !== null && "prompt_template_id" in cat
            ? String((cat as { prompt_template_id?: unknown }).prompt_template_id ?? "").trim()
            : "";
        const swid =
          cat && typeof cat === "object" && cat !== null && "script_writer_template_id" in cat
            ? String((cat as { script_writer_template_id?: unknown }).script_writer_template_id ?? "").trim()
            : "";
        const dedupe = `${workApplied}|${created}|${tid}|${swid}`;
        if (hydrateSigRef.current === dedupe) return;
        hydrateSigRef.current = dedupe;
        if (tid) {
          setPromptTemplateId(tid);
          await applyTemplateFromApi(tid);
        }
        if (cancelled) return;
        if (swid) {
          setScriptWriterTemplateId(swid);
          await applyScriptWriterTemplateFromApi(swid);
        }
        if (cancelled) return;
        const topic = j.artifact.topic;
        if (typeof topic === "string" && topic.trim()) {
          setPromptTopic(topic);
        }
      } catch {
        /* ERR_INSUFFICIENT_RESOURCES / red */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [
    workApplied,
    promptStepMeta,
    setPromptTemplateId,
    applyTemplateFromApi,
    setPromptTopic,
    setScriptWriterTemplateId,
    applyScriptWriterTemplateFromApi,
  ]);

  const steps = pipelineState?.steps ?? [];
  const currentStep = openPipelineStepId ? steps.find((s) => s.id === openPipelineStepId) : undefined;
  const stepTitle = currentStep?.title ?? openPipelineStepId ?? "";
  const stepState = currentStep?.state ?? "idle";
  const promptStepState = steps.find((s) => s.id === PROMPT_STEP_ID)?.state ?? "idle";
  const promptLocked = promptStepState === "done" || promptStepState === "running";
  const scriptWriterStepState = steps.find((s) => s.id === SCRIPT_WRITER_STEP_ID)?.state ?? "idle";
  const scriptWriterLocked = scriptWriterStepState === "done" || scriptWriterStepState === "running";

  return (
    <Card title="Create · Pipeline" subtitle="Ejecuta la pipeline por pasos (nuevo flujo).">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Estado</span>
          <StatusBadge state={pipelineState?.state ?? "idle"} />
          {pipelineState?.last_error ? <span className="text-sm text-rose-700">Error: {pipelineState.last_error}</span> : null}
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <Btn
            className="bg-emerald-600 text-white hover:bg-emerald-700"
            onClick={() =>
              run("Start pipeline", async () => {
                await postJson(`/api/pipeline/start`, {
                  work: workApplied,
                  keywords: kw,
                  context: ctx,
                  lang,
                  minutes,
                  provider,
                  model,
                  prompt_topic: promptLib.promptTopic,
                  ...(promptLib.promptTemplateId.trim() ? { prompt_template_id: promptLib.promptTemplateId.trim() } : {}),
                  ...(scriptLib.scriptWriterTemplateId.trim()
                    ? { script_writer_template_id: scriptLib.scriptWriterTemplateId.trim() }
                    : {}),
                });
                await refreshPipeline();
              })
            }
          >
            Start
          </Btn>
          <Btn
            className="bg-rose-600 text-white hover:bg-rose-700"
            onClick={() =>
              run("Stop pipeline", async () => {
                await postJson(`/api/pipeline/stop`, { work: workApplied });
                await refreshPipeline();
              })
            }
          >
            Stop
          </Btn>
          <Btn
            className="bg-white text-slate-900 ring-1 ring-slate-200 hover:bg-slate-50"
            onClick={() =>
              run("Reset pipeline", async () => {
                await postJson(`/api/pipeline/reset`, { work: workApplied });
                onCloseStep();
                await refreshPipeline();
              })
            }
          >
            Reset
          </Btn>
        </div>
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-[280px_1fr]">
        <PipelineStepsAside steps={steps} selectedId={openPipelineStepId} onSelectStep={onOpenStep} />

        <section className="rounded-2xl border border-slate-200 bg-white p-4">
          {openPipelineStepId ? (
            <PipelineWorkspace
              stepTitle={stepTitle}
              stepId={openPipelineStepId}
              stepState={stepState}
              onBack={onCloseStep}
              startDisabled={!!busy || stepState === "running"}
              onStartStep={() =>
                void run(`Start step · ${openPipelineStepId}`, async () => {
                  await postJson(`/api/pipeline/step/rerun`, {
                    work: workApplied,
                    step_id: openPipelineStepId,
                    ...(openPipelineStepId === PROMPT_STEP_ID
                      ? {
                          ...(promptLib.promptTemplateId.trim()
                            ? { prompt_template_id: promptLib.promptTemplateId.trim() }
                            : {}),
                          prompt_topic: promptLib.promptTopic,
                        }
                      : {}),
                    ...(openPipelineStepId === SCRIPT_WRITER_STEP_ID
                      ? {
                          keywords: kw,
                          context: ctx,
                          lang,
                          minutes,
                          provider,
                          model,
                          ...(scriptLib.scriptWriterTemplateId.trim()
                            ? { script_writer_template_id: scriptLib.scriptWriterTemplateId.trim() }
                            : {}),
                          ...(scriptFragmentIndex !== null ? { script_fragment_index: scriptFragmentIndex } : {}),
                        }
                      : {}),
                  });
                  await refreshPipeline();
                })
              }
            >
              {openPipelineStepId === PROMPT_STEP_ID ? (
                <PromptLibraryPanel run={run} locked={promptLocked} promptStepState={promptStepState} library={promptLib} />
              ) : openPipelineStepId === SCRIPT_WRITER_STEP_ID ? (
                <ScriptWriterPanel
                  run={run}
                  workApplied={workApplied}
                  locked={scriptWriterLocked}
                  scriptStepState={scriptWriterStepState}
                  library={scriptLib}
                  kw={kw}
                  setKw={setKw}
                  ctx={ctx}
                  setCtx={setCtx}
                  lang={lang}
                  setLang={setLang}
                  minutes={minutes}
                  setMinutes={setMinutes}
                  provider={provider}
                  setProvider={setProvider}
                  model={model}
                  setModel={setModel}
                  scriptFragmentIndex={scriptFragmentIndex}
                  setScriptFragmentIndex={setScriptFragmentIndex}
                  refreshPipeline={refreshPipeline}
                />
              ) : openPipelineStepId === VOICE_STEP_ID ? (
                <VoiceoversGenerationPanel
                  session={session}
                  workApplied={workApplied}
                  busy={busy}
                  run={run}
                  preset={preset}
                  setPreset={setPreset}
                  previewText={previewText}
                  setPreviewText={setPreviewText}
                  maxChars={maxChars}
                  setMaxChars={setMaxChars}
                  maxSeg={maxSeg}
                  setMaxSeg={setMaxSeg}
                />
              ) : (
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">Definiremos este proceso a continuación.</div>
              )}
            </PipelineWorkspace>
          ) : (
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">Selecciona un proceso en la columna izquierda para empezar.</div>
          )}
        </section>
      </div>
    </Card>
  );
}
