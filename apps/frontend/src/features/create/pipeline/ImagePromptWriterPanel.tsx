import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Btn, ExpandableTextArea, Input, IosSwitch, Label, Select, TextArea } from "../../../components/ui";
import { postJson, putJson } from "../../../services/api";
import { ALEX_PRESET_ID } from "../sceneEditor/visualStylePresets";
import type { RunFn } from "../types";
import { VisualStylePanel } from "../sceneEditor/VisualStylePanel";
import { ProductionResetButton } from "./ProductionResetButton";
import { PipelineStepConfirmBar } from "./PipelineStepConfirmBar";
import { PipelineSection as Section } from "./PipelineSection";
import {
  messageForHookPushToImagePrompts,
  type HookPushToImagePromptsResult,
} from "./hookRouterPushFeedback";

type TargetGenerator = "midjourney" | "flux" | "dall_e" | "sd" | "custom";
type VisualMode = "static" | "animation" | "combined";

// ── Types for individual prompts ──────────────────────────────────────────
interface PromptItem {
  id?: string;
  track?: "avatar" | "insert" | string;
  act?: string;
  role?: string;
  expression?: string;
  situation?: string;
  narration_text?: string;
  ai_prompt?: string;
  negative_prompt?: string;
  segment_text?: string;
  text_anchor?: string;
  /** Si existe en el bundle, solo los marcados se envían a Images Generation. */
  selected?: boolean;
  // legacy
  text?: string;
  [key: string]: unknown;
}

type ValidationCandidate = {
  id: string;
  source: string;
  act: string;
  track: string;
  text_anchor: string;
  has_ai_prompt?: boolean;
};

const ACT_COLORS: Record<string, string> = {
  thumbnail: "bg-amber-950/50 text-amber-200 ring-1 ring-amber-500/40",
  hook:  "bg-amber-950/50 text-amber-300 ring-1 ring-amber-500/30",
  intro: "bg-violet-950/40 text-violet-200 ring-1 ring-violet-500/30",
  body:  "bg-slate-600 text-slate-200",
  cta:   "bg-sky-950/40 text-sky-200 ring-1 ring-sky-500/30",
  outro: "bg-emerald-950/40 text-emerald-200 ring-1 ring-emerald-500/30",
};
const ACT_LABELS: Record<string, string> = {
  thumbnail: "Miniatura", hook: "Hook", intro: "Intro", body: "Body", cta: "CTA", outro: "Outro",
};
const EXPRESSIONS = [
  "smiling","surprised","bored","sleepy","neutral",
  "explaining","worried","thinking","excited",
];

// ── PromptCard ─────────────────────────────────────────────────────────────
function PromptCard({
  item,
  index,
  expanded,
  onToggle,
  onSave,
  readOnly,
  showExportSelect,
  onToggleExportSelect,
}: {
  item: PromptItem;
  index: number;
  expanded: boolean;
  onToggle: () => void;
  onSave: (updated: PromptItem) => void;
  readOnly: boolean;
  showExportSelect?: boolean;
  onToggleExportSelect?: () => void;
}) {
  const exportSelected = item.selected !== false;
  const act =
    item.role === "thumbnail"
      ? "thumbnail"
      : item.act ?? (item.role?.includes("intro") ? "intro" : item.role?.includes("outro") ? "outro" : "body");
  const actColor = ACT_COLORS[act] ?? ACT_COLORS.body;
  const actLabel = ACT_LABELS[act] ?? act;
  const preview = item.situation || item.ai_prompt || item.text || "";

  // Local edit state
  const [editAct, setEditAct] = useState(act);
  const [editExpression, setEditExpression] = useState(item.expression ?? "");
  const [editSituation, setEditSituation] = useState(item.situation ?? "");
  const [editNarration, setEditNarration] = useState(item.narration_text ?? "");
  const [editPrompt, setEditPrompt] = useState(item.ai_prompt ?? item.text ?? "");
  const [editNeg, setEditNeg] = useState(item.negative_prompt ?? "");
  const cardRef = useRef<HTMLDivElement>(null);

  // Reset local state when card collapses
  useEffect(() => {
    if (!expanded) {
      setEditAct(item.act ?? act);
      setEditExpression(item.expression ?? "");
      setEditSituation(item.situation ?? "");
      setEditNarration(item.narration_text ?? "");
      setEditPrompt(item.ai_prompt ?? item.text ?? "");
      setEditNeg(item.negative_prompt ?? "");
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expanded]);

  useEffect(() => {
    if (expanded) cardRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [expanded]);

  const handleSave = () => {
    onSave({
      ...item,
      act: editAct,
      expression: editExpression,
      situation: editSituation,
      narration_text: editNarration || undefined,
      ai_prompt: editPrompt,
      negative_prompt: editNeg,
    });
  };

  const isSpecial = item.id === "intro" || item.id === "outro";

  return (
    <div
      ref={cardRef}
      className={`rounded-xl border transition-all ${expanded ? "border-slate-500 bg-slate-800/80 shadow-md" : "border-slate-600 bg-slate-800/40 hover:border-slate-500"}`}
    >
      {/* Collapsed header — always visible, clickable */}
      <div className="flex w-full items-start gap-2 px-3 py-2">
        {showExportSelect && onToggleExportSelect ? (
          <button
            type="button"
            className={`mt-0.5 shrink-0 h-5 w-5 rounded border-2 flex items-center justify-center transition-colors ${
              exportSelected
                ? "border-cyan-500 bg-cyan-600"
                : "border-slate-500 bg-slate-800 hover:border-slate-400"
            }`}
            onClick={(e) => {
              e.stopPropagation();
              onToggleExportSelect();
            }}
            disabled={readOnly}
            aria-label={exportSelected ? "Quitar de exportación" : "Incluir en exportación"}
            title="Incluir al enviar a Images Generation"
          >
            {exportSelected ? (
              <svg className="h-3 w-3 text-white" viewBox="0 0 12 12" fill="none">
                <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
            ) : null}
          </button>
        ) : null}
      <button
        type="button"
        className="flex min-w-0 flex-1 items-start gap-2 text-left"
        onClick={onToggle}
        disabled={readOnly}
      >
        {/* Index badge */}
        <span className="mt-0.5 shrink-0 rounded bg-slate-700 px-1.5 py-0.5 font-mono text-[10px] text-slate-400">
          {isSpecial ? (item.id ?? index + 1) : `#${index + 1}`}
        </span>
        {/* Act badge */}
        <span className={`mt-0.5 shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold ${actColor}`}>
          {actLabel}
        </span>
        {item.track === "insert" && (
          <span className="mt-0.5 shrink-0 rounded bg-rose-950/50 px-1.5 py-0.5 text-[10px] font-semibold text-rose-200 ring-1 ring-rose-500/30">
            insert
          </span>
        )}
        {item.track === "avatar" && act === "hook" && (
          <span className="mt-0.5 shrink-0 rounded bg-teal-950/50 px-1.5 py-0.5 text-[10px] font-semibold text-teal-200 ring-1 ring-teal-500/30">
            avatar
          </span>
        )}
        {/* Expression badge */}
        {editExpression && (
          <span className="mt-0.5 shrink-0 rounded bg-indigo-950/50 px-1.5 py-0.5 text-[10px] text-indigo-200 ring-1 ring-indigo-500/25">
            {editExpression}
          </span>
        )}
        {/* Preview text */}
        <span className="flex-1 truncate text-[11px] text-slate-300 leading-snug">
          {preview.slice(0, 110)}{preview.length > 110 ? "…" : ""}
        </span>
        {/* Segment snippet */}
        {item.segment_text && (
          <span className="hidden shrink-0 max-w-[140px] truncate text-[10px] text-slate-500 sm:block">
            "{(item.segment_text as string).slice(0, 50)}…"
          </span>
        )}
        {/* Chevron */}
        <span className={`shrink-0 text-slate-500 transition-transform ${expanded ? "rotate-180" : ""}`}>
          ▾
        </span>
      </button>
      </div>

      {/* Expanded editor */}
      {expanded && (
        <div className="border-t border-slate-600 px-3 pb-3 pt-2 space-y-2">
          {/* Original segment text (readonly) */}
          {item.segment_text && (
            <div className="rounded-lg border border-slate-600 bg-slate-900/50 px-2 py-1.5 text-[10px] text-slate-400 italic leading-snug">
              <span className="font-semibold not-italic text-slate-500">Texto original: </span>
              {item.segment_text as string}
            </div>
          )}

          <div className="grid gap-2 sm:grid-cols-2">
            <div>
              <Label>Acto</Label>
              <Select value={editAct} onChange={(e) => setEditAct(e.target.value)} className="!mt-1 !rounded-lg !border-slate-600 !bg-slate-700 !text-slate-200 !text-xs focus:!border-slate-400">
                <option value="hook">Hook</option>
                <option value="intro">Intro (coletilla)</option>
                <option value="body">Body</option>
                <option value="cta">CTA</option>
                <option value="outro">Outro (cierre)</option>
              </Select>
            </div>
            <div>
              <Label>Expresión del avatar</Label>
              <Select value={editExpression} onChange={(e) => setEditExpression(e.target.value)} className="!mt-1 !rounded-lg !border-slate-600 !bg-slate-700 !text-slate-200 !text-xs focus:!border-slate-400">
                <option value="">— sin especificar —</option>
                {EXPRESSIONS.map((ex) => (
                  <option key={ex} value={ex}>{ex}</option>
                ))}
              </Select>
            </div>
          </div>

          <div>
            <Label>Situación (descripción breve)</Label>
            <TextArea
              value={editSituation}
              onChange={(e) => setEditSituation(e.target.value)}
              className="min-h-[48px] !border-slate-600 !bg-slate-700 !text-slate-200 !text-xs placeholder:!text-slate-500 focus:!border-slate-400"
              placeholder="¿Qué hace el avatar? ¿Qué hay de fondo?"
            />
          </div>

          {/* Narration text: show for intro/outro or if it has content */}
          {(isSpecial || editNarration) && (
            <div>
              <Label>Texto de narración (TTS)</Label>
              <TextArea
                value={editNarration}
                onChange={(e) => setEditNarration(e.target.value)}
                className="min-h-[52px] !border-slate-600 !bg-slate-700 !text-slate-200 !text-xs placeholder:!text-slate-500 focus:!border-slate-400"
                placeholder="Texto que leerá el TTS para esta imagen…"
              />
            </div>
          )}

          <div>
            <Label>Prompt IA (ai_prompt)</Label>
            <TextArea
              value={editPrompt}
              onChange={(e) => setEditPrompt(e.target.value)}
              className="min-h-[72px] !border-slate-600 !bg-slate-700 !font-mono !text-xs !text-slate-200 placeholder:!text-slate-500 focus:!border-slate-400"
              placeholder="Prompt completo en inglés para el generador de imágenes…"
            />
          </div>

          <div>
            <Label>Negative prompt</Label>
            <Input
              value={editNeg}
              onChange={(e) => setEditNeg(e.target.value)}
              placeholder="realistic, photorealistic, 3D render…"
              className="!mt-1 !rounded-lg !border-slate-600 !bg-slate-700 !font-mono !text-xs !text-slate-200 placeholder:!text-slate-500 focus:!border-slate-400"
            />
          </div>

          <div className="flex gap-2 pt-1">
            <Btn
              type="button"
              className="bg-white text-slate-900 hover:bg-slate-100"
              onClick={handleSave}
            >
              Guardar cambios
            </Btn>
            <Btn
              type="button"
              className="border border-slate-500 bg-slate-700 text-slate-200 hover:bg-slate-600"
              onClick={onToggle}
            >
              Cerrar
            </Btn>
          </div>
        </div>
      )}
    </div>
  );
}


export function ImagePromptWriterPanel({
  run,
  workApplied,
  refreshPipeline,
  imagePromptStepState,
  scriptWriterStepState = "idle",
}: {
  run: RunFn;
  workApplied: string;
  refreshPipeline: () => Promise<void>;
  imagePromptStepState: string;
  /** Si es «done», ocultamos modo visual (ya fijado en Script Writer). */
  scriptWriterStepState?: string;
}) {
  const [jsonText, setJsonText] = useState("");
  const [hasBundle, setHasBundle] = useState(false);
  const [estimatedPrompts, setEstimatedPrompts] = useState<number | null>(null);
  const [viewMode, setViewMode] = useState<"cards" | "json">("cards");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [pushImagesInfo, setPushImagesInfo] = useState<string | null>(null);
  const [ipwResetInfo, setIpwResetInfo] = useState<string | null>(null);
  const [previewSegment, setPreviewSegment] = useState("");
  const [previewResult, setPreviewResult] = useState<Record<string, unknown> | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [validationCandidates, setValidationCandidates] = useState<ValidationCandidate[]>([]);
  const [validationSelectedIds, setValidationSelectedIds] = useState<Set<string>>(new Set());
  const [validationBusy, setValidationBusy] = useState(false);
  const [validationInfo, setValidationInfo] = useState<string | null>(null);

  // General settings
  const [targetGenerator, setTargetGenerator] = useState<TargetGenerator>("gemini");
  const [visualMode, setVisualMode] = useState<VisualMode>("animation");
  const [appendMjSuffix, setAppendMjSuffix] = useState(true);
  const [exportNegativeSeparate, setExportNegativeSeparate] = useState(true);

  const [useAvatar, setUseAvatar] = useState(false);
  const [hookEssayCounterpoint, setHookEssayCounterpoint] = useState(true);
  const [visualStylePresetId, setVisualStylePresetId] = useState(ALEX_PRESET_ID);

  const generationRunning = imagePromptStepState === "running";

  // ── Loaders ──────────────────────────────────────────────

  const loadBundle = useCallback(async () => {
    const r = await fetch(
      `/api/pipeline/image-prompts?work=${encodeURIComponent(workApplied)}`,
    );
    if (!r.ok) return;
    const j = (await r.json()) as { exists?: boolean; bundle?: Record<string, unknown> | null };
    if (j.exists && j.bundle && typeof j.bundle === "object") {
      setJsonText(JSON.stringify(j.bundle, null, 2));
      setHasBundle(true);
      const b = j.bundle as Record<string, unknown>;
      if (Array.isArray(b.prompts)) setEstimatedPrompts((b.prompts as unknown[]).length);
    } else {
      setJsonText(""); setHasBundle(false); setEstimatedPrompts(null);
    }
  }, [workApplied]);

  const loadSettings = useCallback(async () => {
    const r = await fetch(
      `/api/pipeline/image-prompt-writer-settings?work=${encodeURIComponent(workApplied)}`,
    );
    if (!r.ok) return;
    const j = (await r.json()) as {
      target_generator?: string;
      visual_mode?: string;
      append_midjourney_suffix?: boolean;
      export_negative_separate?: boolean;
      notes?: string;
      use_avatar?: boolean;
      hook_essay_counterpoint?: boolean;
      visual_style_preset_id?: string;
    };
    const tg = j.target_generator;
    const allowed: TargetGenerator[] = ["gemini", "midjourney", "flux", "dall_e", "sd", "custom"];
    setTargetGenerator(tg && allowed.includes(tg as TargetGenerator) ? (tg as TargetGenerator) : "gemini");
    if (typeof j.append_midjourney_suffix === "boolean") setAppendMjSuffix(j.append_midjourney_suffix);
    if (typeof j.export_negative_separate === "boolean") setExportNegativeSeparate(j.export_negative_separate);
    if (typeof j.visual_mode === "string" && ["static", "animation", "combined"].includes(j.visual_mode)) {
      setVisualMode(j.visual_mode as VisualMode);
    }
    if (typeof j.use_avatar === "boolean") setUseAvatar(j.use_avatar);
    if (typeof j.hook_essay_counterpoint === "boolean") {
      setHookEssayCounterpoint(j.hook_essay_counterpoint);
    }
    if (j.visual_style_preset_id) setVisualStylePresetId(j.visual_style_preset_id);
  }, [workApplied]);

  useEffect(() => { void loadBundle(); }, [loadBundle, imagePromptStepState, workApplied]);
  useEffect(() => { void loadSettings(); }, [loadSettings]);

  // ── Persist ───────────────────────────────────────────────

  const saveSettings = async (overrides?: {
    use_avatar?: boolean;
    visual_style_preset_id?: string;
  }) => {
    await putJson("/api/pipeline/image-prompt-writer-settings", {
      work: workApplied,
      target_generator: targetGenerator,
      visual_mode: visualMode,
      append_midjourney_suffix: appendMjSuffix,
      export_negative_separate: exportNegativeSeparate,
      notes: "",
      use_avatar: overrides?.use_avatar ?? useAvatar,
      hook_essay_counterpoint: hookEssayCounterpoint,
      visual_style_preset_id:
        overrides?.visual_style_preset_id ?? (visualStylePresetId || ALEX_PRESET_ID),
    });
    await loadSettings();
  };

  const saveBundle = async () => {
    let parsed: Record<string, unknown>;
    try { parsed = JSON.parse(jsonText) as Record<string, unknown>; }
    catch { alert("JSON no válido. Revisa el formato antes de guardar."); return; }
    await putJson("/api/pipeline/image-prompts", { work: workApplied, bundle: parsed });
    await loadBundle();
    await refreshPipeline();
  };

  const showMidjourneySuffixOption = targetGenerator === "midjourney";
  const showExportNegativeOption = targetGenerator === "sd" || targetGenerator === "flux";
  const showScriptVisualMode = scriptWriterStepState !== "done";

  const loadValidationCandidates = useCallback(async () => {
    const r = await fetch(
      `/api/pipeline/image-prompts/validation-candidates?work=${encodeURIComponent(workApplied)}&limit=24`,
    );
    if (!r.ok) {
      setValidationCandidates([]);
      return;
    }
    const j = (await r.json()) as { candidates?: ValidationCandidate[] };
    const list = Array.isArray(j.candidates) ? j.candidates : [];
    setValidationCandidates(list);
    const defaultIds = list.slice(0, 3).map((c) => c.id);
    setValidationSelectedIds(new Set(defaultIds));
  }, [workApplied]);

  useEffect(() => {
    if (useAvatar) void loadValidationCandidates();
  }, [useAvatar, loadValidationCandidates]);

  const toggleValidationCandidate = (id: string) => {
    setValidationSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else {
        if (next.size >= 3) {
          setValidationInfo("Máximo 3 planos en la muestra de validación.");
          return prev;
        }
        next.add(id);
      }
      return next;
    });
  };

  const buildValidationSample = async () => {
    const ids = [...validationSelectedIds];
    if (ids.length === 0) {
      setValidationInfo("Selecciona al menos un plano avatar (máx. 3).");
      return;
    }
    setValidationBusy(true);
    setValidationInfo(null);
    try {
      const res = await postJson<{
        prompt_count?: number;
        added?: number;
        replaced?: number;
        merged?: boolean;
      }>("/api/pipeline/image-prompts/build-validation-sample", {
        work: workApplied,
        candidate_ids: ids,
      });
      const total = res.prompt_count ?? ids.length;
      const parts: string[] = [];
      if (res.added) parts.push(`${res.added} nuevos`);
      if (res.replaced) parts.push(`${res.replaced} actualizados`);
      const mergeNote =
        parts.length > 0
          ? ` Fusionado en salida (${parts.join(", ")}); inserts y demás prompts conservados.`
          : res.merged
            ? " Fusionado en salida; el resto de prompts se mantiene."
            : "";
      setValidationInfo(
        `Listo: ${total} prompts en total.${mergeNote} Revisa las ✓ y envía a Images Generation.`,
      );
      await loadBundle();
      await refreshPipeline();
    } catch (e) {
      setValidationInfo(e instanceof Error ? e.message : "Error generando muestra");
    } finally {
      setValidationBusy(false);
    }
  };

  const loadPreviewFromBodyRouter = useCallback(async () => {
    const r = await fetch(
      `/api/pipeline/body-router-artifact?work=${encodeURIComponent(workApplied)}`,
    );
    if (!r.ok) return;
    const j = (await r.json()) as { exists?: boolean; artifact?: Record<string, unknown> };
    const beats = j.artifact?.macro_beats;
    if (!Array.isArray(beats)) return;
    const avatarBeat = beats.find(
      (b) =>
        typeof b === "object" &&
        b !== null &&
        String((b as Record<string, unknown>).track || "avatar").toLowerCase() === "avatar",
    ) as Record<string, unknown> | undefined;
    const anchor = String(avatarBeat?.text_anchor || avatarBeat?.purpose || "").trim();
    if (anchor) setPreviewSegment(anchor);
  }, [workApplied]);

  const parsedPrompts = useMemo((): PromptItem[] => {
    try {
      const b = JSON.parse(jsonText) as Record<string, unknown>;
      if (Array.isArray(b.prompts)) return b.prompts as PromptItem[];
    } catch { /* invalid */ }
    return [];
  }, [jsonText]);

  const bundleHybrid = useMemo(() => {
    try {
      const b = JSON.parse(jsonText) as Record<string, unknown>;
      const src = String(b.source ?? "");
      const tracks = b.hybrid_tracks as { avatar?: number; insert?: number } | undefined;
      return {
        isHybrid: Boolean(b.hybrid_mode) || src === "avatar_hybrid",
        avatar: tracks?.avatar,
        insert: tracks?.insert,
      };
    } catch {
      return { isHybrid: false, avatar: undefined, insert: undefined };
    }
  }, [jsonText]);

  const bundleMeta = useMemo(() => {
    try {
      const b = JSON.parse(jsonText) as Record<string, unknown>;
      const hasExplicitSelection = parsedPrompts.some((p) => p.selected !== undefined);
      const exportCount = hasExplicitSelection
        ? parsedPrompts.filter((p) => p.selected !== false).length
        : parsedPrompts.length;
      return {
        isValidationSample: Boolean(b.validation_sample) || b.source === "validation_sample",
        hasExplicitSelection,
        exportCount,
      };
    } catch {
      return {
        isValidationSample: false,
        hasExplicitSelection: false,
        exportCount: 0,
      };
    }
  }, [jsonText, parsedPrompts]);

  const togglePromptExport = useCallback((index: number) => {
    setJsonText((prev) => {
      try {
        const bundle = JSON.parse(prev) as Record<string, unknown>;
        const prompts = Array.isArray(bundle.prompts) ? [...(bundle.prompts as PromptItem[])] : [];
        if (!prompts[index]) return prev;
        const cur = prompts[index];
        const included = cur.selected !== false;
        prompts[index] = { ...cur, selected: !included };
        return JSON.stringify({ ...bundle, prompts }, null, 2);
      } catch {
        return prev;
      }
    });
  }, []);

  const setAllPromptsExport = useCallback((selected: boolean) => {
    setJsonText((prev) => {
      try {
        const bundle = JSON.parse(prev) as Record<string, unknown>;
        const prompts = Array.isArray(bundle.prompts) ? [...(bundle.prompts as PromptItem[])] : [];
        if (!prompts.length) return prev;
        return JSON.stringify(
          {
            ...bundle,
            prompts: prompts.map((p) => ({ ...p, selected })),
          },
          null,
          2,
        );
      } catch {
        return prev;
      }
    });
  }, []);

  const updatePromptAt = useCallback((index: number, updated: PromptItem) => {
    setJsonText((prev) => {
      try {
        const bundle = JSON.parse(prev) as Record<string, unknown>;
        const prompts = Array.isArray(bundle.prompts) ? [...(bundle.prompts as PromptItem[])] : [];
        if (!prompts.length) return prev;
        prompts[index] = updated;
        return JSON.stringify({ ...bundle, prompts }, null, 2);
      } catch {
        return prev;
      }
    });
    setExpandedId(null);
  }, []);

  const pushToImagesGeneration = async () => {
    if (!parsedPrompts.length) {
      alert("No hay prompts para enviar. Guarda image_prompts.json primero.");
      return;
    }
    const exportCount = bundleMeta.exportCount;
    if (exportCount === 0) {
      alert("Marca al menos un prompt con ✓ en la salida antes de enviar.");
      return;
    }
    if (
      !window.confirm(
        `Se reemplazará el manifest de Images Generation con ${exportCount} escena(s) (solo las marcadas con ✓).\n\n` +
          "Las imágenes del proyecto anterior dejarán de aparecer en la UI (no se borran del disco).\n\n¿Continuar?",
      )
    ) {
      return;
    }
    const res = (await postJson("/api/pipeline/image-prompts/push-to-images-generation", {
      work: workApplied,
    })) as { total?: number; pending?: number; generated?: number };
    setPushImagesInfo(
      `Enviado: ${res.total ?? parsedPrompts.length} escenas (${res.pending ?? "?"} pendientes, ${res.generated ?? 0} ya en disco).`,
    );
    await refreshPipeline();
  };

  return (
    <div className="rounded-2xl bg-slate-900 p-4 space-y-3">
      <div className="rounded-xl border border-amber-500/40 bg-amber-950/30 px-3 py-2 text-xs text-amber-300">
        <span className="font-semibold">Image Prompt Writer.</span> Con Hook + Body Router listos: activa{" "}
        <strong className="text-amber-100">modo avatar</strong>, guarda estilo, elige{" "}
        <strong className="text-amber-100">Gemini</strong> como generador y pulsa{" "}
        <strong className="text-amber-100">Start step</strong> (construye{" "}
        <code className="rounded bg-amber-900/50 px-1">image_prompts.json</code> desde los routers). En el gancho,
        activa <strong className="text-amber-100">contrapunto ensayo</strong> para no ilustrar la narración al pie de
        la letra. Revisa la salida y envía a Images Generation.
      </div>

      <PipelineStepConfirmBar
        stepId="image_prompt_writer"
        stepLabel="Image Prompt Writer"
        workApplied={workApplied}
        stepState={imagePromptStepState}
        run={run}
        onAfterRun={refreshPipeline}
      />

      {generationRunning && (
        <div className="rounded-xl border border-amber-500/40 bg-amber-950/30 px-3 py-2 text-xs text-amber-300">
          Ejecutando paso… el editor puede quedar en solo lectura hasta que termine.
        </div>
      )}

      <Section
        id="ipw-avatar"
        badge="1"
        title="Modo avatar · generador y estilo"
        description="El generador objetivo define el formato del ai_prompt que escribe el LLM en filas avatar. Start step usa Hook + Body Router; los inserts no gastan tokens de avatar."
      >
        <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-[11px] font-semibold text-slate-200">Modo avatar (prompts por segmento)</p>
            <p className="mt-0.5 text-[10px] text-slate-500">
              Actívalo para definir el estilo visual guardado y generar prompts por segmento en{" "}
              <strong className="text-slate-400">Start step</strong>. Si existe Hook Scene Router, el gancho
              mezcla <strong className="text-slate-400">avatar</strong> (personaje) e <strong className="text-slate-400">insert</strong> (B-roll).
            </p>
          </div>
          <IosSwitch
            checked={useAvatar}
            onChange={(v) => {
              const pid = visualStylePresetId || ALEX_PRESET_ID;
              setUseAvatar(v);
              if (v && !visualStylePresetId) setVisualStylePresetId(ALEX_PRESET_ID);
              void saveSettings({ use_avatar: v, visual_style_preset_id: pid });
            }}
            disabled={generationRunning}
            aria-label="Activar modo avatar"
          />
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-violet-500/30 bg-violet-950/20 px-3 py-2">
          <div className="min-w-0 flex-1">
            <p className="text-[11px] font-semibold text-violet-200">Gancho · contrapunto ensayo (LLM)</p>
            <p className="mt-0.5 text-[10px] text-slate-500">
              Reescribe los inserts del hook con emoción/subtexto/contraste — no pasa el texto narrado al LLM. Desactiva
              solo si quieres los prompts literales del Hook Router.
            </p>
          </div>
          <IosSwitch
            checked={hookEssayCounterpoint}
            onChange={(v) => {
              setHookEssayCounterpoint(v);
              void saveSettings();
            }}
            disabled={generationRunning}
            aria-label="Contrapunto ensayo en gancho"
          />
        </div>

        <div className="rounded-lg border border-slate-700 bg-slate-900/40 p-3 space-y-3">
          <div>
            <Label>Generador objetivo</Label>
            <Select
              value={targetGenerator}
              disabled={generationRunning}
              onChange={(e) => setTargetGenerator(e.target.value as TargetGenerator)}
              className="!mt-1"
            >
              <option value="gemini">Gemini / Nano Banana (cola en Images)</option>
              <option value="midjourney">Midjourney</option>
              <option value="flux">Flux</option>
              <option value="dall_e">DALL·E</option>
              <option value="sd">Stable Diffusion / SDXL</option>
              <option value="custom">Personalizado</option>
            </Select>
            {targetGenerator === "gemini" ? (
              <p className="mt-1 text-[10px] text-slate-500">
                Prompts en prosa inglesa densa; sin sufijos <code className="rounded bg-slate-800 px-1">--ar</code>.
              </p>
            ) : null}
          </div>

          {(showMidjourneySuffixOption || showExportNegativeOption) && (
            <div className="space-y-2">
              {showMidjourneySuffixOption && (
                <div className="flex items-center justify-between gap-3 rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-2.5">
                  <span className="text-xs text-slate-300">
                    Sufijo Midjourney en <code className="rounded bg-slate-700 px-1">global_style</code>
                  </span>
                  <IosSwitch
                    checked={appendMjSuffix}
                    onChange={setAppendMjSuffix}
                    disabled={generationRunning}
                    aria-label="Sufijo Midjourney"
                  />
                </div>
              )}
              {showExportNegativeOption && (
                <div className="flex items-center justify-between gap-3 rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-2.5">
                  <span className="text-xs text-slate-300">Negative por separado (Flux / SD)</span>
                  <IosSwitch
                    checked={exportNegativeSeparate}
                    onChange={setExportNegativeSeparate}
                    disabled={generationRunning}
                    aria-label="Negative por separado"
                  />
                </div>
              )}
            </div>
          )}

          {showScriptVisualMode ? (
            <div>
              <Label>Modo visual del guion</Label>
              <Select
                value={visualMode}
                disabled={generationRunning}
                onChange={(e) => setVisualMode(e.target.value as VisualMode)}
                className="!mt-1"
              >
                <option value="static">Estático (sin B-roll en guion)</option>
                <option value="animation">Animación (B-roll en guion)</option>
                <option value="combined">Combinado</option>
              </Select>
              <p className="mt-1 text-[10px] text-slate-500">
                Afecta al Script Writer si aún no lo has ejecutado. Tras generar el guion, este control se oculta.
              </p>
            </div>
          ) : (
            <p className="text-[10px] text-slate-500">
              Modo visual del guion ya fijado (Script Writer completado).
            </p>
          )}
        </div>

        {useAvatar ? (
          <VisualStylePanel
            work={workApplied}
            theme="dark"
            presetId={visualStylePresetId}
            onPresetIdChange={(id) => {
              setVisualStylePresetId(id);
              void saveSettings({ visual_style_preset_id: id });
            }}
            showPresetControls
            onSaved={() => {
              void refreshPipeline();
              void saveSettings();
            }}
          />
        ) : (
          <p className="text-[11px] text-slate-500">
            Activa el modo avatar para que Start step enriquezca las filas <code className="rounded bg-slate-800 px-1">track: avatar</code> con el LLM.
          </p>
        )}

        {useAvatar ? (
          <div className="rounded-xl border border-cyan-500/30 bg-cyan-950/20 p-3 space-y-3">
            <div>
              <p className="text-[11px] font-semibold text-cyan-200">Validación · 2–3 imágenes</p>
              <p className="mt-1 text-[10px] leading-relaxed text-slate-500">
                Elige hasta <strong className="text-slate-400">3 planos avatar</strong> (gancho + cuerpo). Se generan
                prompts con LLM y se <strong className="text-slate-400">fusionan en salida</strong> (no borran inserts ni
                otros prompts). Mismo <code className="rounded bg-slate-800 px-1">id</code> = se sobrescribe; id nuevo =
                se añade al final.
              </p>
            </div>
            {validationCandidates.length === 0 ? (
              <p className="text-[10px] text-amber-300/90">
                No hay candidatos avatar. Ejecuta Hook + Body Scene Router y recarga esta página.
              </p>
            ) : (
              <ul className="max-h-48 space-y-1.5 overflow-y-auto rounded-lg border border-cyan-500/20 bg-slate-900/50 p-2">
                {validationCandidates.map((c) => {
                  const checked = validationSelectedIds.has(c.id);
                  return (
                    <li key={c.id}>
                      <label className="flex cursor-pointer items-start gap-2 rounded-md px-1 py-1 hover:bg-slate-800/60">
                        <input
                          type="checkbox"
                          className="mt-0.5 rounded border-slate-500"
                          checked={checked}
                          disabled={generationRunning || validationBusy}
                          onChange={() => toggleValidationCandidate(c.id)}
                        />
                        <span className="min-w-0 flex-1 text-[10px] text-slate-300">
                          <span className="font-mono text-cyan-200/90">{c.id}</span>
                          <span className="text-slate-500"> · {c.source}</span>
                          <span className="block truncate text-slate-400">{c.text_anchor || "(sin ancla)"}</span>
                        </span>
                      </label>
                    </li>
                  );
                })}
              </ul>
            )}
            <div className="flex flex-wrap gap-2">
              <Btn
                type="button"
                className="bg-cyan-600 text-white hover:bg-cyan-500 disabled:opacity-40"
                disabled={
                  generationRunning ||
                  validationBusy ||
                  validationSelectedIds.size === 0 ||
                  validationCandidates.length === 0
                }
                onClick={() => run("Muestra validación → image_prompts", buildValidationSample)}
              >
                {validationBusy
                  ? "Generando prompts…"
                  : `Generar muestra (${validationSelectedIds.size}) → salida`}
              </Btn>
              <button
                type="button"
                className="rounded-lg border border-slate-600 px-2 py-1 text-[10px] text-slate-400 hover:bg-slate-800"
                onClick={() => void loadValidationCandidates()}
              >
                Recargar candidatos
              </button>
            </div>
            {validationInfo ? (
              <p className="rounded-lg border border-cyan-500/30 bg-cyan-950/40 px-2 py-1.5 text-[10px] text-cyan-100">
                {validationInfo}
              </p>
            ) : null}

            <details className="text-[10px] text-slate-500">
              <summary className="cursor-pointer text-slate-400 hover:text-slate-300">
                Probar un solo fragmento (1 LLM, sin guardar)
              </summary>
              <div className="mt-2 space-y-2">
                <TextArea
                  value={previewSegment}
                  onChange={(e) => setPreviewSegment(e.target.value)}
                  disabled={generationRunning || previewBusy}
                  className="min-h-[56px] !border-slate-600 !bg-slate-800 !text-xs !text-slate-200"
                  placeholder="text_anchor de un macro_beat avatar…"
                />
                <div className="flex flex-wrap gap-2">
                  <Btn
                    type="button"
                    className="border border-cyan-500/50 bg-cyan-950/40 text-cyan-100 text-[11px] disabled:opacity-40"
                    disabled={generationRunning || previewBusy || !previewSegment.trim()}
                    onClick={async () => {
                      setPreviewBusy(true);
                      setPreviewResult(null);
                      try {
                        const res = await postJson<Record<string, unknown>>(
                          "/api/pipeline/image-prompts/preview-avatar",
                          { work: workApplied, segment_text: previewSegment.trim() },
                        );
                        setPreviewResult(res);
                      } catch (e) {
                        setPreviewResult({ error: e instanceof Error ? e.message : "Error" });
                      } finally {
                        setPreviewBusy(false);
                      }
                    }}
                  >
                    {previewBusy ? "Llamando…" : "Vista previa LLM"}
                  </Btn>
                  <button
                    type="button"
                    className="rounded border border-slate-600 px-2 py-0.5 text-[10px] text-slate-400"
                    onClick={() => void loadPreviewFromBodyRouter()}
                  >
                    Cargar 1.er beat
                  </button>
                </div>
                {previewResult && !("error" in previewResult) ? (
                  <pre className="max-h-32 overflow-auto whitespace-pre-wrap rounded border border-slate-600 bg-slate-900/60 p-2 font-mono text-[9px] text-emerald-200/90">
                    {String(previewResult.ai_prompt || "")}
                  </pre>
                ) : null}
              </div>
            </details>
          </div>
        ) : null}

        <Btn
          type="button"
          className="bg-white text-slate-900 hover:bg-slate-100 disabled:opacity-40"
          disabled={generationRunning}
          onClick={() => run("Guardar ajustes Image Prompt Writer", saveSettings)}
        >
          Guardar ajustes
        </Btn>
        </div>
      </Section>

      <div className="rounded-xl border border-slate-600 bg-slate-800/60 px-4 py-3">
        <div className="text-xs font-semibold text-slate-300">Referencia · campos del JSON</div>
        <p className="mt-1 text-[11px] text-slate-500">Lo que espera el paso de imágenes y exportaciones externas.</p>
        <ul className="mt-2 list-disc space-y-1 pl-4 text-[11px] leading-relaxed text-slate-400">
          <li><code className="rounded bg-slate-700 px-1 text-slate-200">version</code>, <code className="rounded bg-slate-700 px-1 text-slate-200">source</code>, <code className="rounded bg-slate-700 px-1 text-slate-200">global_style</code></li>
          <li>
            <code className="rounded bg-slate-700 px-1 text-slate-200">prompts[]</code>: <code className="rounded bg-slate-700 px-1 text-slate-200">track</code> (<code className="rounded bg-slate-700 px-1 text-slate-200">avatar</code> | <code className="rounded bg-slate-700 px-1 text-slate-200">insert</code>), <code className="rounded bg-slate-700 px-1 text-slate-200">id</code>, <code className="rounded bg-slate-700 px-1 text-slate-200">act</code>, <code className="rounded bg-slate-700 px-1 text-slate-200">timing</code>, <code className="rounded bg-slate-700 px-1 text-slate-200">ai_prompt</code>
          </li>
          <li>Formato legacy: <code className="rounded bg-slate-700 px-1 text-slate-200">role</code> + <code className="rounded bg-slate-700 px-1 text-slate-200">text</code> (válido)</li>
        </ul>
      </div>

      <Section
        id="ipw-output"
        badge="2"
        title="Salida · image_prompts.json"
        description="Marca con ✓ los prompts a exportar. En Images Generation podrás volver a elegir tarjetas antes de la cola Gemini."
      >
      <div className="space-y-2">
        {bundleMeta.isValidationSample ? (
          <p className="rounded-xl border border-cyan-500/40 bg-cyan-950/30 px-3 py-2 text-[11px] text-cyan-200">
            <strong className="text-cyan-100">Bundle con muestras fusionadas.</strong> Inserts y demás prompts se
            conservan. Revisa las ✓ y pulsa <strong className="text-cyan-100">Enviar a Images Generation</strong>.
            Regenerar el mismo <code className="rounded bg-cyan-900/50 px-1">id</code> en validación lo actualiza.
          </p>
        ) : null}

        {parsedPrompts.length > 0 ? (
          <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
            <span>
              Exportar:{" "}
              <strong className="text-slate-200">{bundleMeta.exportCount}</strong>
              / {parsedPrompts.length}
            </span>
            <button
              type="button"
              className="rounded border border-slate-600 px-2 py-0.5 hover:bg-slate-800"
              disabled={generationRunning}
              onClick={() => setAllPromptsExport(true)}
            >
              Marcar todos
            </button>
            <button
              type="button"
              className="rounded border border-slate-600 px-2 py-0.5 hover:bg-slate-800"
              disabled={generationRunning}
              onClick={() => setAllPromptsExport(false)}
            >
              Desmarcar todos
            </button>
            <span className="text-slate-500">✓ en tarjeta = se incluye en Images Generation</span>
          </div>
        ) : null}

        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="sr-only">Acciones salida</div>
          <div className="flex flex-wrap items-center gap-1.5">
            <div className="flex overflow-hidden rounded-lg border border-slate-600 text-xs">
              <button
                type="button"
                className={`px-2.5 py-1 transition-colors ${viewMode === "cards" ? "bg-white text-slate-900" : "bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-slate-200"}`}
                onClick={() => setViewMode("cards")}
              >
                Tarjetas
              </button>
              <button
                type="button"
                className={`px-2.5 py-1 transition-colors ${viewMode === "json" ? "bg-white text-slate-900" : "bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-slate-200"}`}
                onClick={() => setViewMode("json")}
              >
                JSON
              </button>
            </div>
            <Btn type="button" className="border border-slate-600 bg-slate-800 text-slate-200 hover:bg-slate-700"
              onClick={() => void loadBundle()}>
              Recargar desde disco
            </Btn>
            <Btn
              type="button"
              className="border border-sky-500/50 bg-sky-950/40 text-sky-200 hover:bg-sky-900/50 disabled:opacity-40"
              disabled={
                generationRunning ||
                parsedPrompts.length === 0 ||
                (bundleMeta.hasExplicitSelection && bundleMeta.exportCount === 0)
              }
              onClick={() => run("Enviar a Images Generation", pushToImagesGeneration)}
            >
              Enviar a Images Generation
              {bundleMeta.exportCount > 0 && bundleMeta.exportCount < parsedPrompts.length
                ? ` (${bundleMeta.exportCount})`
                : ""}
            </Btn>
            <Btn type="button" className="bg-white text-slate-900 hover:bg-slate-100 disabled:opacity-40"
              disabled={generationRunning || !jsonText.trim()}
              onClick={() => run("Guardar image_prompts.json", saveBundle)}>
              Guardar y marcar listo
            </Btn>
            <ProductionResetButton
              workApplied={workApplied}
              scope="image_prompts"
              label="Nuevo proyecto (prompts)"
              disabled={generationRunning}
              onDone={async (msg) => {
                setIpwResetInfo(msg);
                setJsonText("");
                setHasBundle(false);
                setExpandedId(null);
                await loadBundle();
                await refreshPipeline();
              }}
            />
          </div>
        </div>

        {ipwResetInfo ? (
          <p className="rounded-lg border border-rose-500/40 bg-rose-950/30 px-3 py-2 text-[11px] text-rose-200">
            {ipwResetInfo}
          </p>
        ) : null}

        {bundleHybrid.isHybrid && (
          <p className="rounded-xl border border-teal-500/40 bg-teal-950/30 px-3 py-2 text-[11px] text-teal-200">
            Modo <strong className="text-teal-100">avatar híbrido</strong>
            {bundleHybrid.avatar != null && bundleHybrid.insert != null
              ? `: ${bundleHybrid.avatar} pista avatar + ${bundleHybrid.insert} inserts (hook).`
              : ": gancho intercalado según Hook Scene Router."}
          </p>
        )}

        {parsedPrompts.length > 0 && (
          <div className="text-[11px] text-slate-500">
            <span className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-slate-400">{parsedPrompts.length}</span>
            {" "}prompts en el array actual
          </div>
        )}

        {pushImagesInfo ? (
          <p className="rounded-xl border border-emerald-500/40 bg-emerald-950/30 px-3 py-2 text-[11px] text-emerald-200">
            {pushImagesInfo}
          </p>
        ) : null}

        {viewMode === "cards" && (
          parsedPrompts.length > 0 ? (
            <div className="space-y-1 max-h-[620px] overflow-y-auto rounded-xl border border-slate-600 bg-slate-800 p-2 shadow-inner">
              {parsedPrompts.map((item, i) => {
                const cardKey = item.id != null ? String(item.id) : String(i);
                return (
                  <PromptCard
                    key={cardKey}
                    item={item}
                    index={i}
                    expanded={expandedId === cardKey}
                    onToggle={() => setExpandedId(expandedId === cardKey ? null : cardKey)}
                    onSave={(updated) => updatePromptAt(i, updated)}
                    readOnly={generationRunning}
                    showExportSelect={parsedPrompts.length > 0}
                    onToggleExportSelect={() => togglePromptExport(i)}
                  />
                );
              })}
            </div>
          ) : (
            <div className="min-h-[120px] rounded-xl border border-dashed border-slate-600 bg-slate-800 px-4 py-6 text-center text-xs text-slate-500 shadow-inner"
            >
              {hasBundle
                ? "El bundle no contiene prompts en el array esperado."
                : "Aún no hay bundle. Guarda ajustes (paso 1) y ejecuta «Start step»."}
            </div>
          )
        )}

        {viewMode === "json" && (
          <>
            <ExpandableTextArea
              value={jsonText}
              onChange={setJsonText}
              placeholder={hasBundle ? "" : "Aún no hay bundle."}
              modalTitle="pipeline/image_prompts.json"
              variant="output"
              disabled={generationRunning}
              disabledTitle={generationRunning ? "No disponible mientras se genera" : undefined}
            />
            <p className="text-[11px] leading-snug text-slate-500">
              Clic en el recuadro o «✎ editar» para pantalla completa. Confirma con <strong className="text-slate-300">Guardar y marcar listo</strong> para escribir disco.
            </p>
          </>
        )}
      </div>
      </Section>
    </div>
  );
}
