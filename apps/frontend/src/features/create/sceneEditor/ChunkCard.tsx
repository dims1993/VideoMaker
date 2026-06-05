import { useRef } from "react";
import { ACT_COLORS, ACT_LABELS, sectionToAct } from "./chunkSection";
import type { Chunk } from "./types";

function formatMs(ms: number | null): string {
  if (ms == null || ms <= 0) return "—";
  const s = Math.round(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function ChunkCard({
  chunk,
  index,
  total,
  generating,
  planningVisual,
  batchBusy,
  onTextChange,
  onAiPromptChange,
  onSplit,
  onGenerate,
  onPlanVisual,
  onExpandRhythm,
  onMergePrevious,
  onMergeNext,
  onDelete,
}: {
  chunk: Chunk;
  index: number;
  total: number;
  generating?: boolean;
  planningVisual?: boolean;
  batchBusy?: boolean;
  onTextChange: (text: string) => void;
  onAiPromptChange: (prompt: string) => void;
  onSplit: (cursorIndex: number) => void;
  onGenerate: () => void;
  onPlanVisual: () => void;
  onExpandRhythm?: () => void;
  onMergePrevious?: () => void;
  onMergeNext?: () => void;
  onDelete?: () => void;
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSplit = () => {
    const el = textareaRef.current;
    if (!el) return;
    onSplit(el.selectionStart ?? el.value.length);
  };

  const handleDelete = () => {
    if (!onDelete) return;
    const hadAudio = Boolean(chunk.audio_url);
    const hadVisual = Boolean((chunk.ai_prompt ?? "").trim());
    let msg = "¿Eliminar este bloque?";
    if (hadAudio && hadVisual) msg = "¿Eliminar este bloque? Se perderá su audio y prompt visual.";
    else if (hadAudio) msg = "¿Eliminar este bloque? Se perderá su audio generado.";
    else if (hadVisual) msg = "¿Eliminar este bloque? Se perderá su prompt visual.";
    if (window.confirm(msg)) onDelete();
  };

  const hasVisualInput = Boolean(chunk.narration_text.trim());
  const hasScenePrompt = Boolean((chunk.scene_prompt_en ?? "").trim());
  const visualDone =
    chunk.visual_status === "done" &&
    Boolean((chunk.ai_prompt ?? "").trim()) &&
    hasScenePrompt;
  const visualStale =
    chunk.visual_status === "planning" ||
    chunk.visual_status === "error" ||
    (Boolean((chunk.ai_prompt ?? "").trim()) && !hasScenePrompt);
  const promptLen = (chunk.ai_prompt ?? "").length;
  const promptWeak = visualDone && promptLen > 0 && promptLen < 120;
  const shotCount = chunk.visual_shots?.length ?? 0;
  const rhythmWarn = Boolean(chunk.visual_rhythm_warning?.trim());

  const statusTone =
    chunk.status === "done"
      ? "border-emerald-200 bg-emerald-50/50"
      : chunk.status === "error"
        ? "border-rose-200 bg-rose-50/50"
        : chunk.status === "generating"
          ? "border-amber-200 bg-amber-50/50"
          : visualDone
            ? "border-sky-200 bg-sky-50/40"
            : "border-slate-200 bg-white";

  const btn =
    "rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40";

  const act = sectionToAct(chunk.section);
  const actLabel = ACT_LABELS[act] ?? act;
  const actColor = ACT_COLORS[act] ?? ACT_COLORS.body;

  return (
    <article className={`rounded-2xl border p-4 shadow-sm ${statusTone}`}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="text-[12px] font-semibold text-slate-800">
          Bloque {index + 1}
          {chunk.section ? (
            <span
              className={`ml-2 rounded-full px-2 py-0.5 text-[10px] font-medium ${actColor}`}
              title={chunk.section}
            >
              {actLabel}
            </span>
          ) : null}
          <span className="ml-2 font-normal text-slate-500">{formatMs(chunk.duration_ms)}</span>
          {visualDone ? (
            <span className="ml-2 rounded-full bg-sky-100 px-2 py-0.5 text-[10px] font-medium text-sky-800">
              visual ✓
            </span>
          ) : visualStale ? (
            <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-900">
              visual ⚠
            </span>
          ) : null}
          {shotCount > 1 ? (
            <span className="ml-2 rounded-full bg-violet-100 px-2 py-0.5 text-[10px] font-medium text-violet-900">
              {shotCount} planos
            </span>
          ) : null}
          {rhythmWarn ? (
            <span className="ml-2 rounded-full bg-orange-100 px-2 py-0.5 text-[10px] font-medium text-orange-900">
              ritmo visual
            </span>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2">
          {onMergePrevious ? (
            <button type="button" className={btn} title="Une el bloque anterior con este" onClick={onMergePrevious}>
              ↑ Fusionar arriba
            </button>
          ) : null}
          {onMergeNext ? (
            <button type="button" className={btn} title="Une el bloque siguiente con este" onClick={onMergeNext}>
              ↓ Fusionar abajo
            </button>
          ) : null}
          <button type="button" className={btn} onClick={handleSplit} title="Divide el bloque en el cursor del textarea">
            Dividir aquí
          </button>
          {onDelete && total > 1 ? (
            <button
              type="button"
              className="rounded-lg border border-rose-200 bg-rose-50 px-2.5 py-1 text-[11px] font-medium text-rose-800 hover:bg-rose-100"
              onClick={handleDelete}
            >
              Eliminar
            </button>
          ) : null}
          {onExpandRhythm ? (
            <button
              type="button"
              className="rounded-lg border border-orange-300 bg-orange-50 px-2.5 py-1 text-[11px] font-semibold text-orange-900 hover:bg-orange-100 disabled:opacity-50"
              disabled={planningVisual || batchBusy}
              title={chunk.visual_rhythm_warning ?? undefined}
              onClick={() => void onExpandRhythm()}
            >
              Dividir en sub-planos
            </button>
          ) : null}
          <button
            type="button"
            className="rounded-lg bg-sky-600 px-2.5 py-1 text-[11px] font-semibold text-white hover:bg-sky-500 disabled:opacity-50"
            disabled={planningVisual || batchBusy || !hasVisualInput}
            onClick={() => void onPlanVisual()}
          >
            {planningVisual ? "Planificando…" : visualDone ? "Replanificar visual" : "Planificar visual"}
          </button>
          <button
            type="button"
            className="rounded-lg bg-violet-600 px-2.5 py-1 text-[11px] font-semibold text-white hover:bg-violet-500 disabled:opacity-50"
            disabled={generating || batchBusy || !chunk.narration_text.trim()}
            onClick={() => void onGenerate()}
          >
            {generating ? "Generando…" : chunk.audio_url ? "Regenerar audio" : "Generar audio"}
          </button>
        </div>
      </div>

      {rhythmWarn ? (
        <p className="mb-2 rounded-lg border border-orange-200 bg-orange-50 px-3 py-2 text-[11px] text-orange-900">
          {chunk.visual_rhythm_warning}
        </p>
      ) : null}

      <label className="block text-[11px] font-medium text-slate-600">Narración (TTS)</label>
      <textarea
        ref={textareaRef}
        className="mt-1 min-h-[96px] w-full resize-y rounded-xl border border-slate-200 bg-white px-3 py-2 text-[13px] leading-relaxed text-slate-900 focus:border-violet-400 focus:outline-none focus:ring-2 focus:ring-violet-100"
        value={chunk.narration_text}
        onChange={(e) => onTextChange(e.target.value)}
        placeholder="Texto que irá a locución…"
      />

      <div className="mt-3 rounded-xl border border-dashed border-sky-200 bg-sky-50/60 px-3 py-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <label className="text-[11px] font-semibold text-sky-900">Prompt de imagen (IA)</label>
          <div className="flex flex-wrap items-center gap-2">
            {chunk.protagonist_expression_key ? (
              <span
                className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-medium text-emerald-900"
                title={chunk.protagonist_expression_en ?? chunk.protagonist_expression_key}
              >
                expresión: {chunk.protagonist_expression_key}
              </span>
            ) : null}
            {chunk.situation_es ? (
              <span className="text-[10px] text-sky-700">{chunk.situation_es}</span>
            ) : null}
          </div>
        </div>
        <textarea
          className="mt-1 min-h-[72px] w-full resize-y rounded-lg border border-sky-100 bg-white/80 px-2.5 py-1.5 font-mono text-[11px] leading-relaxed text-sky-950 focus:border-sky-300 focus:outline-none"
          value={chunk.ai_prompt ?? ""}
          onChange={(e) => onAiPromptChange(e.target.value)}
          placeholder="Prompt listo para Nano Banana 2 — estilo base + escena + Avoid + ratio"
        />
        {promptWeak ? (
          <p className="mt-1 text-[10px] text-amber-800">
            Prompt corto ({promptLen} chars) — revisa o replanifica.
          </p>
        ) : null}
      </div>

      {chunk.audio_url ? (
        <div className="mt-3">
          <audio key={chunk.audio_url} controls className="w-full" src={chunk.audio_url} preload="auto" />
        </div>
      ) : null}
    </article>
  );
}
