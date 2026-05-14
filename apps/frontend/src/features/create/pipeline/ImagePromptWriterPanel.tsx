import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Btn, ExpandableTextArea, Input, IosSwitch, Label, Select, TextArea } from "../../../components/ui";
import { postJson, putJson, deleteReq } from "../../../services/api";
import type { RunFn } from "../types";
import { PipelineSection as Section } from "./PipelineSection";

type TargetGenerator = "midjourney" | "flux" | "dall_e" | "sd" | "custom";

const AVATAR_DEFAULT_DESCRIPTION =
  "chibi cartoon boy, round thick-frame glasses, chubby face, short messy brown hair, " +
  "light blue button-up shirt with small chest pocket, dark navy pants, simple flat shoes, " +
  "flat 2D cartoon illustration, thick black outline";

interface AvatarSummary {
  id: string;
  name: string;
  created_at: string;
  bundled: boolean;
}

interface AvatarFull extends AvatarSummary {
  description: string;
  expressions: string[];
  style_notes: string;
  intro_enabled: boolean;
  intro_character_name: string;
  outro_enabled: boolean;
  outro_character_name: string;
}

// ── Types for individual prompts ──────────────────────────────────────────
interface PromptItem {
  id?: string;
  act?: string;
  role?: string;
  expression?: string;
  situation?: string;
  narration_text?: string;
  ai_prompt?: string;
  negative_prompt?: string;
  segment_text?: string;
  // legacy
  text?: string;
  [key: string]: unknown;
}

const ACT_COLORS: Record<string, string> = {
  hook:  "bg-amber-950/50 text-amber-300 ring-1 ring-amber-500/30",
  intro: "bg-violet-950/40 text-violet-200 ring-1 ring-violet-500/30",
  body:  "bg-slate-600 text-slate-200",
  cta:   "bg-sky-950/40 text-sky-200 ring-1 ring-sky-500/30",
  outro: "bg-emerald-950/40 text-emerald-200 ring-1 ring-emerald-500/30",
};
const ACT_LABELS: Record<string, string> = {
  hook: "Hook", intro: "Intro", body: "Body", cta: "CTA", outro: "Outro",
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
}: {
  item: PromptItem;
  index: number;
  expanded: boolean;
  onToggle: () => void;
  onSave: (updated: PromptItem) => void;
  readOnly: boolean;
}) {
  const act = item.act ?? (item.role?.includes("intro") ? "intro" : item.role?.includes("outro") ? "outro" : "body");
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
      <button
        type="button"
        className="flex w-full items-start gap-2 px-3 py-2 text-left"
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
}: {
  run: RunFn;
  workApplied: string;
  refreshPipeline: () => Promise<void>;
  imagePromptStepState: string;
}) {
  const [jsonText, setJsonText] = useState("");
  const [hasBundle, setHasBundle] = useState(false);
  const [estimatedPrompts, setEstimatedPrompts] = useState<number | null>(null);
  const [viewMode, setViewMode] = useState<"cards" | "json">("cards");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // General settings
  const [targetGenerator, setTargetGenerator] = useState<TargetGenerator>("midjourney");
  const [appendMjSuffix, setAppendMjSuffix] = useState(true);
  const [exportNegativeSeparate, setExportNegativeSeparate] = useState(true);
  const [settingsNotes, setSettingsNotes] = useState("");

  // Avatar settings
  const [useAvatar, setUseAvatar] = useState(false);
  const [avatarSecsPerImage, setAvatarSecsPerImage] = useState(6);
  const [avatarMaxImages, setAvatarMaxImages] = useState(80);

  // Avatar selector from store
  const [avatarList, setAvatarList] = useState<AvatarSummary[]>([]);
  const [selectedAvatarId, setSelectedAvatarId] = useState("");
  const [selectedAvatarFull, setSelectedAvatarFull] = useState<AvatarFull | null>(null);

  // Avatar editor
  const [showAvatarEditor, setShowAvatarEditor] = useState(false);
  const [editingAvatarId, setEditingAvatarId] = useState<string | null>(null); // null = new
  const [editorName, setEditorName] = useState("");
  const [editorDescription, setEditorDescription] = useState(AVATAR_DEFAULT_DESCRIPTION);
  const [editorStyleNotes, setEditorStyleNotes] = useState("");
  const [editorIntroEnabled, setEditorIntroEnabled] = useState(true);
  const [editorIntroCharacterName, setEditorIntroCharacterName] = useState("");
  const [editorOutroEnabled, setEditorOutroEnabled] = useState(true);
  const [editorOutroCharacterName, setEditorOutroCharacterName] = useState("");

  const generationRunning = imagePromptStepState === "running";

  // ── Loaders ──────────────────────────────────────────────

  const loadAvatarList = useCallback(async () => {
    const r = await fetch("/api/avatars");
    if (!r.ok) return;
    const j = (await r.json()) as { avatars: AvatarSummary[] };
    setAvatarList(j.avatars ?? []);
  }, []);

  const loadAvatarDetail = useCallback(async (id: string) => {
    if (!id) { setSelectedAvatarFull(null); return; }
    const r = await fetch(`/api/avatars/${encodeURIComponent(id)}`);
    if (!r.ok) { setSelectedAvatarFull(null); return; }
    const j = (await r.json()) as AvatarFull;
    setSelectedAvatarFull(j);
  }, []);

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
      append_midjourney_suffix?: boolean;
      export_negative_separate?: boolean;
      notes?: string;
      use_avatar?: boolean;
      avatar_id?: string;
      avatar_secs_per_image?: number;
      avatar_max_images?: number;
    };
    const tg = j.target_generator;
    const allowed: TargetGenerator[] = ["midjourney", "flux", "dall_e", "sd", "custom"];
    setTargetGenerator(tg && allowed.includes(tg as TargetGenerator) ? (tg as TargetGenerator) : "midjourney");
    if (typeof j.append_midjourney_suffix === "boolean") setAppendMjSuffix(j.append_midjourney_suffix);
    if (typeof j.export_negative_separate === "boolean") setExportNegativeSeparate(j.export_negative_separate);
    if (j.notes !== undefined) setSettingsNotes(j.notes);
    if (typeof j.use_avatar === "boolean") setUseAvatar(j.use_avatar);
    if (typeof j.avatar_secs_per_image === "number") setAvatarSecsPerImage(j.avatar_secs_per_image);
    if (typeof j.avatar_max_images === "number") setAvatarMaxImages(j.avatar_max_images);
    const savedId = j.avatar_id ?? "";
    setSelectedAvatarId(savedId);
    await loadAvatarDetail(savedId);
  }, [workApplied, loadAvatarDetail]);

  useEffect(() => { void loadBundle(); }, [loadBundle, imagePromptStepState, workApplied]);
  useEffect(() => { void loadSettings(); void loadAvatarList(); }, [loadSettings, loadAvatarList]);

  // When avatar selection changes, load detail
  useEffect(() => { void loadAvatarDetail(selectedAvatarId); }, [selectedAvatarId, loadAvatarDetail]);

  // ── Persist ───────────────────────────────────────────────

  const saveSettings = async () => {
    const desc = selectedAvatarFull?.description ?? AVATAR_DEFAULT_DESCRIPTION;
    await putJson("/api/pipeline/image-prompt-writer-settings", {
      work: workApplied,
      target_generator: targetGenerator,
      append_midjourney_suffix: appendMjSuffix,
      export_negative_separate: exportNegativeSeparate,
      notes: settingsNotes.trim(),
      use_avatar: useAvatar,
      avatar_id: selectedAvatarId,
      avatar_description: desc,
      avatar_secs_per_image: avatarSecsPerImage,
      avatar_max_images: avatarMaxImages,
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

  // ── Avatar CRUD ──────────────────────────────────────────

  const openNewAvatarEditor = () => {
    setEditingAvatarId(null);
    setEditorName("");
    setEditorDescription(AVATAR_DEFAULT_DESCRIPTION);
    setEditorStyleNotes("");
    setEditorIntroEnabled(true);
    setEditorIntroCharacterName("");
    setEditorOutroEnabled(true);
    setEditorOutroCharacterName("");
    setShowAvatarEditor(true);
  };

  const openEditAvatarEditor = (av: AvatarFull) => {
    setEditingAvatarId(av.id);
    setEditorName(av.name);
    setEditorDescription(av.description);
    setEditorStyleNotes(av.style_notes);
    setEditorIntroEnabled(av.intro_enabled);
    setEditorIntroCharacterName(av.intro_character_name);
    setEditorOutroEnabled(av.outro_enabled);
    setEditorOutroCharacterName(av.outro_character_name);
    setShowAvatarEditor(true);
  };

  const saveAvatarEditor = async () => {
    if (!editorName.trim()) { alert("El avatar necesita un nombre."); return; }
    const payload = {
      name: editorName.trim(),
      description: editorDescription.trim(),
      style_notes: editorStyleNotes.trim(),
      intro_enabled: editorIntroEnabled,
      intro_character_name: editorIntroCharacterName.trim() || editorName.trim(),
      outro_enabled: editorOutroEnabled,
      outro_character_name: editorOutroCharacterName.trim() || editorName.trim(),
    };
    if (editingAvatarId) {
      await putJson(`/api/avatars/${editingAvatarId}`, payload);
    } else {
      const created = (await postJson("/api/avatars", payload)) as AvatarFull;
      setSelectedAvatarId(created.id);
    }
    await loadAvatarList();
    setShowAvatarEditor(false);
  };

  const deleteSelectedAvatar = async () => {
    if (!selectedAvatarId || selectedAvatarFull?.bundled) return;
    if (!confirm(`¿Eliminar el avatar "${selectedAvatarFull?.name ?? selectedAvatarId}"?`)) return;
    await deleteReq(`/api/avatars/${selectedAvatarId}`);
    setSelectedAvatarId("");
    setSelectedAvatarFull(null);
    await loadAvatarList();
  };

  // ── Derived UI ────────────────────────────────────────────

  const estimatedLabel = avatarSecsPerImage > 0
    ? `≈ ${Math.min(avatarMaxImages, Math.round(300 / avatarSecsPerImage))}–${Math.min(avatarMaxImages, Math.round(600 / avatarSecsPerImage))} imgs para 5-10 min de narración`
    : "";

  const showMidjourneySuffixOption = targetGenerator === "midjourney";
  const showExportNegativeOption = targetGenerator === "sd" || targetGenerator === "flux";

  const parsedPrompts = useMemo((): PromptItem[] => {
    try {
      const b = JSON.parse(jsonText) as Record<string, unknown>;
      if (Array.isArray(b.prompts)) return b.prompts as PromptItem[];
    } catch { /* invalid */ }
    return [];
  }, [jsonText]);

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

  return (
    <div className="rounded-2xl bg-slate-900 p-4 space-y-3">
      <div className="rounded-xl border border-amber-500/40 bg-amber-950/30 px-3 py-2 text-xs text-amber-300">
        <span className="font-semibold">Image Prompt Writer.</span> Orden recomendado:{" "}
        <strong className="text-amber-100">1</strong> generador y exportación,{" "}
        <strong className="text-amber-100">2</strong> importar desde Hook o Metadata,{" "}
        <strong className="text-amber-100">3</strong> modo avatar solo si lo necesitas, luego revisa la{" "}
        <strong className="text-amber-100">salida</strong> abajo.{" "}
        <strong className="text-amber-100">Start step</strong> en la tarjeta del paso puede fusionar o generar con avatar si está activo.
      </div>

      {generationRunning && (
        <div className="rounded-xl border border-amber-500/40 bg-amber-950/30 px-3 py-2 text-xs text-amber-300">
          Ejecutando paso… el editor puede quedar en solo lectura hasta que termine.
        </div>
      )}

      <Section
        id="ipw-generator"
        badge="1"
        title="Generador y exportación"
        description="Motor de imagen y opciones que aplican a ese motor. El sufijo Midjourney solo aplica si eliges Midjourney; el negative por separado solo si eliges Flux o Stable Diffusion."
      >
        <div className="space-y-3">
          <div>
            <Label>Generador objetivo</Label>
            <Select
              value={targetGenerator}
              disabled={generationRunning}
              onChange={(e) => setTargetGenerator(e.target.value as TargetGenerator)}
            >
              <option value="midjourney">Midjourney</option>
              <option value="flux">Flux</option>
              <option value="dall_e">DALL·E</option>
              <option value="sd">Stable Diffusion / SDXL</option>
              <option value="custom">Personalizado (solo JSON / export manual)</option>
            </Select>
          </div>

          {(showMidjourneySuffixOption || showExportNegativeOption) && (
            <div className="space-y-2">
              {showMidjourneySuffixOption && (
                <div className="flex items-center justify-between gap-3 rounded-lg border border-slate-700 bg-slate-900/40 px-3 py-2.5">
                  <span className="text-xs text-slate-300">
                    Añadir sufijo Midjourney desde <code className="rounded bg-slate-700 px-1 text-slate-200">global_style</code>
                  </span>
                  <IosSwitch
                    checked={appendMjSuffix}
                    onChange={setAppendMjSuffix}
                    disabled={generationRunning}
                    aria-label="Añadir sufijo Midjourney desde global_style"
                  />
                </div>
              )}
              {showExportNegativeOption && (
                <div className="flex items-center justify-between gap-3 rounded-lg border border-slate-700 bg-slate-900/40 px-3 py-2.5">
                  <span className="text-xs text-slate-300">
                    Exportar <code className="rounded bg-slate-700 px-1 text-slate-200">negative_prompt</code> por separado (Flux / SD)
                  </span>
                  <IosSwitch
                    checked={exportNegativeSeparate}
                    onChange={setExportNegativeSeparate}
                    disabled={generationRunning}
                    aria-label="Exportar negative_prompt por separado"
                  />
                </div>
              )}
            </div>
          )}

          {!showMidjourneySuffixOption && !showExportNegativeOption && (
            <p className="text-[11px] leading-snug text-slate-500">
              Para este generador no hay opciones extra aquí: elige Midjourney para el sufijo en <code className="rounded bg-slate-800 px-1">global_style</code>, o Flux / Stable Diffusion para el modo de <code className="rounded bg-slate-800 px-1">negative_prompt</code> separado.
            </p>
          )}

          <div>
            <Label>Notas internas</Label>
            <Input value={settingsNotes} disabled={generationRunning}
              onChange={(e) => setSettingsNotes(e.target.value)}
              placeholder="Ej.: usar solo planos macro en Acto 3…" />
          </div>
          <Btn type="button" className="bg-white text-slate-900 hover:bg-slate-100 disabled:opacity-40" disabled={generationRunning}
            onClick={() => run("Guardar ajustes Image Prompt Writer", saveSettings)}>
            Guardar ajustes
          </Btn>
        </div>
      </Section>

      <Section
        id="ipw-import"
        badge="2"
        title="Importar desde otros pasos"
        description="Rellena o sustituye el bundle a partir del Hook Scene Router o de las ideas de miniatura en Metadata (sin avatar; para miniaturas con personaje usa Metadata paso 3)."
      >
        <div className="flex flex-wrap gap-2">
          <Btn type="button" className="bg-white text-slate-900 hover:bg-slate-100 disabled:opacity-40"
            disabled={generationRunning}
            onClick={() => run("Hook Router → image_prompts", async () => {
              await postJson("/api/pipeline/hook-router/push-to-image-prompts", { work: workApplied });
              await loadBundle(); await refreshPipeline();
            })}>
            Fusionar desde Hook Scene Router
          </Btn>
          <Btn type="button" className="border border-slate-500 bg-slate-700 text-slate-200 hover:bg-slate-600 disabled:opacity-40"
            disabled={generationRunning}
            onClick={() => run("Metadata miniaturas → image_prompts", async () => {
              await postJson("/api/pipeline/metadata/push-thumbnails-to-images", { work: workApplied, include_avatar: false });
              await loadBundle(); await refreshPipeline();
            })}>
            Reemplazar por ideas de miniatura (Metadata)
          </Btn>
        </div>
      </Section>

      <div className="rounded-xl border border-slate-600 bg-slate-800/50 px-4 py-3 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-baseline gap-2">
              <span className="shrink-0 rounded bg-slate-600 px-1.5 py-0.5 text-[10px] font-mono text-slate-300">3</span>
              <span className="text-sm font-semibold tracking-wide text-white">Modo avatar</span>
              <span className="text-[10px] font-medium uppercase tracking-wide text-slate-500">Opcional</span>
            </div>
            <p className="mt-1 text-[11px] leading-snug text-slate-400">
              Un prompt por segmento de narración con el personaje del canal. Activa el interruptor solo si quieres este flujo además o en lugar del import del paso 2.
            </p>
          </div>
          <IosSwitch
            checked={useAvatar}
            onChange={setUseAvatar}
            disabled={generationRunning}
            aria-label="Activar modo avatar"
          />
        </div>

        {useAvatar && (
          <div className="space-y-3 border-t border-slate-700 pt-3">
            <div className="space-y-2">
              <div className="flex flex-wrap items-end gap-2">
                <div className="min-w-[200px] flex-1">
                  <Label>Avatar seleccionado</Label>
                  <Select
                    value={selectedAvatarId}
                    disabled={generationRunning}
                    onChange={(e) => setSelectedAvatarId(e.target.value)}
                  >
                    <option value="">— Descripción manual —</option>
                    {avatarList.map((av) => (
                      <option key={av.id} value={av.id}>
                        {av.bundled ? "★ " : ""}{av.name}
                      </option>
                    ))}
                  </Select>
                </div>
                <Btn
                  type="button"
                  className="shrink-0 border border-violet-500/50 bg-violet-950/40 text-violet-200 hover:bg-violet-900/50"
                  disabled={generationRunning}
                  onClick={openNewAvatarEditor}
                >
                  + Nuevo avatar
                </Btn>
                {selectedAvatarFull && !selectedAvatarFull.bundled && (
                  <>
                    <Btn
                      type="button"
                      className="shrink-0 border border-slate-500 bg-slate-700 text-slate-200 hover:bg-slate-600"
                      disabled={generationRunning}
                      onClick={() => openEditAvatarEditor(selectedAvatarFull)}
                    >
                      Editar
                    </Btn>
                    <Btn
                      type="button"
                      className="shrink-0 border border-rose-500/40 bg-rose-950/30 text-rose-200 hover:bg-rose-950/50"
                      disabled={generationRunning}
                      onClick={() => void deleteSelectedAvatar()}
                    >
                      Borrar
                    </Btn>
                  </>
                )}
              </div>

              {selectedAvatarFull ? (
                <div className="rounded-lg border border-slate-600 bg-slate-800/80 px-3 py-2 text-[11px] text-slate-300 space-y-1.5">
                  <div className="font-semibold text-white">{selectedAvatarFull.name}</div>
                  <div className="leading-snug text-slate-400">{selectedAvatarFull.description}</div>
                  {selectedAvatarFull.expressions.length > 0 && (
                    <div className="flex flex-wrap gap-1 pt-0.5">
                      {selectedAvatarFull.expressions.map((e) => (
                        <span key={e} className="rounded bg-slate-700 px-1.5 py-0.5 text-[10px] font-mono text-slate-300">
                          {e}
                        </span>
                      ))}
                    </div>
                  )}
                  {selectedAvatarFull.style_notes && (
                    <div className="text-slate-500 italic">{selectedAvatarFull.style_notes}</div>
                  )}
                  <div className={`flex items-center gap-1.5 pt-0.5 ${selectedAvatarFull.intro_enabled ? "text-slate-200" : "text-slate-500"}`}>
                    <span className={`inline-block h-2 w-2 rounded-full ${selectedAvatarFull.intro_enabled ? "bg-violet-400" : "bg-slate-600"}`} />
                    {selectedAvatarFull.intro_enabled
                      ? <>Coletilla de <strong className="text-white">presentación</strong> — <strong>{selectedAvatarFull.intro_character_name}</strong></>
                      : "Coletilla de presentación desactivada"}
                  </div>
                  <div className={`flex items-center gap-1.5 ${selectedAvatarFull.outro_enabled ? "text-slate-200" : "text-slate-500"}`}>
                    <span className={`inline-block h-2 w-2 rounded-full ${selectedAvatarFull.outro_enabled ? "bg-emerald-400" : "bg-slate-600"}`} />
                    {selectedAvatarFull.outro_enabled
                      ? <>Coletilla de <strong className="text-white">cierre</strong> — <strong>{selectedAvatarFull.outro_character_name}</strong></>
                      : "Coletilla de cierre desactivada"}
                  </div>
                </div>
              ) : (
                <div>
                  <Label>Descripción manual del avatar</Label>
                  <TextArea
                    value={AVATAR_DEFAULT_DESCRIPTION}
                    disabled
                    className="min-h-[52px] !cursor-not-allowed !border-slate-600 !bg-slate-800/50 !text-slate-500 !text-xs"
                  />
                  <p className="mt-1 text-[10px] text-slate-500">
                    Selecciona un avatar del desplegable o crea uno nuevo para editarlo.
                  </p>
                </div>
              )}
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <Label>Segundos de narración por imagen</Label>
                <Input
                  type="number"
                  min={2}
                  max={30}
                  step={0.5}
                  value={avatarSecsPerImage}
                  disabled={generationRunning}
                  onChange={(e) => setAvatarSecsPerImage(parseFloat(e.target.value) || 6)}
                  className="!mt-1 !rounded-lg !border-slate-600 !bg-slate-700 !text-sm !text-slate-200 focus:!border-slate-400"
                />
                {estimatedLabel && (
                  <div className="mt-0.5 text-[10px] text-slate-500">{estimatedLabel}</div>
                )}
              </div>
              <div>
                <Label>Máximo de imágenes</Label>
                <Input
                  type="number"
                  min={1}
                  max={300}
                  step={1}
                  value={avatarMaxImages}
                  disabled={generationRunning}
                  onChange={(e) => setAvatarMaxImages(parseInt(e.target.value, 10) || 80)}
                  className="!mt-1 !rounded-lg !border-slate-600 !bg-slate-700 !text-sm !text-slate-200 focus:!border-slate-400"
                />
                <div className="mt-0.5 text-[10px] text-slate-500">
                  Limita las llamadas al LLM y a la API de generación de imágenes.
                </div>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Btn
                type="button"
                className="bg-white text-slate-900 hover:bg-slate-100 disabled:opacity-40"
                disabled={generationRunning}
                onClick={() =>
                  run("Guardar ajustes + Generar prompts con Avatar", async () => {
                    await saveSettings();
                    await postJson("/api/pipeline/avatar-prompts/generate", { work: workApplied });
                    await refreshPipeline();
                  })
                }
              >
                Guardar ajustes y generar prompts con Avatar
              </Btn>
              {estimatedPrompts !== null && (
                <span className="text-[11px] text-slate-400">
                  En disco: <strong className="text-slate-200">{estimatedPrompts}</strong> prompts
                </span>
              )}
            </div>
          </div>
        )}

        {!useAvatar && (
          <p className="border-t border-slate-700 pt-2 text-[11px] text-slate-500">
            Con el modo desactivado no se generan prompts por segmento aquí; usa el paso 2 o Start step según tu flujo.
          </p>
        )}
      </div>

      {showAvatarEditor && (
        <div className="rounded-xl border border-slate-600 bg-slate-800/90 p-4 space-y-3 shadow-md">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-300">
            {editingAvatarId ? "Editar avatar" : "Nuevo avatar"}
          </div>
          <div>
            <Label>Nombre</Label>
            <Input
              value={editorName}
              onChange={(e) => setEditorName(e.target.value)}
              placeholder="Ej.: Nerd Boy versión femenina, Robot presentador…"
            />
          </div>
          <div>
            <Label>Descripción para el prompt IA</Label>
            <TextArea
              value={editorDescription}
              onChange={(e) => setEditorDescription(e.target.value)}
              className="min-h-[80px] !border-slate-600 !bg-slate-700 !text-xs !text-slate-200"
              placeholder="Describe el avatar tal como quieres que aparezca en cada imagen…"
            />
            <div className="mt-0.5 text-[10px] text-slate-500">
              Incluye rasgos físicos, ropa, estilo de ilustración y color de contorno.
            </div>
          </div>
          <div>
            <Label>Notas de estilo (opcional)</Label>
            <Input
              value={editorStyleNotes}
              onChange={(e) => setEditorStyleNotes(e.target.value)}
              placeholder="Ej.: fondo siempre blanco, sin sombras…"
            />
          </div>

          <div className="rounded-lg border border-slate-600 bg-slate-800/80 p-2.5 space-y-2">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-xs font-semibold text-slate-200">
                  Coletilla de <span className="text-white">presentación</span> (tras el hook)
                </div>
                <p className="mt-0.5 text-[10px] leading-snug text-slate-400">
                  Una imagen donde el personaje se presenta y adelanta el tema.
                </p>
              </div>
              <IosSwitch
                checked={editorIntroEnabled}
                onChange={setEditorIntroEnabled}
                aria-label="Activar coletilla de presentación"
              />
            </div>
            {editorIntroEnabled && (
              <div>
                <Label>Nombre del personaje</Label>
                <Input
                  value={editorIntroCharacterName}
                  onChange={(e) => setEditorIntroCharacterName(e.target.value)}
                  placeholder={`Por defecto: "${editorName || "nombre del avatar"}"`}
                />
                <div className="mt-0.5 text-[10px] text-slate-500">
                  Ej.: "Nerd", "Alex". El LLM usará este nombre en el texto generado.
                </div>
              </div>
            )}
          </div>

          <div className="rounded-lg border border-slate-600 bg-slate-800/80 p-2.5 space-y-2">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-xs font-semibold text-slate-200">
                  Coletilla de <span className="text-white">cierre</span> (suscripción + like)
                </div>
                <p className="mt-0.5 text-[10px] leading-snug text-slate-400">
                  Una imagen al final pidiendo suscripción y like de forma natural.
                </p>
              </div>
              <IosSwitch
                checked={editorOutroEnabled}
                onChange={setEditorOutroEnabled}
                aria-label="Activar coletilla de cierre"
              />
            </div>
            {editorOutroEnabled && (
              <div>
                <Label>Nombre del personaje</Label>
                <Input
                  value={editorOutroCharacterName}
                  onChange={(e) => setEditorOutroCharacterName(e.target.value)}
                  placeholder={`Por defecto: "${editorName || "nombre del avatar"}"`}
                />
                <div className="mt-0.5 text-[10px] text-slate-500">
                  Ej.: "Nerd", "Alex". El LLM generará la frase de cierre con este nombre.
                </div>
              </div>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            <Btn
              type="button"
              className="bg-white text-slate-900 hover:bg-slate-100"
              onClick={() => run("Guardar avatar", saveAvatarEditor)}
            >
              Guardar avatar
            </Btn>
            <Btn
              type="button"
              className="border border-slate-500 bg-slate-700 text-slate-200 hover:bg-slate-600"
              onClick={() => setShowAvatarEditor(false)}
            >
              Cancelar
            </Btn>
          </div>
        </div>
      )}

      <div className="rounded-xl border border-slate-600 bg-slate-800/60 px-4 py-3">
        <div className="text-xs font-semibold text-slate-300">Referencia · campos del JSON</div>
        <p className="mt-1 text-[11px] text-slate-500">Lo que espera el paso de imágenes y exportaciones externas.</p>
        <ul className="mt-2 list-disc space-y-1 pl-4 text-[11px] leading-relaxed text-slate-400">
          <li><code className="rounded bg-slate-700 px-1 text-slate-200">version</code>, <code className="rounded bg-slate-700 px-1 text-slate-200">source</code>, <code className="rounded bg-slate-700 px-1 text-slate-200">global_style</code></li>
          <li>
            <code className="rounded bg-slate-700 px-1 text-slate-200">prompts[]</code>: <code className="rounded bg-slate-700 px-1 text-slate-200">id</code>, <code className="rounded bg-slate-700 px-1 text-slate-200">act</code>, <code className="rounded bg-slate-700 px-1 text-slate-200">expression</code>,{" "}
            <code className="rounded bg-slate-700 px-1 text-slate-200">situation</code>, <code className="rounded bg-slate-700 px-1 text-slate-200">ai_prompt</code>, <code className="rounded bg-slate-700 px-1 text-slate-200">negative_prompt</code>, <code className="rounded bg-slate-700 px-1 text-slate-200">segment_text</code>
          </li>
          <li>Formato legacy: <code className="rounded bg-slate-700 px-1 text-slate-200">role</code> + <code className="rounded bg-slate-700 px-1 text-slate-200">text</code> (válido)</li>
        </ul>
      </div>

      <div className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="text-sm font-semibold tracking-wider capitalize text-white">Salida · image_prompts.json</div>
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
            <Btn type="button" className="bg-white text-slate-900 hover:bg-slate-100 disabled:opacity-40"
              disabled={generationRunning || !jsonText.trim()}
              onClick={() => run("Guardar image_prompts.json", saveBundle)}>
              Guardar y marcar listo
            </Btn>
          </div>
        </div>

        {parsedPrompts.length > 0 && (
          <div className="text-[11px] text-slate-500">
            <span className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-slate-400">{parsedPrompts.length}</span>
            {" "}prompts en el array actual
          </div>
        )}

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
                  />
                );
              })}
            </div>
          ) : (
            <div className="min-h-[120px] rounded-xl border border-dashed border-slate-600 bg-slate-800 px-4 py-6 text-center text-xs text-slate-500 shadow-inner"
            >
              {hasBundle
                ? "El bundle no contiene prompts en el array esperado."
                : "Aún no hay bundle. Completa los pasos 1–3 o ejecuta «Start step» en la tarjeta del paso."}
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
    </div>
  );
}
