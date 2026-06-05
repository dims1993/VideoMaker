import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Btn, Label, Select, TextArea } from "../../../components/ui";
import { postJson, putJson } from "../../../services/api";
import type { RunFn } from "../types";
import { PipelineStepConfirmBar } from "./PipelineStepConfirmBar";
import { PipelineSection as Section } from "./PipelineSection";
import { InferredFieldShell } from "../prompt/InferredFieldShell";
import { inferredControlClass, inferredPanelClass } from "../prompt/promptFieldStyles";
import {
  messageForHookPushToImagePrompts,
  type HookPushToImagePromptsResult,
} from "./hookRouterPushFeedback";

type RouterMode = "template" | "llm";
type FinanceStyle =
  | "auto"
  | "deep_documentary"
  | "data_minimalist"
  | "financial_noir"
  | "intimate_pov";
type HookPlatform = "auto" | "tiktok" | "youtube_shorts" | "reels" | "youtube";
type VisualEnergy = "auto" | "high" | "medium" | "low";
type SystemPromptSource = "internal" | "manual";

type TalkingHeadDelay = "auto" | "20" | "25" | "30";

type MicroBeat = {
  index?: number;
  start_sec?: number;
  end_sec?: number;
  sequence_block?: string;
  shot_distance?: string;
  shot_angle?: string;
  color_temperature?: string;
  light_quality?: string;
  camera_motion?: string;
  camera_motion_direction?: string;
  camera_motion_note?: string;
  rhythm_tier?: string;
  rhythm_note?: string;
  shot_hierarchy?: string;
  is_anchor_shot?: boolean;
  new_information_layer?: string;
  purpose?: string;
  pacing_role?: string;
  intensity?: number;
  emotion?: string;
  scene_type?: string;
  narrator_visible?: boolean;
  text_overlay_content?: string;
  visual_description?: string;
  audio?: {
    music_energy?: string;
    sfx?: string[];
    silence?: boolean;
    impact_beat?: boolean;
  };
  transition_to_next?: {
    type?: string;
    duration_frames?: number;
    sync_audio_impact?: boolean;
  };
  viewer_state?: {
    attention?: number;
    curiosity?: number;
    cognitive_load?: number;
  };
  viewer_pacing_hint?: string;
};

export function HookSceneRouterPanel({
  run,
  workApplied,
  lang,
  refreshPipeline,
  hookStepState,
}: {
  run: RunFn;
  workApplied: string;
  lang: string;
  refreshPipeline: () => Promise<void>;
  hookStepState: string;
}) {
  const [mode, setMode] = useState<RouterMode>("llm");
  const [financeStyle, setFinanceStyle] = useState<FinanceStyle>("auto");
  const [platform, setPlatform] = useState<HookPlatform>("auto");
  const [visualEnergy, setVisualEnergy] = useState<VisualEnergy>("auto");
  const [resolvedPlatform, setResolvedPlatform] = useState("");
  const [resolvedEnergy, setResolvedEnergy] = useState("");
  const [talkingHeadAfter, setTalkingHeadAfter] = useState<TalkingHeadDelay>("auto");
  const [resolvedTalkingHeadAfter, setResolvedTalkingHeadAfter] = useState(25);
  const [systemPromptSource, setSystemPromptSource] =
    useState<SystemPromptSource>("internal");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [defaultSystemPrompt, setDefaultSystemPrompt] = useState("");
  const [narrativePreset, setNarrativePreset] = useState<string | null>(null);
  const [recommendedHint, setRecommendedHint] = useState("");
  const [artifactJson, setArtifactJson] = useState("");
  const [hasArtifact, setHasArtifact] = useState(false);
  const [pushFeedback, setPushFeedback] = useState<{
    kind: "success" | "error";
    message: string;
  } | null>(null);
  const [fullscreen, setFullscreen] = useState(false);
  const modalRef = useRef<HTMLTextAreaElement>(null);
  const pushFeedbackTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const generationRunning = hookStepState === "running";

  useEffect(() => {
    return () => {
      if (pushFeedbackTimerRef.current) clearTimeout(pushFeedbackTimerRef.current);
    };
  }, []);

  const showPushFeedback = (next: { kind: "success" | "error"; message: string } | null) => {
    if (pushFeedbackTimerRef.current) {
      clearTimeout(pushFeedbackTimerRef.current);
      pushFeedbackTimerRef.current = null;
    }
    setPushFeedback(next);
    if (next?.kind === "success") {
      pushFeedbackTimerRef.current = setTimeout(() => setPushFeedback(null), 12_000);
    }
  };

  const beatsPreview = useMemo(() => {
    if (!artifactJson.trim()) return [] as MicroBeat[];
    try {
      const parsed = JSON.parse(artifactJson) as { micro_beats?: MicroBeat[] };
      return Array.isArray(parsed.micro_beats) ? parsed.micro_beats : [];
    } catch {
      return [];
    }
  }, [artifactJson]);

  const retentionSummary = useMemo(() => {
    if (!artifactJson.trim()) return null;
    try {
      const parsed = JSON.parse(artifactJson) as {
        retention_analysis?: {
          primary_hook_class?: string;
          patterns_detected?: string[];
          scroll_stop_rationale?: string;
        };
        intensity_curve?: number[];
        platform_pacing?: {
          label?: string;
          pacing_profile?: string;
          escalation_style?: string;
          breathing_room?: boolean;
          tension_release_cycles?: boolean;
          guidance?: string;
        };
        intensity_arc?: {
          peak_intensity?: number;
          peak_beat_index?: number;
          shape?: string;
          pacing_profile?: string;
        };
        audio_design?: {
          music_energy?: string;
          sfx?: string[];
          silence_before_payoff?: boolean;
        };
        narrator_visibility?: {
          talking_head_allowed_after_sec?: number;
          entire_hook_visual_only?: boolean;
          replacements_applied?: number;
        };
        transition_rhythm?: {
          types_used?: Record<string, number>;
          transition_count?: number;
        };
        viewer_state_tracking?: {
          attention_curve?: number[];
          curiosity_curve?: number[];
          cognitive_load_curve?: number[];
          dropoff_risk_beat_indices?: number[];
          boredom_risk_beat_indices?: number[];
          pacing_recommendations?: string[];
        };
        image_prompt_policy?: {
          style?: string;
          anti_stock?: boolean;
          repairs_applied?: number;
        };
        visual_direction?: { beat_count?: number; total_hook_duration_sec?: number };
        visual_sequence_plan?: {
          arc?: string;
          block_counts?: Record<string, number>;
          emotional_tone?: string;
          motif_thread?: string;
          violations_fixed?: number;
          color_language?: {
            chromatic_argument?: string;
            protagonist_world?: { light_language?: string };
            contrast_world?: { light_language?: string };
          };
          narrative_rhythm?: {
            tier_counts?: Record<string, number>;
            duration_range_s?: number[];
          };
        };
        narrative_rhythm?: {
          tier_counts?: Record<string, number>;
          duration_range_s?: number[];
        };
      };
      return parsed;
    } catch {
      return null;
    }
  }, [artifactJson]);

  useEffect(() => {
    if (!fullscreen) return;
    modalRef.current?.focus();
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setFullscreen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [fullscreen]);

  const loadSettings = useCallback(async () => {
    const params = new URLSearchParams({
      work: workApplied,
      lang,
      preview_platform: platform,
      preview_visual_energy: visualEnergy,
    });
    const r = await fetch(`/api/pipeline/hook-router-settings?${params.toString()}`);
    if (!r.ok) return;
    const j = (await r.json()) as {
      mode?: string;
      finance_style?: string;
      platform?: string;
      visual_energy?: string;
      resolved_platform?: string;
      resolved_visual_energy?: string;
      system_prompt?: string;
      system_prompt_source?: string;
      default_system_prompt?: string;
      talking_head_after_sec?: string | number;
      resolved_talking_head_after_sec?: number;
      narrative_preset?: string | null;
      recommended_defaults?: { hint?: string };
    };
    if (j.mode === "template" || j.mode === "llm") setMode(j.mode);
    const fs = j.finance_style;
    if (
      fs === "auto" ||
      fs === "deep_documentary" ||
      fs === "data_minimalist" ||
      fs === "financial_noir" ||
      fs === "intimate_pov"
    )
      setFinanceStyle(fs);
    const pl = j.platform;
    if (
      pl === "auto" ||
      pl === "tiktok" ||
      pl === "youtube_shorts" ||
      pl === "reels" ||
      pl === "youtube"
    )
      setPlatform(pl);
    const ve = j.visual_energy;
    if (ve === "auto" || ve === "high" || ve === "medium" || ve === "low")
      setVisualEnergy(ve);
    if (j.resolved_platform) setResolvedPlatform(j.resolved_platform);
    if (j.resolved_visual_energy) setResolvedEnergy(j.resolved_visual_energy);
    const th = String(j.talking_head_after_sec ?? "auto").toLowerCase();
    if (th === "20") setTalkingHeadAfter("20");
    else if (th === "25") setTalkingHeadAfter("25");
    else if (th === "30") setTalkingHeadAfter("30");
    else setTalkingHeadAfter("auto");
    if (j.resolved_talking_head_after_sec != null) {
      setResolvedTalkingHeadAfter(j.resolved_talking_head_after_sec);
    }
    if (j.system_prompt_source === "manual" || j.system_prompt_source === "internal") {
      setSystemPromptSource(j.system_prompt_source);
    }
    if (j.system_prompt !== undefined) setSystemPrompt(j.system_prompt);
    if (j.default_system_prompt !== undefined) {
      setDefaultSystemPrompt(j.default_system_prompt);
    }
    setNarrativePreset(j.narrative_preset ?? null);
    setRecommendedHint(j.recommended_defaults?.hint ?? "");
  }, [workApplied, lang, platform, visualEnergy]);

  const loadArtifact = useCallback(async () => {
    const r = await fetch(
      `/api/pipeline/hook-router-artifact?work=${encodeURIComponent(workApplied)}`,
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
    void loadSettings();
  }, [loadSettings]);
  useEffect(() => {
    void loadArtifact();
  }, [loadArtifact, workApplied]);
  useEffect(() => {
    if (hookStepState === "done") void loadArtifact();
  }, [hookStepState, loadArtifact]);

  const applyRecommended = () => {
    setMode("llm");
    setFinanceStyle("auto");
    setPlatform("auto");
    setVisualEnergy("auto");
    setSystemPromptSource("internal");
  };

  const handleLoadDefaultIntoManual = () => {
    if (defaultSystemPrompt.trim()) {
      setSystemPrompt(defaultSystemPrompt);
    }
  };

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-violet-200 bg-violet-50/80 px-3 py-2 text-xs text-slate-700">
        <span className="font-semibold text-violet-700">Hook Scene Router (retención)</span>{" "}
        analiza el <strong className="text-slate-700">gancho (Acto 1)</strong> con psicología de
        scroll-stop: curiosity gap, contradicción, miedo, payoff rápido. Segmenta en{" "}
        <strong className="text-slate-700">micro-beats</strong> (1–2 s), clasifica el tipo de hook,
        mapea emoción → visual, diseño de audio (SFX, silencios, impact beats) e instrucciones de
        cámara para <code className="rounded bg-white px-1 text-slate-700">image_prompts.json</code>.
      </div>

      <PipelineStepConfirmBar
        stepId="hook_scene_router"
        stepLabel="Hook Scene Router"
        workApplied={workApplied}
        stepState={hookStepState}
        run={run}
        onAfterRun={refreshPipeline}
      />

      {narrativePreset && (
        <p className="text-xs text-slate-600">
          Categoría narrativa: <strong className="text-slate-900">{narrativePreset}</strong>
        </p>
      )}
      {recommendedHint && <p className="text-[11px] text-violet-700">{recommendedHint}</p>}
      {systemPromptSource === "internal" && systemPrompt.trim() ? (
        <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-900">
          Hay un system prompt guardado en disco; en modo automático se ignora. Cambia a manual o
          guarda ajustes en automático para limpiarlo.
        </p>
      ) : null}
      {(resolvedPlatform || resolvedEnergy) && (
        <p className="text-[11px] text-slate-600">
          Resuelto: plataforma <strong className="text-slate-900">{resolvedPlatform || "—"}</strong>
          {" · "}
          energía <strong className="text-slate-900">{resolvedEnergy || "—"}</strong>
          {" · "}
          sin talking head hasta <strong className="text-slate-900">{resolvedTalkingHeadAfter}s</strong>
        </p>
      )}

      {generationRunning && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          Ejecutando router de retención…
        </div>
      )}

      <Section
        id="hook-settings"
        title="Retención y pacing"
        description="IA (recomendado) o reglas heurísticas. Plataforma «auto» usa Metadata."
        theme="light"
      >
        <div className="space-y-3">
          <InferredFieldShell showSectionLabel className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <Label className="text-slate-700">Modo</Label>
                <Select
                  value={mode}
                  disabled={generationRunning}
                  onChange={(e) => setMode(e.target.value as RouterMode)}
                  className={inferredControlClass}
                >
                  <option value="llm">IA — retención + micro-beats (OpenAI)</option>
                  <option value="template">Reglas — segmentación heurística sin LLM</option>
                </Select>
              </div>
              <div>
                <Label className="text-slate-700">Plataforma</Label>
                <Select
                  value={platform}
                  disabled={generationRunning}
                  onChange={(e) => setPlatform(e.target.value as HookPlatform)}
                  className={inferredControlClass}
                >
                  <option value="auto">Auto (desde Metadata)</option>
                  <option value="tiktok">TikTok</option>
                  <option value="youtube_shorts">YouTube Shorts</option>
                  <option value="reels">Reels</option>
                  <option value="youtube">YouTube (hook narrativo)</option>
                </Select>
              </div>
              <div>
                <Label className="text-slate-700">Energía visual</Label>
                <Select
                  value={visualEnergy}
                  disabled={generationRunning}
                  onChange={(e) => setVisualEnergy(e.target.value as VisualEnergy)}
                  className={inferredControlClass}
                >
                  <option value="auto">Auto (según plataforma)</option>
                  <option value="high">Alta — cortes rápidos, zooms</option>
                  <option value="medium">Media — educativo limpio</option>
                  <option value="low">Baja — cinematic</option>
                </Select>
              </div>
              <div>
                <Label className="text-slate-700">Narrator visible después de</Label>
                <Select
                  value={talkingHeadAfter}
                  disabled={generationRunning}
                  onChange={(e) => setTalkingHeadAfter(e.target.value as TalkingHeadDelay)}
                  className={inferredControlClass}
                >
                  <option value="auto">Auto (20s Shorts/TikTok · 30s YouTube)</option>
                  <option value="20">20 segundos</option>
                  <option value="25">25 segundos</option>
                  <option value="30">30 segundos</option>
                </Select>
              </div>
              <div>
                <Label className="text-slate-700">Estilo finanzas (override)</Label>
                <Select
                  value={financeStyle}
                  disabled={generationRunning}
                  onChange={(e) => setFinanceStyle(e.target.value as FinanceStyle)}
                  className={inferredControlClass}
                >
                  <option value="auto">Automático (desde tipo de hook)</option>
                  <option value="deep_documentary">Deep Documentary</option>
                  <option value="data_minimalist">Data Minimalist</option>
                  <option value="financial_noir">Financial Noir</option>
                  <option value="intimate_pov">Intimate POV</option>
                </Select>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Btn
                type="button"
                className="border border-slate-300 bg-white text-slate-900 hover:bg-slate-50"
                disabled={generationRunning}
                onClick={applyRecommended}
              >
                Valores recomendados
              </Btn>
              <Btn
                type="button"
                className="bg-white text-slate-900 hover:bg-slate-100"
                disabled={generationRunning}
                onClick={() =>
                  run("Guardar ajustes Hook Router", async () => {
                    await putJson(`/api/pipeline/hook-router-settings`, {
                      work: workApplied,
                      mode,
                      finance_style: financeStyle,
                      platform,
                      visual_energy: visualEnergy,
                      system_prompt_source: systemPromptSource,
                      system_prompt:
                        systemPromptSource === "manual" ? systemPrompt.trim() : "",
                      talking_head_after_sec: talkingHeadAfter,
                    });
                    await loadSettings();
                  })
                }
              >
                Guardar ajustes
              </Btn>
            </div>
            {mode === "llm" ? (
              <div className="space-y-3 border-t border-slate-200 pt-3">
                <Label className="text-slate-700">System prompt</Label>
                <div className="flex flex-wrap gap-4">
                  <label className="flex cursor-pointer items-center gap-2">
                    <input
                      type="radio"
                      name="hook_system_prompt_source"
                      checked={systemPromptSource === "internal"}
                      disabled={generationRunning}
                      onChange={() => setSystemPromptSource("internal")}
                      className="text-violet-600 focus:ring-violet-500"
                    />
                    <span className="text-sm text-slate-700">IA automática (prompt interno)</span>
                  </label>
                  <label className="flex cursor-pointer items-center gap-2">
                    <input
                      type="radio"
                      name="hook_system_prompt_source"
                      checked={systemPromptSource === "manual"}
                      disabled={generationRunning}
                      onChange={() => setSystemPromptSource("manual")}
                      className="text-violet-600 focus:ring-violet-500"
                    />
                    <span className="text-sm text-slate-700">Manual (sustituye el interno)</span>
                  </label>
                </div>
                {systemPromptSource === "internal" ? (
                  <>
                    <p className="text-[11px] text-slate-500">
                      Vista previa según plataforma/energía resueltas y idioma de sesión (
                      {lang === "en" ? "English" : "Español"}). El gancho y metadata van en el
                      mensaje user al ejecutar Start step.
                    </p>
                    <TextArea
                      readOnly
                      value={defaultSystemPrompt}
                      className="min-h-[220px] cursor-default font-mono text-xs bg-slate-50 text-slate-700"
                    />
                  </>
                ) : (
                  <>
                    <div className="flex flex-wrap gap-2">
                      <Btn
                        type="button"
                        className="border border-slate-300 bg-white text-slate-800 hover:bg-slate-50 text-xs"
                        disabled={generationRunning || !defaultSystemPrompt.trim()}
                        onClick={handleLoadDefaultIntoManual}
                      >
                        Copiar prompt interno como base
                      </Btn>
                    </div>
                    <p className="text-[11px] text-amber-800">
                      Al guardar en manual, este texto reemplaza por completo el prompt interno.
                    </p>
                    <TextArea
                      value={systemPrompt}
                      disabled={generationRunning}
                      onChange={(e) => setSystemPrompt(e.target.value)}
                      className="min-h-[220px] font-mono text-xs"
                      placeholder="Escribe instrucciones propias o copia el interno como punto de partida."
                    />
                  </>
                )}
              </div>
            ) : (
              <p className="text-[11px] text-slate-500 border-t border-slate-200 pt-3">
                En modo <strong>Reglas</strong> no se usa system prompt; la segmentación es
                heurística en el servidor.
              </p>
            )}
          </InferredFieldShell>
        </div>
      </Section>

      {retentionSummary?.retention_analysis && (
        <div className={`text-xs ${inferredPanelClass()}`}>
          <p className="font-semibold text-slate-900">
            Clase: {retentionSummary.retention_analysis.primary_hook_class ?? "—"}
            {retentionSummary.visual_direction?.beat_count != null
              ? ` · ${retentionSummary.visual_direction.beat_count} beats`
              : null}
            {retentionSummary.visual_direction?.total_hook_duration_sec != null
              ? ` · ${retentionSummary.visual_direction.total_hook_duration_sec}s`
              : null}
            {retentionSummary.platform_pacing?.pacing_profile ? (
              <span className="text-emerald-700">
                {" "}
                · {retentionSummary.platform_pacing.label ?? retentionSummary.platform_pacing.pacing_profile}
                {retentionSummary.platform_pacing.breathing_room ? " · respiración" : " · sin dips"}
              </span>
            ) : null}
            {retentionSummary.intensity_arc?.shape ? (
              <span className="text-slate-600"> · arco {retentionSummary.intensity_arc.shape}</span>
            ) : null}
            {retentionSummary.intensity_curve?.length ? (
              <span className="text-slate-600">
                {" "}
                · curva [{retentionSummary.intensity_curve.join(", ")}]
              </span>
            ) : null}
          </p>
          {retentionSummary.platform_pacing?.guidance ? (
            <p className="mt-1 text-[11px] text-slate-600">{retentionSummary.platform_pacing.guidance}</p>
          ) : null}
          {retentionSummary.narrator_visibility ? (
            <p className="mt-1 text-slate-700">
              Visual: solo b-roll/gráficos
              {retentionSummary.narrator_visibility.entire_hook_visual_only
                ? " (gancho completo sin cámara)"
                : ` hasta ${retentionSummary.narrator_visibility.talking_head_allowed_after_sec ?? resolvedTalkingHeadAfter}s`}
              {retentionSummary.narrator_visibility.replacements_applied
                ? ` · ${retentionSummary.narrator_visibility.replacements_applied} talking_head corregidos`
                : null}
            </p>
          ) : null}
          {retentionSummary.image_prompt_policy?.anti_stock ? (
            <p className="mt-1 text-[11px] text-slate-600">
              Prompts imagen: estilo cinematográfico (anti-stock)
              {retentionSummary.image_prompt_policy.repairs_applied
                ? ` · ${retentionSummary.image_prompt_policy.repairs_applied} genéricos reescritos`
                : null}
            </p>
          ) : null}
          {retentionSummary.viewer_state_tracking?.attention_curve?.length ? (
            <p className="mt-1 text-slate-700">
              Viewer: att [{retentionSummary.viewer_state_tracking.attention_curve.join(", ")}]
              {" · "}
              carga [{retentionSummary.viewer_state_tracking.cognitive_load_curve?.join(", ")}]
              {retentionSummary.viewer_state_tracking.dropoff_risk_beat_indices?.length
                ? ` · ⚠ dropoff beats ${retentionSummary.viewer_state_tracking.dropoff_risk_beat_indices.join(",")}`
                : null}
            </p>
          ) : null}
          {retentionSummary.viewer_state_tracking?.pacing_recommendations?.[0] ? (
            <p className="mt-0.5 text-[11px] text-amber-800">
              {retentionSummary.viewer_state_tracking.pacing_recommendations[0]}
            </p>
          ) : null}
          {retentionSummary.transition_rhythm?.types_used &&
          Object.keys(retentionSummary.transition_rhythm.types_used).length > 0 ? (
            <p className="mt-1 text-slate-700">
              Transiciones:{" "}
              {Object.entries(retentionSummary.transition_rhythm.types_used)
                .map(([k, v]) => `${k}×${v}`)
                .join(" · ")}
            </p>
          ) : null}
          {retentionSummary.audio_design ? (
            <p className="mt-1 text-slate-700">
              Audio: música {retentionSummary.audio_design.music_energy ?? "—"}
              {retentionSummary.audio_design.sfx?.length
                ? ` · SFX ${retentionSummary.audio_design.sfx.slice(0, 4).join(", ")}`
                : null}
              {retentionSummary.audio_design.silence_before_payoff
                ? " · silencio pre-payoff"
                : null}
            </p>
          ) : null}
          {retentionSummary.retention_analysis.scroll_stop_rationale && (
            <p className="mt-1 text-slate-700">
              {retentionSummary.retention_analysis.scroll_stop_rationale}
            </p>
          )}
          {retentionSummary.visual_sequence_plan ? (
            <p className="mt-1 text-violet-800">
              Secuencia doc: {retentionSummary.visual_sequence_plan.arc ?? "—"}
              {retentionSummary.visual_sequence_plan.block_counts
                ? ` · ${Object.entries(retentionSummary.visual_sequence_plan.block_counts)
                    .map(([k, v]) => `${k.replace(/_/g, " ")}×${v}`)
                    .join(" · ")}`
                : null}
              {retentionSummary.visual_sequence_plan.emotional_tone
                ? ` · ${retentionSummary.visual_sequence_plan.emotional_tone}`
                : null}
              {retentionSummary.visual_sequence_plan.violations_fixed
                ? ` · ${retentionSummary.visual_sequence_plan.violations_fixed} pares distancia/ángulo corregidos`
                : null}
              {(retentionSummary.anchor_shot
                ?? retentionSummary.visual_sequence_plan?.anchor_shot)?.anchor_beat_index != null ? (
                <span className="block mt-0.5 text-amber-950 font-medium">
                  Plano ancla: beat #
                  {retentionSummary.anchor_shot?.anchor_beat_index
                    ?? retentionSummary.visual_sequence_plan?.anchor_shot?.anchor_beat_index}{" "}
                  ·{" "}
                  {retentionSummary.anchor_shot?.anchor_motif
                    ?? retentionSummary.visual_sequence_plan?.anchor_shot?.default_motif
                    ?? "cierre app / pantalla"}
                </span>
              ) : null}
              {(retentionSummary.narrative_rhythm
                ?? retentionSummary.visual_sequence_plan?.narrative_rhythm)?.tier_counts ? (
                <span className="block mt-0.5 text-amber-900">
                  Ritmo:{" "}
                  {Object.entries(
                    (retentionSummary.narrative_rhythm
                      ?? retentionSummary.visual_sequence_plan?.narrative_rhythm)!.tier_counts!,
                  )
                    .map(([k, v]) => `${k}×${v}`)
                    .join(" · ")}
                  {(retentionSummary.narrative_rhythm
                    ?? retentionSummary.visual_sequence_plan?.narrative_rhythm)?.duration_range_s
                    ? ` · ${(retentionSummary.narrative_rhythm ?? retentionSummary.visual_sequence_plan?.narrative_rhythm)!.duration_range_s!.join("–")}s/plano`
                    : null}
                </span>
              ) : null}
            </p>
          ) : null}
        </div>
      )}

      {beatsPreview.length > 0 && (
        <div className="space-y-1 rounded-xl border border-slate-200 bg-slate-50 p-3 shadow-sm">
          <p className="text-xs font-semibold text-slate-900">Micro-beats</p>
          <ul className="max-h-40 space-y-1 overflow-y-auto text-[11px] text-slate-700">
            {beatsPreview.map((b, i) => (
              <li
                key={b.index ?? i}
                className={
                  b.is_anchor_shot
                    ? "border-b border-amber-300 bg-amber-50/80 pb-1 last:border-0 rounded px-1"
                    : "border-b border-slate-200 pb-1 last:border-0"
                }
              >
                <span className="font-medium text-violet-700">
                  {b.start_sec ?? 0}s–{b.end_sec ?? "?"}s
                  {b.rhythm_tier ? (
                    <span className="text-amber-700"> · {b.rhythm_tier}</span>
                  ) : null}
                  {b.is_anchor_shot ? (
                    <span className="font-semibold text-amber-900"> · ANCLA</span>
                  ) : b.shot_hierarchy ? (
                    <span className="text-slate-500"> · {b.shot_hierarchy}</span>
                  ) : null}
                </span>{" "}
                {b.sequence_block ? (
                  <span className="text-violet-600">
                    [{b.sequence_block.replace(/_/g, " ")} · {b.shot_distance ?? "?"}/
                    {b.shot_angle ?? "?"}]
                  </span>
                ) : null}{" "}
                · <span className="text-amber-800">⚡{b.intensity ?? "—"}</span> ·{" "}
                {b.purpose ?? "—"}
                {b.pacing_role ? (
                  <span className="text-teal-700"> ({b.pacing_role})</span>
                ) : null}{" "}
                · <span className="text-sky-700">{b.scene_type ?? "broll"}</span>
                {b.narrator_visible ? " · ON-CAM" : ""} · {b.emotion ?? "—"}
                {b.text_overlay_content ? (
                  <span className="block truncate text-slate-600">
                    «{b.text_overlay_content}»
                  </span>
                ) : null}
                {b.audio ? (
                  <span className="block truncate text-emerald-700">
                    🔊 {b.audio.music_energy ?? "—"}
                    {b.audio.sfx?.length ? ` · ${b.audio.sfx.join(", ")}` : ""}
                    {b.audio.silence ? " · silence" : ""}
                    {b.audio.impact_beat ? " · IMPACT" : ""}
                  </span>
                ) : null}
                {b.transition_to_next?.type ? (
                  <span className="block truncate text-fuchsia-700">
                    → {b.transition_to_next.type}
                    {b.transition_to_next.duration_frames != null
                      ? ` (${b.transition_to_next.duration_frames}f)`
                      : ""}
                  </span>
                ) : null}
                {b.viewer_state ? (
                  <span className="block truncate text-indigo-700">
                    👁 att {b.viewer_state.attention} · cur {b.viewer_state.curiosity} · load{" "}
                    {b.viewer_state.cognitive_load}
                    {b.viewer_pacing_hint ? ` · ${b.viewer_pacing_hint}` : ""}
                  </span>
                ) : null}
                {b.light_quality || b.color_temperature ? (
                  <span className="block truncate text-indigo-700">
                    🎨 {b.color_temperature ?? "—"} · {b.light_quality ?? "—"}
                  </span>
                ) : null}
                {b.camera_motion ? (
                  <span className="block truncate text-fuchsia-700">
                    🎬 {b.camera_motion}
                    {b.camera_motion_direction ? ` (${b.camera_motion_direction})` : ""}
                    {b.camera_motion_note ? ` · ${b.camera_motion_note}` : ""}
                  </span>
                ) : null}
                {b.new_information_layer ? (
                  <span className="block truncate text-violet-700/90">
                    + {b.new_information_layer}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="space-y-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
        <div className="flex flex-wrap items-center gap-2">
          <Btn
            type="button"
            className="bg-slate-900 text-white hover:bg-slate-800 disabled:opacity-40"
            disabled={generationRunning || !hasArtifact}
            onClick={() =>
              run("Router → image_prompts.json", async () => {
                setPushFeedback(null);
                try {
                  const data = await postJson<HookPushToImagePromptsResult>(
                    `/api/pipeline/hook-router/push-to-image-prompts`,
                    { work: workApplied },
                  );
                  showPushFeedback({
                    kind: "success",
                    message: messageForHookPushToImagePrompts(data),
                  });
                  await refreshPipeline();
                } catch (e) {
                  showPushFeedback({
                    kind: "error",
                    message:
                      e instanceof Error ? e.message : "No se pudo volcar a image_prompts.json",
                  });
                  throw e;
                }
              })
            }
          >
            Volcar micro-beats → Image Prompt Writer
          </Btn>
          <span className="text-[11px] text-slate-600">
            Un prompt de imagen por beat (timing, cámara, emoción).
          </span>
        </div>
        {pushFeedback ? (
          <div
            role="status"
            className={
              pushFeedback.kind === "success"
                ? "rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-[12px] text-emerald-900"
                : "rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-900"
            }
          >
            {pushFeedback.kind === "success" ? (
              <span className="font-semibold">✓ </span>
            ) : null}
            {pushFeedback.message}
          </div>
        ) : null}
      </div>

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white p-4 shadow-sm shadow-slate-200/50 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="text-sm font-semibold tracking-wider capitalize text-slate-900">
            Salida · hook_scene_router.json
          </div>
          <div className="flex gap-2">
            <Btn
              type="button"
              className="border border-slate-200 bg-slate-100 text-slate-900 hover:bg-slate-200"
              onClick={() => void loadArtifact()}
            >
              Recargar
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
              : "Tras «Start step»: retention_analysis, micro_beats[], density_controls, camera por beat…"}
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
              <span className="text-sm font-semibold text-slate-900">hook_scene_router.json</span>
              <div className="flex gap-2">
                <Btn
                  type="button"
                  className="bg-slate-900 text-white hover:bg-slate-800"
                  disabled={generationRunning}
                  onClick={() =>
                    run("Guardar Hook Router", async () => {
                      let parsed: Record<string, unknown>;
                      try {
                        parsed = JSON.parse(artifactJson) as Record<string, unknown>;
                      } catch {
                        alert("JSON no válido.");
                        return;
                      }
                      await putJson("/api/pipeline/hook-router-artifact", {
                        work: workApplied,
                        artifact: parsed,
                      });
                      await loadArtifact();
                      await refreshPipeline();
                    })
                  }
                >
                  Guardar
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
          </div>
        </div>
      )}
    </div>
  );
}
