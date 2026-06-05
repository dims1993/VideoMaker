import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react";
import { Btn, Card, StatusBadge } from "../../../components/ui";
import { postJson, putJson } from "../../../services/api";
import type { PipelineState } from "../../../types/pipeline";
import type { Session } from "../../../types/session";
import type { RunFn } from "../types";
import { PromptLibraryPanel } from "../prompt/PromptLibraryPanel";
import { TopicGeneratorPanel } from "../topicGenerator/TopicGeneratorPanel";
import type { TopicIdea } from "../topicGenerator/types";
import type { AnalyzeOutputLanguage } from "../../analyze/transcriptsSession";
import {
  findTopicIndexForSession,
  isTopicSelectedForPrompt,
} from "../topicGenerator/topicSelection";
import { clampPipelineMinutes } from "../pipelineDuration";
import {
  sectionIdsToOpen,
  validatePromptStep,
  type PromptValidationResult,
} from "../prompt/promptCompleteness";
import { openSections } from "./PipelineSection";
import { usePromptLibrary } from "../prompt/usePromptLibrary";
import { useScriptWriterLibrary } from "../scriptWriter/useScriptWriterLibrary";
import { PipelineStepsAside } from "./PipelineStepsAside";
import { PipelineWorkspace } from "./PipelineWorkspace";
import { BodySceneRouterPanel } from "./BodySceneRouterPanel";
import { HookSceneRouterPanel } from "./HookSceneRouterPanel";
import { ImagePromptWriterPanel } from "./ImagePromptWriterPanel";
import { ImagesGenerationPanel } from "./ImagesGenerationPanel";
import { MetadataPanel } from "./MetadataPanel";
import { PackagingPanel } from "./PackagingPanel";
import { RenderDraftPanel } from "./MontagePanels";
import { ScriptWriterPanel } from "./ScriptWriterPanel";
import {
  EditorialAnalyzerPanel,
  NarrativeAnglePanel,
  NarrativePacingPassPanel,
} from "./DiagnosticPipelinePanels";
import { VoiceoversGenerationPanel } from "./VoiceoversGenerationPanel";
import { SubtitleEnginePanel } from "./SubtitleEnginePanel";
import { MusicEnginePanel } from "./MusicEnginePanel";
import { VoiceoverEnginePanel } from "./VoiceoverEnginePanel";

const TOPIC_GENERATOR_STEP_ID = "topic_generator";
const NARRATIVE_ANGLE_STEP_ID = "narrative_angle";
const PACKAGING_STEP_ID = "packaging";
const PROMPT_STEP_ID = "prompt";
const SCRIPT_WRITER_STEP_ID = "script_writer";
const EDITORIAL_ANALYZER_STEP_ID = "editorial_analyzer";
const NARRATIVE_PACING_STEP_ID = "narrative_pacing_pass";
const SUBTITLE_ENGINE_STEP_ID = "subtitle_engine";
const MUSIC_ENGINE_STEP_ID = "music_engine";
const VOICEOVER_ENGINE_STEP_ID = "voiceover_engine";
const METADATA_STEP_ID = "metadata";
const HOOK_SCENE_ROUTER_STEP_ID = "hook_scene_router";
const BODY_SCENE_ROUTER_STEP_ID = "body_scene_router";
const IMAGE_PROMPT_WRITER_STEP_ID = "image_prompt_writer";
const IMAGES_GENERATION_STEP_ID = "images_generation";
const VOICE_STEP_ID = "voiceovers_generation";
const RENDER_DRAFT_STEP_ID = "render_draft";

/** Pasos con panel claro (como Prompt / Script Writer / Metadata). */
const LIGHT_PIPELINE_STEP_IDS = new Set([
  TOPIC_GENERATOR_STEP_ID,
  NARRATIVE_ANGLE_STEP_ID,
  PACKAGING_STEP_ID,
  PROMPT_STEP_ID,
  SCRIPT_WRITER_STEP_ID,
  HOOK_SCENE_ROUTER_STEP_ID,
  BODY_SCENE_ROUTER_STEP_ID,
  METADATA_STEP_ID,
]);

/** Mismo orden que `PIPELINE_STEPS` en backend (sidebar Create). */
const PIPELINE_SIDEBAR_ORDER: string[] = [
  TOPIC_GENERATOR_STEP_ID,
  NARRATIVE_ANGLE_STEP_ID,
  PACKAGING_STEP_ID,
  PROMPT_STEP_ID,
  SCRIPT_WRITER_STEP_ID,
  EDITORIAL_ANALYZER_STEP_ID,
  NARRATIVE_PACING_STEP_ID,
  HOOK_SCENE_ROUTER_STEP_ID,
  BODY_SCENE_ROUTER_STEP_ID,
  IMAGE_PROMPT_WRITER_STEP_ID,
  VOICE_STEP_ID,
  IMAGES_GENERATION_STEP_ID,
  MUSIC_ENGINE_STEP_ID,
  METADATA_STEP_ID,
  SUBTITLE_ENGINE_STEP_ID,
  RENDER_DRAFT_STEP_ID,
  VOICEOVER_ENGINE_STEP_ID,
];

function sortPipelineStepsForSidebar(
  steps: PipelineState["steps"],
): PipelineState["steps"] {
  if (!steps?.length) return steps ?? [];
  const rank = new Map(PIPELINE_SIDEBAR_ORDER.map((id, i) => [id, i]));
  return [...steps].sort((a, b) => {
    const ra = rank.get(a.id) ?? 999;
    const rb = rank.get(b.id) ?? 999;
    if (ra !== rb) return ra - rb;
    return a.id.localeCompare(b.id);
  });
}

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
  setModel: Dispatch<SetStateAction<string>>;
  preset: string;
  setPreset: (v: string) => void;
  previewText: string;
  setPreviewText: (v: string) => void;
  maxChars: number;
  setMaxChars: (v: number) => void;
  maxSeg: number;
  setMaxSeg: (v: number) => void;
  refreshSession?: () => void | Promise<void>;
  onSwitchWork?: (work: string) => void;
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
  refreshSession,
  onSwitchWork,
}: CreatePipelineCardProps) {
  const promptLib = usePromptLibrary();
  const [promptValidation, setPromptValidation] =
    useState<PromptValidationResult | null>(null);
  const [promptSectionRevision, setPromptSectionRevision] = useState(0);
  const scriptLib = useScriptWriterLibrary();
  const [scriptFragmentIndex, setScriptFragmentIndex] = useState<number | null>(
    null,
  );
  const [renderNoMusic, setRenderNoMusic] = useState(false);
  const [nicheTrends, setNicheTrends] = useState("");
  const [topicCount, setTopicCount] = useState(8);
  const [topicIdeas, setTopicIdeas] = useState<TopicIdea[]>([]);
  const [selectedTopicIndex, setSelectedTopicIndex] = useState<number | null>(
    null,
  );
  const [topicGenerating, setTopicGenerating] = useState(false);
  const topicGenerateRef = useRef<(() => void) | null>(null);
  const {
    loadPromptTemplates,
    setPromptTemplateId,
    applyTemplateFromApi,
    setPromptVideoRestrictions,
  } = promptLib;
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
    [promptStepStateVal, promptStepUpdatedVal, pipelineUpdatedVal],
  );

  useEffect(() => {
    hydrateSigRef.current = "";
  }, [workApplied]);

  /** Temas generados en Analyse / Topic Generator (artifact en disco). */
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await fetch(
          `/api/pipeline/topic-generator?work=${encodeURIComponent(workApplied)}`,
        );
        if (!res.ok || cancelled) return;
        const data = (await res.json()) as {
          topics?: TopicIdea[];
          selected_index?: number | null;
          niche_trends?: string;
          output_language?: string;
        };
        if (cancelled) return;
        const syncLang = (code: string | undefined) => {
          if (code === "en" || code === "es") setLang(code);
        };
        syncLang(data.output_language);
        if (Array.isArray(data.topics) && data.topics.length > 0) {
          setTopicIdeas(data.topics);
        }
        if (typeof data.niche_trends === "string" && data.niche_trends) {
          setNicheTrends(data.niche_trends);
        }
        let idx =
          data.selected_index != null && data.selected_index >= 0
            ? data.selected_index
            : null;
        if (
          idx == null &&
          Array.isArray(data.topics) &&
          data.topics.length > 0
        ) {
          idx = findTopicIndexForSession(data.topics, kw, ctx);
        }
        if (idx != null && idx >= 0) {
          setSelectedTopicIndex(idx);
          const t = data.topics?.[idx];
          if (t) {
            setKw(t.title);
            setCtx(t.angle);
            setMinutes(clampPipelineMinutes(t.recommended_duration_minutes));
          }
        }
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [workApplied, setCtx, setKw, setLang, setMinutes]);

  const topicSelectedForPrompt = isTopicSelectedForPrompt(
    selectedTopicIndex,
    topicIdeas,
    kw,
    ctx,
  );

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
        const r = await fetch(
          `/api/pipeline/prompt-artifact?work=${encodeURIComponent(workApplied)}`,
        );
        if (!r.ok || cancelled) return;
        const j = (await r.json()) as {
          exists?: boolean;
          artifact?: Record<string, unknown>;
        };
        if (!j.exists || !j.artifact || cancelled) return;
        const created =
          typeof j.artifact.created_at === "string"
            ? j.artifact.created_at
            : "";
        const cat = j.artifact.catalog;
        const tid =
          cat &&
          typeof cat === "object" &&
          cat !== null &&
          "prompt_template_id" in cat
            ? String(
                (cat as { prompt_template_id?: unknown }).prompt_template_id ??
                  "",
              ).trim()
            : "";
        const swid =
          cat &&
          typeof cat === "object" &&
          cat !== null &&
          "script_writer_template_id" in cat
            ? String(
                (cat as { script_writer_template_id?: unknown })
                  .script_writer_template_id ?? "",
              ).trim()
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
          setKw(topic);
        }
        const vr = j.artifact.video_restrictions;
        if (typeof vr === "string") {
          setPromptVideoRestrictions(vr);
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
    setKw,
    setPromptVideoRestrictions,
    setScriptWriterTemplateId,
    applyScriptWriterTemplateFromApi,
  ]);

  const steps = useMemo(
    () => sortPipelineStepsForSidebar(pipelineState?.steps ?? []),
    [pipelineState?.steps],
  );
  const currentStep = openPipelineStepId
    ? steps.find((s) => s.id === openPipelineStepId)
    : undefined;
  const stepTitle = currentStep?.title ?? openPipelineStepId ?? "";
  const stepState = currentStep?.state ?? "idle";
  const promptStepState =
    steps.find((s) => s.id === PROMPT_STEP_ID)?.state ?? "idle";
  const promptLocked =
    promptStepState === "done" || promptStepState === "running";
  const scriptWriterStepState =
    steps.find((s) => s.id === SCRIPT_WRITER_STEP_ID)?.state ?? "idle";
  const scriptWriterLocked =
    scriptWriterStepState === "done" || scriptWriterStepState === "running";
  const subtitleEngineStepState =
    steps.find((s) => s.id === SUBTITLE_ENGINE_STEP_ID)?.state ?? "idle";
  const musicEngineStepState =
    steps.find((s) => s.id === MUSIC_ENGINE_STEP_ID)?.state ?? "idle";
  const voiceoverEngineStepState =
    steps.find((s) => s.id === VOICEOVER_ENGINE_STEP_ID)?.state ?? "idle";
  const topicGeneratorStepState =
    steps.find((s) => s.id === TOPIC_GENERATOR_STEP_ID)?.state ?? "idle";
  const topicGeneratorLocked = topicGeneratorStepState === "done";
  const narrativeAngleStepState =
    steps.find((s) => s.id === NARRATIVE_ANGLE_STEP_ID)?.state ?? "idle";
  const [narrativeAngleConfirmed, setNarrativeAngleConfirmed] = useState(false);

  const refreshNarrativeAngleMeta = useCallback(async () => {
    try {
      const r = await fetch(
        `/api/pipeline/narrative-angle?work=${encodeURIComponent(workApplied)}`,
      );
      if (!r.ok) {
        setNarrativeAngleConfirmed(false);
        return;
      }
      const j = (await r.json()) as { confirmed?: boolean };
      setNarrativeAngleConfirmed(Boolean(j.confirmed));
    } catch {
      setNarrativeAngleConfirmed(false);
    }
  }, [workApplied]);

  useEffect(() => {
    void refreshNarrativeAngleMeta();
  }, [refreshNarrativeAngleMeta, pipelineState]);

  const narrativeAngleLocked = narrativeAngleConfirmed;
  const editorialAnalyzerStepState =
    steps.find((s) => s.id === EDITORIAL_ANALYZER_STEP_ID)?.state ?? "idle";
  const narrativePacingStepState =
    steps.find((s) => s.id === NARRATIVE_PACING_STEP_ID)?.state ?? "idle";

  const runPipelineStepStart = () =>
    run(`Start step · ${openPipelineStepId}`, async () => {
      if (
        openPipelineStepId !== TOPIC_GENERATOR_STEP_ID &&
        openPipelineStepId !== NARRATIVE_ANGLE_STEP_ID &&
        openPipelineStepId !== PROMPT_STEP_ID &&
        !topicSelectedForPrompt
      ) {
        alert(
          "Selecciona un tema en Topic Generator antes de continuar el pipeline.",
        );
        return;
      }

      if (openPipelineStepId === PROMPT_STEP_ID) {
        if (!topicSelectedForPrompt) {
          alert(
            "Selecciona un tema en Topic Generator antes de ejecutar el paso Prompt.",
          );
          return;
        }
        const validation = validatePromptStep(promptLib);
        if (validation.missing.length > 0) {
          openSections(sectionIdsToOpen(validation));
          setPromptValidation(validation);
          setPromptSectionRevision((n) => n + 1);
          const first = validation.missing[0];
          requestAnimationFrame(() => {
            document
              .getElementById(`prompt-field-${first.id}`)
              ?.scrollIntoView({
                behavior: "smooth",
                block: "center",
              });
          });
          return;
        }
        setPromptValidation(null);
      }

      let resolvedPromptTemplateId = promptLib.promptTemplateId.trim();
      if (openPipelineStepId === PROMPT_STEP_ID && !resolvedPromptTemplateId) {
        const hasContent = !!(
          promptLib.promptSystem.trim() ||
          promptLib.promptUserNarrative.trim() ||
          promptLib.promptName.trim()
        );
        if (hasContent) {
          resolvedPromptTemplateId = await promptLib.saveTemplate();
        }
      }

      // Special validation for Script Writer: if the template was generated by IA
      // and includes sequential fragmenting (or explicit fragment weights), allow
      // Start to proceed. If the template is manual (no chunking info), require
      // that a fragmentation session exists beforehand.
      if (openPipelineStepId === SCRIPT_WRITER_STEP_ID) {
        const swChunking = scriptLib.swChunking || "";
        const swFragmentWeights = (scriptLib.swFragmentWeights || "").trim();
        const iaHasFragmentation =
          swChunking === "sequential_fragments" || swFragmentWeights !== "";
        if (!iaHasFragmentation) {
          // Manual template: ensure fragmentation state exists on disk/session
          try {
            const r = await fetch(
              `/api/script-fragmentation?work=${encodeURIComponent(workApplied)}`,
            );
            if (!r.ok) throw new Error("no-frag");
            const j = await r.json();
            if (!j.exists) {
              alert(
                "Este template parece creado manualmente y no hay fragmentación en la sesión.\nGenera o revisa la fragmentación antes de pulsar Start step, o usa la opción IA para que la genere automáticamente.",
              );
              return;
            }
          } catch {
            alert(
              "No se pudo comprobar el estado de la fragmentación. Asegúrate de tener una sesión de fragmentación válida o usa un template generado por IA.",
            );
            return;
          }
        }
      }

      await postJson(`/api/pipeline/step/rerun`, {
        work: workApplied,
        step_id: openPipelineStepId,
        keywords: kw,
        context: ctx,
        lang,
        minutes,
        provider,
        model,
        ...(openPipelineStepId === PROMPT_STEP_ID
          ? {
              ...(resolvedPromptTemplateId
                ? { prompt_template_id: resolvedPromptTemplateId }
                : {}),
              prompt_topic: kw,
              ...(promptLib.promptVideoRestrictions.trim()
                ? {
                    prompt_video_restrictions:
                      promptLib.promptVideoRestrictions.trim(),
                  }
                : {}),
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
                ? {
                    script_writer_template_id:
                      scriptLib.scriptWriterTemplateId.trim(),
                  }
                : {}),
              ...(scriptFragmentIndex !== null
                ? { script_fragment_index: scriptFragmentIndex }
                : {}),
              ...(promptLib.promptVideoRestrictions.trim()
                ? {
                    prompt_video_restrictions:
                      promptLib.promptVideoRestrictions.trim(),
                  }
                : {}),
            }
          : {}),
        ...(openPipelineStepId === PACKAGING_STEP_ID ||
        openPipelineStepId === METADATA_STEP_ID ||
        openPipelineStepId === HOOK_SCENE_ROUTER_STEP_ID ||
        openPipelineStepId === IMAGE_PROMPT_WRITER_STEP_ID
          ? {
              keywords: kw,
              context: ctx,
              lang,
              minutes,
              provider,
              model,
            }
          : {}),
        ...(openPipelineStepId === RENDER_DRAFT_STEP_ID
          ? { render_no_music: renderNoMusic }
          : {}),
      });
      await refreshPipeline();
      await refreshSession?.();
    });

  const runTopicGeneratorApprove = () =>
    run("Confirmar tema", async () => {
      if (!topicSelectedForPrompt) {
        alert("Selecciona un tema con «Usar este tema» antes de continuar.");
        return;
      }
      if (selectedTopicIndex == null && topicIdeas.length > 0) {
        const inferred = findTopicIndexForSession(topicIdeas, kw, ctx);
        if (inferred != null) {
          await putJson("/api/pipeline/topic-generator/select", {
            work: workApplied,
            selected_index: inferred,
          });
          setSelectedTopicIndex(inferred);
        }
      }
      await postJson("/api/pipeline/topic-generator/approve", {
        work: workApplied,
      });
      await refreshPipeline();
      onOpenStep(NARRATIVE_ANGLE_STEP_ID);
    });

  const runTopicGeneratorResetSelection = () =>
    run("Resetear selección", async () => {
      await postJson("/api/pipeline/topic-generator/reset-selection", {
        work: workApplied,
      });
      setSelectedTopicIndex(null);
      await refreshPipeline();
    });

  return (
    <Card
      title="Create · Pipeline"
      subtitle="Ejecuta la pipeline por pasos (nuevo flujo)."
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Estado
          </span>
          <StatusBadge state={pipelineState?.state ?? "idle"} />
          {pipelineState?.last_error &&
          steps.find((s) => s.id === RENDER_DRAFT_STEP_ID)?.state !== "running" ? (
            <span className="text-sm text-rose-700">
              Error: {pipelineState.last_error}
            </span>
          ) : null}
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
                  prompt_topic: kw,
                  ...(promptLib.promptVideoRestrictions.trim()
                    ? {
                        prompt_video_restrictions:
                          promptLib.promptVideoRestrictions.trim(),
                      }
                    : {}),
                  ...(promptLib.promptTemplateId.trim()
                    ? { prompt_template_id: promptLib.promptTemplateId.trim() }
                    : {}),
                  ...(scriptLib.scriptWriterTemplateId.trim()
                    ? {
                        script_writer_template_id:
                          scriptLib.scriptWriterTemplateId.trim(),
                      }
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
        <PipelineStepsAside
          steps={steps}
          selectedId={openPipelineStepId}
          onSelectStep={onOpenStep}
        />

        <section
          className={
            openPipelineStepId && LIGHT_PIPELINE_STEP_IDS.has(openPipelineStepId)
              ? "rounded-2xl border border-slate-200/80 bg-white p-4 sm:p-5 shadow-sm shadow-slate-200/50"
              : "rounded-2xl border border-slate-700 bg-slate-900 p-4 sm:p-5"
          }
        >
          {openPipelineStepId ? (
            <PipelineWorkspace
              stepTitle={stepTitle}
              stepId={openPipelineStepId}
              stepState={stepState}
              theme={
                LIGHT_PIPELINE_STEP_IDS.has(openPipelineStepId) ? "light" : "dark"
              }
              onBack={onCloseStep}
              startLabel={
                openPipelineStepId === TOPIC_GENERATOR_STEP_ID
                  ? "Continuar al Prompt"
                  : "Start step"
              }
              startDisabled={
                !!busy ||
                stepState === "running" ||
                (openPipelineStepId === TOPIC_GENERATOR_STEP_ID &&
                  (topicGenerating ||
                    !topicSelectedForPrompt ||
                    topicGeneratorLocked))
              }
              headerActions={
                openPipelineStepId === TOPIC_GENERATOR_STEP_ID ? (
                  <>
                    <Btn
                      className="bg-violet-600 text-white hover:bg-violet-500 disabled:opacity-50"
                      disabled={!!busy || topicGenerating}
                      onClick={() => topicGenerateRef.current?.()}
                    >
                      {topicGenerating ? "Generando…" : "Generar temas nuevos"}
                    </Btn>
                    <Btn
                      className="border border-rose-400 bg-white text-rose-700 hover:bg-rose-50 disabled:opacity-50"
                      disabled={!!busy || topicGenerating}
                      onClick={() => void runTopicGeneratorResetSelection()}
                    >
                      Resetear selección
                    </Btn>
                  </>
                ) : undefined
              }
              onStartStep={() =>
                void (openPipelineStepId === TOPIC_GENERATOR_STEP_ID
                  ? runTopicGeneratorApprove()
                  : runPipelineStepStart())
              }
            >
              {openPipelineStepId === TOPIC_GENERATOR_STEP_ID ? (
                <TopicGeneratorPanel
                  run={run}
                  workApplied={workApplied}
                  locked={topicGeneratorLocked}
                  generateRef={topicGenerateRef}
                  onGeneratingChange={setTopicGenerating}
                  onTopicsGenerated={refreshPipeline}
                  stepState={topicGeneratorStepState}
                  provider="anthropic"
                  model=""
                  nicheTrends={nicheTrends}
                  onNicheTrendsChange={setNicheTrends}
                  topicCount={topicCount}
                  onTopicCountChange={setTopicCount}
                  topics={topicIdeas}
                  onTopicsChange={setTopicIdeas}
                  selectedIndex={selectedTopicIndex}
                  onSelectTopic={setSelectedTopicIndex}
                  onSessionLanguageSync={(code: AnalyzeOutputLanguage) =>
                    setLang(code)
                  }
                  onApplyToSession={(topic) => {
                    setKw(topic.title);
                    setCtx(topic.angle);
                    setMinutes(clampPipelineMinutes(topic.recommended_duration_minutes));
                  }}
                  onSpawnProduction={(childWork, topic) => {
                    onSwitchWork?.(childWork);
                    setKw(topic.title);
                    setCtx(topic.angle);
                    setMinutes(clampPipelineMinutes(topic.recommended_duration_minutes));
                    setSelectedTopicIndex(0);
                    onOpenStep(NARRATIVE_ANGLE_STEP_ID);
                    void refreshPipeline();
                  }}
                />
              ) : openPipelineStepId === NARRATIVE_ANGLE_STEP_ID ? (
                <NarrativeAnglePanel
                  run={run}
                  workApplied={workApplied}
                  locked={narrativeAngleLocked}
                  stepState={narrativeAngleStepState}
                  onAfterRun={async () => {
                    await refreshPipeline();
                    await refreshNarrativeAngleMeta();
                  }}
                />
              ) : openPipelineStepId === PACKAGING_STEP_ID ? (
                <PackagingPanel
                  run={run}
                  workApplied={workApplied}
                  lang={lang}
                  kw={kw}
                  ctx={ctx}
                  minutes={minutes}
                  provider={provider}
                  model={model}
                  refreshPipeline={refreshPipeline}
                  packagingStepState={
                    steps.find((s) => s.id === PACKAGING_STEP_ID)?.state ?? "idle"
                  }
                  topicSelected={topicSelectedForPrompt}
                  narrativeAngleDone={narrativeAngleConfirmed}
                />
              ) : openPipelineStepId === PROMPT_STEP_ID ? (
                <PromptLibraryPanel
                  run={run}
                  locked={promptLocked}
                  promptStepState={promptStepState}
                  library={promptLib}
                  workApplied={workApplied}
                  topicSelected={topicSelectedForPrompt}
                  provider={provider}
                  model={model}
                  validationHighlight={promptValidation}
                  sectionRevision={promptSectionRevision}
                  onClearValidation={() => setPromptValidation(null)}
                  onAfterRun={refreshPipeline}
                  sessionLang={lang}
                  sessionMinutes={minutes}
                  sessionKeywords={kw}
                  sessionContext={ctx}
                />
              ) : openPipelineStepId === SCRIPT_WRITER_STEP_ID ? (
                <ScriptWriterPanel
                  run={run}
                  workApplied={workApplied}
                  locked={scriptWriterLocked}
                  scriptStepState={scriptWriterStepState}
                  onAfterRun={refreshPipeline}
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
              ) : openPipelineStepId === EDITORIAL_ANALYZER_STEP_ID ? (
                <EditorialAnalyzerPanel
                  run={run}
                  workApplied={workApplied}
                  locked={false}
                  stepState={editorialAnalyzerStepState}
                  onAfterRun={refreshPipeline}
                  sessionMinutes={clampPipelineMinutes(minutes)}
                />
              ) : openPipelineStepId === NARRATIVE_PACING_STEP_ID ? (
                <NarrativePacingPassPanel
                  run={run}
                  workApplied={workApplied}
                  locked={false}
                  stepState={narrativePacingStepState}
                  onAfterRun={refreshPipeline}
                  sessionMinutes={clampPipelineMinutes(minutes)}
                />
              ) : openPipelineStepId === SUBTITLE_ENGINE_STEP_ID ? (
                <SubtitleEnginePanel
                  run={run}
                  workApplied={workApplied}
                  subtitleStepState={subtitleEngineStepState}
                  refreshPipeline={refreshPipeline}
                />
              ) : openPipelineStepId === MUSIC_ENGINE_STEP_ID ? (
                <MusicEnginePanel
                  run={run}
                  workApplied={workApplied}
                  musicStepState={musicEngineStepState}
                  refreshPipeline={refreshPipeline}
                />
              ) : openPipelineStepId === VOICEOVER_ENGINE_STEP_ID ? (
                <VoiceoverEnginePanel
                  run={run}
                  workApplied={workApplied}
                  voiceoverEngineStepState={voiceoverEngineStepState}
                />
              ) : openPipelineStepId === METADATA_STEP_ID ? (
                <MetadataPanel
                  run={run}
                  workApplied={workApplied}
                  lang={lang}
                  kw={kw}
                  ctx={ctx}
                  minutes={minutes}
                  provider={provider}
                  model={model}
                  refreshPipeline={refreshPipeline}
                  metadataStepState={
                    steps.find((s) => s.id === METADATA_STEP_ID)?.state ??
                    "idle"
                  }
                />
              ) : openPipelineStepId === HOOK_SCENE_ROUTER_STEP_ID ? (
                <HookSceneRouterPanel
                  run={run}
                  workApplied={workApplied}
                  lang={lang}
                  refreshPipeline={refreshPipeline}
                  hookStepState={
                    steps.find((s) => s.id === HOOK_SCENE_ROUTER_STEP_ID)
                      ?.state ?? "idle"
                  }
                />
              ) : openPipelineStepId === BODY_SCENE_ROUTER_STEP_ID ? (
                <BodySceneRouterPanel
                  run={run}
                  workApplied={workApplied}
                  refreshPipeline={refreshPipeline}
                  bodyStepState={
                    steps.find((s) => s.id === BODY_SCENE_ROUTER_STEP_ID)
                      ?.state ?? "idle"
                  }
                />
              ) : openPipelineStepId === IMAGE_PROMPT_WRITER_STEP_ID ? (
                <ImagePromptWriterPanel
                  run={run}
                  workApplied={workApplied}
                  refreshPipeline={refreshPipeline}
                  imagePromptStepState={
                    steps.find((s) => s.id === IMAGE_PROMPT_WRITER_STEP_ID)
                      ?.state ?? "idle"
                  }
                  scriptWriterStepState={
                    steps.find((s) => s.id === SCRIPT_WRITER_STEP_ID)
                      ?.state ?? "idle"
                  }
                />
              ) : openPipelineStepId === IMAGES_GENERATION_STEP_ID ? (
                <ImagesGenerationPanel
                  run={run}
                  workApplied={workApplied}
                  refreshPipeline={refreshPipeline}
                  imagesStepState={
                    steps.find((s) => s.id === IMAGES_GENERATION_STEP_ID)
                      ?.state ?? "idle"
                  }
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
                  voiceStepState={
                    steps.find((s) => s.id === VOICE_STEP_ID)?.state ?? "idle"
                  }
                  refreshSession={refreshSession}
                  refreshPipeline={refreshPipeline}
                />
              ) : openPipelineStepId === RENDER_DRAFT_STEP_ID ? (
                <RenderDraftPanel
                  session={session}
                  renderNoMusic={renderNoMusic}
                  setRenderNoMusic={setRenderNoMusic}
                  workApplied={workApplied}
                  run={run}
                  onRefreshSession={refreshSession}
                  refreshPipeline={refreshPipeline}
                  renderStepState={
                    (steps.find((s) => s.id === RENDER_DRAFT_STEP_ID)?.state ??
                      "idle") as "idle" | "running" | "done" | "error"
                  }
                  renderStepDetail={
                    steps.find((s) => s.id === RENDER_DRAFT_STEP_ID)?.detail
                  }
                  pipelineLastError={pipelineState?.last_error ?? null}
                />
              ) : (
                <div className="rounded-xl border border-slate-700 bg-slate-800 p-4 text-sm text-slate-400">
                  Definiremos este proceso a continuación.
                </div>
              )}
            </PipelineWorkspace>
          ) : (
            <div className="rounded-xl border border-slate-700 bg-slate-800 p-4 text-sm text-slate-400">
              Selecciona un proceso en la columna izquierda para empezar.
            </div>
          )}
        </section>
      </div>
    </Card>
  );
}
