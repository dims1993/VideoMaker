import { useCallback, useEffect, useRef, useState, type MutableRefObject } from "react";
import { Btn, Input, Label } from "../../../components/ui";
import { postJson, putJson } from "../../../services/api";
import type { RunFn } from "../types";
import { TranscriptsSessionBanner } from "../shared/TranscriptsSessionBanner";
import {
  normalizeAnalyzeOutputLang,
  type AnalyzeOutputLanguage,
} from "../../analyze/transcriptsSession";
import { PIPELINE_DURATION_HINT } from "../pipelineDuration";
import type { TopicGeneratorArtifact, TopicIdea } from "./types";

export function TopicGeneratorPanel({
  run,
  workApplied,
  provider,
  model,
  nicheTrends,
  onNicheTrendsChange,
  topicCount,
  onTopicCountChange,
  topics,
  onTopicsChange,
  selectedIndex,
  onSelectTopic,
  onApplyToSession,
  onSpawnProduction,
  onSessionLanguageSync,
  stepState = "idle",
  locked = false,
  generateRef,
  onGeneratingChange,
  onTopicsGenerated,
}: {
  run: RunFn;
  workApplied: string;
  stepState?: string;
  locked?: boolean;
  /** Botón «Generar temas nuevos» en el header de la pipeline. */
  generateRef?: MutableRefObject<(() => void) | null>;
  onGeneratingChange?: (generating: boolean) => void;
  onTopicsGenerated?: () => void | Promise<void>;
  provider: string;
  model: string;
  nicheTrends: string;
  onNicheTrendsChange: (v: string) => void;
  topicCount: number;
  onTopicCountChange: (n: number) => void;
  topics: TopicIdea[];
  onTopicsChange: (topics: TopicIdea[]) => void;
  selectedIndex: number | null;
  onSelectTopic: (index: number | null) => void;
  onApplyToSession: (topic: TopicIdea) => void;
  /** Nueva carpeta de producción reutilizando el banco de temas (sin LLM). */
  onSpawnProduction?: (childWork: string, topic: TopicIdea) => void;
  /** Alinea idioma de sesión Create ({{LANGUAGE_CODE}}) con Topic Generator / Analyse. */
  onSessionLanguageSync?: (code: AnalyzeOutputLanguage) => void;
}) {
  const [error, setError] = useState("");
  const [generating, setGenerating] = useState(false);
  const [enrichingIndex, setEnrichingIndex] = useState<number | null>(null);
  const [sessionReady, setSessionReady] = useState(false);
  const [analyzeDone, setAnalyzeDone] = useState(false);
  const [outputLang, setOutputLang] = useState<AnalyzeOutputLanguage>("en");
  const onTopicsChangeRef = useRef(onTopicsChange);
  const onNicheTrendsChangeRef = useRef(onNicheTrendsChange);
  const onSelectTopicRef = useRef(onSelectTopic);
  const onSessionLanguageSyncRef = useRef(onSessionLanguageSync);

  useEffect(() => {
    onTopicsChangeRef.current = onTopicsChange;
    onNicheTrendsChangeRef.current = onNicheTrendsChange;
    onSelectTopicRef.current = onSelectTopic;
    onSessionLanguageSyncRef.current = onSessionLanguageSync;
  }, [onTopicsChange, onNicheTrendsChange, onSelectTopic, onSessionLanguageSync]);

  const loadArtifact = useCallback(async () => {
    if (!workApplied) return;

    try {
      const res = await fetch(
        `/api/pipeline/topic-generator?work=${encodeURIComponent(workApplied)}`,
      );
      if (!res.ok) return;
      const data = (await res.json()) as TopicGeneratorArtifact;
      if (Array.isArray(data.topics) && data.topics.length > 0) {
        onTopicsChangeRef.current(data.topics);
      }
      if (typeof data.niche_trends === "string" && data.niche_trends && !nicheTrends) {
        onNicheTrendsChangeRef.current(data.niche_trends);
      }
      if (data.selected_index != null && data.selected_index >= 0) {
        onSelectTopicRef.current(data.selected_index);
      }
      if (data.output_language === "en" || data.output_language === "es") {
        const code = normalizeAnalyzeOutputLang(data.output_language);
        setOutputLang(code);
        onSessionLanguageSyncRef.current?.(code);
      } else {
        const code = normalizeAnalyzeOutputLang(outputLang);
        onSessionLanguageSyncRef.current?.(code);
        try {
          await putJson("/api/pipeline/topic-generator/output-language", {
            work: workApplied,
            output_language: code,
          });
        } catch {
          /* ignore */
        }
      }
    } catch {
      /* ignore */
    }
  }, [workApplied, nicheTrends, outputLang]);

  useEffect(() => {
    void loadArtifact();
  }, [loadArtifact]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await fetch(
          `/api/session/transcripts?work=${encodeURIComponent(workApplied)}`,
        );
        if (!res.ok || cancelled) return;
        const data = (await res.json()) as {
          stored?: boolean;
          valid_count?: number;
          analyze_status?: string;
        };
        if (cancelled) return;
        setSessionReady(!!data.stored && (data.valid_count ?? 0) >= 1);
        setAnalyzeDone(data.analyze_status === "completed");
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [workApplied]);

  useEffect(() => {
    if (stepState === "done") void loadArtifact();
  }, [stepState, loadArtifact]);

  const handleGenerate = useCallback(
    () =>
      run("Generar temas", async () => {
        setError("");
        if (!sessionReady) {
          setError(
            "Carga y analiza transcripts en Analyse (Transcripts JSON → sesión) primero.",
          );
          return;
        }
        setGenerating(true);
        onGeneratingChange?.(true);
        try {
          const payload = await postJson<TopicGeneratorArtifact>(
            "/api/pipeline/topic-generator/generate",
            {
              work: workApplied,
              transcript_text: "",
              use_session: true,
              niche_trends: nicheTrends,
              topic_count: topicCount,
              output_language: outputLang,
              provider,
              model,
            },
          );
          onTopicsChange(payload.topics ?? []);
          const idx = payload.selected_index;
          onSelectTopic(typeof idx === "number" && idx >= 0 ? idx : null);
          if (typeof idx === "number" && idx >= 0 && payload.topics?.[idx]) {
            onApplyToSession(payload.topics[idx]);
          }
          if (payload.output_language === "en" || payload.output_language === "es") {
            const code = normalizeAnalyzeOutputLang(payload.output_language);
            setOutputLang(code);
            onSessionLanguageSync?.(code);
          }
          await onTopicsGenerated?.();
        } catch (e) {
          setError(e instanceof Error ? e.message : "Error al generar temas");
        } finally {
          setGenerating(false);
          onGeneratingChange?.(false);
        }
      }),
    [
      run,
      sessionReady,
      workApplied,
      nicheTrends,
      topicCount,
      outputLang,
      provider,
      model,
      onTopicsChange,
      onSelectTopic,
      onApplyToSession,
      onGeneratingChange,
      onTopicsGenerated,
    ],
  );

  useEffect(() => {
    if (generateRef) {
      generateRef.current = () => {
        handleGenerate();
      };
    }
    return () => {
      if (generateRef) generateRef.current = null;
    };
  }, [generateRef, handleGenerate]);

  const handleProduceVideo = (index: number) =>
    run("Producir vídeo", async () => {
      const topic = topics[index];
      if (!topic) return;
      setError("");
      await putJson("/api/pipeline/topic-generator/select", {
        work: workApplied,
        selected_index: index,
      });
      onSelectTopic(index);
      const resp = await postJson<{
        child_work: string;
        topic: TopicIdea;
        topic_title: string;
      }>("/api/pipeline/sessions/spawn", {
        parent_work: workApplied,
        topic_index: index,
        copy_transcripts: true,
        reset_from_step: "narrative_angle",
      });
      onApplyToSession(topic);
      onSessionLanguageSync?.(outputLang);
      onSpawnProduction?.(resp.child_work, resp.topic ?? topic);
    });

  const handleUseTopic = (index: number) =>
    run("Seleccionar tema", async () => {
      const topic = topics[index];
      if (!topic) return;
      await putJson("/api/pipeline/topic-generator/select", {
        work: workApplied,
        selected_index: index,
      });
      onSelectTopic(index);
      onApplyToSession(topic);
      onSessionLanguageSync?.(outputLang);

      // Enrich selected topic (heavy fields) after selection.
      setEnrichingIndex(index);
      try {
        await postJson("/api/pipeline/topic-generator/enrich", {
          work: workApplied,
          selected_index: index,
          provider,
          model,
        });
        await loadArtifact();
      } catch {
        // Ignore enrich failures; base topic is still usable.
      } finally {
        setEnrichingIndex(null);
      }
    });

  const disabled = locked || generating;

  return (
    <div className="relative space-y-4">
      {locked ? (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-900">
          Tema confirmado. El apartado está bloqueado. Usa{" "}
          <strong>Resetear selección</strong> para volver a elegir o{" "}
          <strong>Generar temas nuevos</strong> para otra lista.
        </div>
      ) : null}
      <TranscriptsSessionBanner workApplied={workApplied} />

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm shadow-slate-200/50">
        <div className="border-b border-slate-200 bg-slate-50 px-4 py-3.5">
          <h3 className="text-[15px] font-semibold tracking-tight text-slate-900">
            TENDENCIAS DEL NICHO
          </h3>
          <p className="mt-1 text-[12px] text-slate-500">
            Pega señales de tendencia, búsquedas en alza, competencia o notas de investigación.
          </p>
        </div>
        <div className="space-y-3 p-4 sm:p-5">
          <textarea
            value={nicheTrends}
            onChange={(e) => onNicheTrendsChange(e.target.value)}
            disabled={disabled}
            rows={5}
            placeholder="Ej: Shorts de finanzas personales en alza; audiencia pregunta por inflación 2026; competidores cubren cripto pero no nóminas…"
            className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
          />
          <div className="flex flex-wrap items-end gap-3">
            <div className="w-36">
              <Label>Idioma de salida</Label>
              <p className="mb-1 text-[11px] text-slate-500">
                Define el idioma de guion, metadata, routers y engines de esta sesión.
              </p>
              <select
                className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-2 py-2 text-sm text-slate-900"
                value={outputLang}
                onChange={(e) => {
                  const code = normalizeAnalyzeOutputLang(e.target.value);
                  setOutputLang(code);
                  onSessionLanguageSync?.(code);
                  void putJson("/api/pipeline/topic-generator/output-language", {
                    work: workApplied,
                    output_language: code,
                  }).catch(() => {
                    /* persist best-effort */
                  });
                }}
                disabled={disabled}
              >
                <option value="en">English</option>
                <option value="es">Español</option>
              </select>
            </div>
            <div className="w-28">
              <Label>Cantidad (X)</Label>
              <Input
                type="number"
                min={3}
                max={20}
                value={topicCount}
                disabled={disabled}
                onChange={(e) => {
                  const n = Number.parseInt(e.target.value, 10);
                  onTopicCountChange(Number.isFinite(n) ? Math.min(20, Math.max(3, n)) : 8);
                }}
              />
            </div>
            {analyzeDone && topics.length > 0 ? (
              <p className="text-[11px] text-slate-500">
                Regenera la lista con el botón violeta del encabezado.
              </p>
            ) : null}
          </div>
        </div>
      </div>

      {topics.length > 0 ? (
        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-200 bg-slate-50 px-4 py-3">
            <h3 className="text-[15px] font-semibold text-slate-900">
              IDEAS GENERADAS ({topics.length})
            </h3>
            <p className="text-[12px] text-slate-500">
              Elige un tema para rellenar keywords, ángulo y duración de la sesión (paso Prompt).
            </p>
          </div>
          <ul className="divide-y divide-slate-100">
            {topics.map((t, i) => {
              const selected = selectedIndex === i;
              return (
                <li
                  key={`${i}-${t.title}`}
                  className={[
                    "px-4 py-3 transition-colors",
                    selected ? "bg-violet-50/80" : "hover:bg-slate-50/80",
                  ].join(" ")}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-semibold text-slate-900">{t.title}</div>
                      {(t.primary_trigger || (t.trigger_stack && t.trigger_stack.length > 0)) && (
                        <p className="mt-1 text-[11px] text-emerald-700/90">
                          {t.primary_trigger ? (
                            <span className="font-semibold">Trigger:</span>
                          ) : (
                            <span className="font-semibold">Triggers:</span>
                          )}{" "}
                          {t.primary_trigger || t.trigger_stack?.[0] || "—"}
                          {t.trigger_stack && t.trigger_stack.length > 1
                            ? ` · ${t.trigger_stack.slice(1, 4).join(" · ")}`
                            : ""}
                        </p>
                      )}
                      <p className="mt-1 text-[12px] leading-relaxed text-slate-600">{t.angle}</p>
                      {t.why_now ? (
                        <p className="mt-1 text-[11px] text-violet-700/90">{t.why_now}</p>
                      ) : null}
                      {t.emotional_promise ? (
                        <p className="mt-1 text-[11px] text-slate-500">
                          <span className="font-semibold text-slate-700">Promesa:</span>{" "}
                          {t.emotional_promise}
                        </p>
                      ) : null}
                      {t.core_emotion || t.identity_shift || t.transformation_claim ? (
                        <div className="mt-1 grid gap-1 sm:grid-cols-3">
                          {t.core_emotion ? (
                            <p className="text-[11px] text-slate-500">
                              <span className="font-semibold text-slate-700">Emoción:</span>{" "}
                              {t.core_emotion}
                            </p>
                          ) : null}
                          {t.identity_shift ? (
                            <p className="text-[11px] text-slate-500 sm:col-span-2">
                              <span className="font-semibold text-slate-700">Identidad:</span>{" "}
                              {t.identity_shift}
                            </p>
                          ) : null}
                          {t.transformation_claim ? (
                            <p className="text-[11px] text-slate-500 sm:col-span-3">
                              <span className="font-semibold text-slate-700">Transformación:</span>{" "}
                              {t.transformation_claim}
                            </p>
                          ) : null}
                        </div>
                      ) : null}
                      {t.visual_anchor ? (
                        <p className="mt-1 text-[11px] text-slate-500">
                          <span className="font-semibold text-slate-700">Visual anchor:</span>{" "}
                          {t.visual_anchor}
                        </p>
                      ) : null}
                      {t.scene_pack && t.scene_pack.length > 0 ? (
                        <div className="mt-1.5 rounded-lg border border-slate-100 bg-slate-50 px-2.5 py-2">
                          <p className="text-[10px] font-semibold text-slate-600">
                            Scene pack ({t.scene_pack.length}/15)
                          </p>
                          <ul className="mt-1 list-disc space-y-0.5 pl-4 text-[11px] text-slate-600">
                            {t.scene_pack.slice(0, 5).map((s, idx) => (
                              <li key={idx}>{s}</li>
                            ))}
                          </ul>
                          {t.scene_pack.length > 5 ? (
                            <p className="mt-1 text-[10px] text-slate-500">
                              +{t.scene_pack.length - 5} escenas más…
                            </p>
                          ) : null}
                        </div>
                      ) : null}
                      {t.broll_keywords && t.broll_keywords.length > 0 ? (
                        <p className="mt-1 text-[11px] text-slate-500">
                          <span className="font-semibold text-slate-700">B-roll:</span>{" "}
                          {t.broll_keywords.slice(0, 10).join(", ")}
                        </p>
                      ) : null}
                      {(t.thumbnail_text || t.opening_hook) && (
                        <div className="mt-1.5 grid gap-1 sm:grid-cols-2">
                          {t.thumbnail_text ? (
                            <p className="text-[11px] text-slate-500">
                              <span className="font-semibold text-slate-700">Thumbnail:</span>{" "}
                              <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-700">
                                {t.thumbnail_text}
                              </span>
                            </p>
                          ) : null}
                          {t.opening_hook ? (
                            <p className="text-[11px] text-slate-500">
                              <span className="font-semibold text-slate-700">Hook 0–5s:</span>{" "}
                              {t.opening_hook}
                            </p>
                          ) : null}
                        </div>
                      )}
                      {t.thumbnail_concept ? (
                        <div className="mt-1.5 rounded-lg border border-slate-100 bg-white px-2.5 py-2">
                          <p className="text-[10px] font-semibold text-slate-600">Thumbnail-first</p>
                          {t.thumbnail_concept.one_sentence ? (
                            <p className="mt-0.5 text-[11px] text-slate-600">
                              {t.thumbnail_concept.one_sentence}
                            </p>
                          ) : null}
                          <div className="mt-1 grid gap-1 sm:grid-cols-2">
                            {t.thumbnail_concept.contrast ? (
                              <p className="text-[11px] text-slate-500">
                                <span className="font-semibold text-slate-700">Contraste:</span>{" "}
                                {t.thumbnail_concept.contrast}
                              </p>
                            ) : null}
                            {t.thumbnail_concept.face_emotion ? (
                              <p className="text-[11px] text-slate-500">
                                <span className="font-semibold text-slate-700">Emoción:</span>{" "}
                                {t.thumbnail_concept.face_emotion}
                              </p>
                            ) : null}
                            {t.thumbnail_concept.props?.length ? (
                              <p className="text-[11px] text-slate-500">
                                <span className="font-semibold text-slate-700">Props:</span>{" "}
                                {t.thumbnail_concept.props.slice(0, 3).join(", ")}
                              </p>
                            ) : null}
                            {t.thumbnail_concept.color_story ? (
                              <p className="text-[11px] text-slate-500">
                                <span className="font-semibold text-slate-700">Color:</span>{" "}
                                {t.thumbnail_concept.color_story}
                              </p>
                            ) : null}
                            {t.thumbnail_concept.composition ? (
                              <p className="text-[11px] text-slate-500 sm:col-span-2">
                                <span className="font-semibold text-slate-700">Composición:</span>{" "}
                                {t.thumbnail_concept.composition}
                              </p>
                            ) : null}
                            {t.thumbnail_concept.avoid?.length ? (
                              <p className="text-[11px] text-slate-500 sm:col-span-2">
                                <span className="font-semibold text-slate-700">Evitar:</span>{" "}
                                {t.thumbnail_concept.avoid.slice(0, 4).join(", ")}
                              </p>
                            ) : null}
                          </div>
                          {typeof t.thumbnailability === "number" ? (
                            <p className="mt-1 text-[11px] text-slate-500">
                              <span className="font-semibold text-slate-700">Thumbnailability:</span>{" "}
                              {t.thumbnailability}
                            </p>
                          ) : null}
                        </div>
                      ) : null}
                      {t.familiar_pain || t.expectation_break || t.novelty_device ? (
                        <div className="mt-1.5 rounded-lg border border-slate-100 bg-amber-50 px-2.5 py-2">
                          <p className="text-[10px] font-semibold text-amber-900">Novelty injection</p>
                          {t.familiar_pain ? (
                            <p className="mt-0.5 text-[11px] text-amber-900/90">
                              <span className="font-semibold">Pain:</span> {t.familiar_pain}
                            </p>
                          ) : null}
                          {t.expectation_break ? (
                            <p className="mt-0.5 text-[11px] text-amber-900/90">
                              <span className="font-semibold">Break:</span> {t.expectation_break}
                            </p>
                          ) : null}
                          {t.novelty_device ? (
                            <p className="mt-0.5 text-[11px] text-amber-900/80">
                              <span className="font-semibold">Device:</span> {t.novelty_device}
                            </p>
                          ) : null}
                        </div>
                      ) : null}
                      {t.social_identity_tension ||
                      t.tribe_boundary ||
                      t.status_anxiety_hook ||
                      t.freedom_fantasy ||
                      t.regret_trigger ? (
                        <div className="mt-1.5 rounded-lg border border-slate-100 bg-rose-50 px-2.5 py-2">
                          <p className="text-[10px] font-semibold text-rose-900">
                            Social identity tension
                          </p>
                          {t.tribe_boundary ? (
                            <p className="mt-0.5 text-[11px] text-rose-900/90">
                              <span className="font-semibold">Tribu:</span> {t.tribe_boundary}
                            </p>
                          ) : null}
                          {t.social_identity_tension ? (
                            <p className="mt-0.5 text-[11px] text-rose-900/90">
                              <span className="font-semibold">Tensión:</span>{" "}
                              {t.social_identity_tension}
                            </p>
                          ) : null}
                          {t.status_anxiety_hook ? (
                            <p className="mt-0.5 text-[11px] text-rose-900/80">
                              <span className="font-semibold">Status fear:</span>{" "}
                              {t.status_anxiety_hook}
                            </p>
                          ) : null}
                          {t.freedom_fantasy ? (
                            <p className="mt-0.5 text-[11px] text-rose-900/80">
                              <span className="font-semibold">Freedom:</span> {t.freedom_fantasy}
                            </p>
                          ) : null}
                          {t.regret_trigger ? (
                            <p className="mt-0.5 text-[11px] text-rose-900/80">
                              <span className="font-semibold">Regret:</span> {t.regret_trigger}
                            </p>
                          ) : null}
                          {typeof t.identity_tension === "number" ? (
                            <p className="mt-0.5 text-[11px] text-rose-900/80">
                              <span className="font-semibold">Identity tension:</span>{" "}
                              {t.identity_tension}
                            </p>
                          ) : null}
                        </div>
                      ) : null}
                      {t.dominant_emotion || t.visualizability || (t.scroll_stop_factors?.length ?? 0) > 0 ? (
                        <div className="mt-1.5 rounded-lg border border-slate-100 bg-sky-50 px-2.5 py-2">
                          <p className="text-[10px] font-semibold text-sky-900">Scroll-stop</p>
                          {t.dominant_emotion ? (
                            <p className="mt-0.5 text-[11px] text-sky-900/90">
                              <span className="font-semibold">Dominant emotion:</span>{" "}
                              {t.dominant_emotion}
                            </p>
                          ) : null}
                          {t.visualizability ? (
                            <p className="mt-0.5 text-[11px] text-sky-900/80">
                              <span className="font-semibold">Visualizability:</span>{" "}
                              b-roll {t.visualizability.broll_strength ?? "—"} · symbolic{" "}
                              {t.visualizability.symbolic_visuals ?? "—"} · motion{" "}
                              {t.visualizability.motion_graphics_potential ?? "—"}
                            </p>
                          ) : null}
                          {t.scroll_stop_factors?.length ? (
                            <p className="mt-0.5 text-[11px] text-sky-900/80">
                              <span className="font-semibold">Factors:</span>{" "}
                              {t.scroll_stop_factors.slice(0, 6).join(" · ")}
                            </p>
                          ) : null}
                        </div>
                      ) : null}
                      {(typeof t.click_impulse_score === "number" ||
                        typeof t.visual_explosiveness_score === "number" ||
                        typeof t.abstractness_score === "number" ||
                        typeof t.explaining_mode_score === "number" ||
                        typeof t.novelty_score === "number" ||
                        typeof t.social_tension_score === "number" ||
                        typeof t.identity_tension === "number" ||
                        typeof t.thumbnailability === "number" ||
                        typeof t.intellectual_tone_score === "number") && (
                        <p className="mt-1 text-[11px] text-slate-500">
                          {typeof t.click_impulse_score === "number" ? (
                            <>
                              <span className="font-semibold text-slate-700">Click:</span>{" "}
                              {t.click_impulse_score}
                            </>
                          ) : null}
                          {typeof t.visual_explosiveness_score === "number" ? (
                            <>
                              {typeof t.click_impulse_score === "number" ? " · " : null}
                              <span className="font-semibold text-slate-700">Visual:</span>{" "}
                              {t.visual_explosiveness_score}
                            </>
                          ) : null}
                          {typeof t.abstractness_score === "number" ? (
                            <>
                              {typeof t.click_impulse_score === "number" ||
                              typeof t.visual_explosiveness_score === "number"
                                ? " · "
                                : null}
                              <span className="font-semibold text-slate-700">Abstracto:</span>{" "}
                              {t.abstractness_score}
                            </>
                          ) : null}
                          {typeof t.explaining_mode_score === "number" ? (
                            <>
                              {typeof t.click_impulse_score === "number" ||
                              typeof t.visual_explosiveness_score === "number" ||
                              typeof t.abstractness_score === "number"
                                ? " · "
                                : null}
                              <span className="font-semibold text-slate-700">Explain:</span>{" "}
                              {t.explaining_mode_score}
                            </>
                          ) : null}
                          {typeof t.novelty_score === "number" ? (
                            <>
                              {typeof t.click_impulse_score === "number" ||
                              typeof t.visual_explosiveness_score === "number" ||
                              typeof t.abstractness_score === "number" ||
                              typeof t.explaining_mode_score === "number"
                                ? " · "
                                : null}
                              <span className="font-semibold text-slate-700">Novelty:</span>{" "}
                              {t.novelty_score}
                            </>
                          ) : null}
                          {typeof t.thumbnailability === "number" ? (
                            <>
                              {typeof t.click_impulse_score === "number" ||
                              typeof t.visual_explosiveness_score === "number" ||
                              typeof t.abstractness_score === "number" ||
                              typeof t.explaining_mode_score === "number" ||
                              typeof t.novelty_score === "number"
                                ? " · "
                                : null}
                              <span className="font-semibold text-slate-700">Thumb:</span>{" "}
                              {t.thumbnailability}
                            </>
                          ) : null}
                          {typeof t.social_tension_score === "number" ? (
                            <>
                              {typeof t.click_impulse_score === "number" ||
                              typeof t.visual_explosiveness_score === "number" ||
                              typeof t.abstractness_score === "number" ||
                              typeof t.explaining_mode_score === "number" ||
                              typeof t.novelty_score === "number"
                                ? " · "
                                : null}
                              <span className="font-semibold text-slate-700">Social:</span>{" "}
                              {t.social_tension_score}
                            </>
                          ) : null}
                          {typeof t.identity_tension === "number" ? (
                            <>
                              {typeof t.click_impulse_score === "number" ||
                              typeof t.visual_explosiveness_score === "number" ||
                              typeof t.abstractness_score === "number" ||
                              typeof t.explaining_mode_score === "number" ||
                              typeof t.novelty_score === "number" ||
                              typeof t.thumbnailability === "number" ||
                              typeof t.social_tension_score === "number"
                                ? " · "
                                : null}
                              <span className="font-semibold text-slate-700">Identity:</span>{" "}
                              {t.identity_tension}
                            </>
                          ) : null}
                          {typeof t.intellectual_tone_score === "number" ? (
                            <>
                              {typeof t.click_impulse_score === "number" ||
                              typeof t.visual_explosiveness_score === "number" ||
                              typeof t.abstractness_score === "number" ||
                              typeof t.explaining_mode_score === "number" ||
                              typeof t.novelty_score === "number" ||
                              typeof t.social_tension_score === "number" ||
                              typeof t.thumbnailability === "number" ||
                              typeof t.identity_tension === "number"
                                ? " · "
                                : null}
                              <span className="font-semibold text-slate-700">Intelectual:</span>{" "}
                              {t.intellectual_tone_score}
                            </>
                          ) : null}
                        </p>
                      )}
                      <p className="mt-1.5 text-[11px] text-slate-500">
                        Duración recomendada:{" "}
                        <strong>{t.recommended_duration_minutes} min</strong>
                      </p>
                    </div>
                    <div className="flex shrink-0 flex-col gap-2">
                      <Btn
                        className="bg-emerald-600 text-white hover:bg-emerald-500"
                        disabled={disabled}
                        onClick={() => void handleProduceVideo(i)}
                        title="Nueva sesión de producción (reutiliza temas, sin volver a llamar al LLM)"
                      >
                        Producir vídeo →
                      </Btn>
                      <Btn
                        className={
                          selected
                            ? "bg-violet-700 text-white"
                            : "bg-white text-slate-800 ring-1 ring-slate-200 hover:bg-slate-50"
                        }
                        disabled={disabled || enrichingIndex === i}
                        onClick={() => void handleUseTopic(i)}
                      >
                        {enrichingIndex === i
                          ? "Enriqueciendo…"
                          : selected
                            ? "Seleccionado"
                            : "Usar en esta sesión"}
                      </Btn>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      ) : (
        <p className="text-[12px] text-slate-500">
          Tras generar verás la lista con título, ángulo único y duración recomendada por vídeo.
        </p>
      )}

      {error ? (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
          {error}
        </div>
      ) : null}

      <p className="text-[10px] text-slate-400">
        {PIPELINE_DURATION_HINT} La sesión y Narrative Angle usan ese rango al elegir tema.
      </p>
      <p className="text-[10px] text-slate-400">
        <strong>Producir vídeo →</strong> abre una carpeta nueva (
        <code className="text-[9px]">output/v01_…</code>) con el mismo banco de temas y
        transcripts, sin regenerar la lista. <strong>Usar en esta sesión</strong> solo marca el
        tema aquí (útil para investigar en la carpeta padre).
      </p>
    </div>
  );
}
