import { useEffect, useState } from "react";
import { Btn, Select } from "../../../components/ui";
import { ProductionResetButton } from "../pipeline/ProductionResetButton";
import { ChunkCard } from "./ChunkCard";
import { useSceneEditor } from "./useSceneEditor";

export function SceneEditor({
  workApplied,
  reloadKey = 0,
}: {
  workApplied: string;
  /** Incrementar tras un reset de voiceovers para recargar chunks desde disco. */
  reloadKey?: number;
}) {
  const {
    chunks,
    parsing,
    generatingId,
    error,
    ttsConfig,
    voices,
    selectedVoiceId,
    setSelectedVoiceId,
    parseScript,
    loadSavedChunks,
    updateChunkText,
    updateAiPrompt,
    splitChunk,
    deleteChunk,
    mergeWithPrevious,
    mergeWithNext,
    generateAudio,
    generatePendingAudio,
    regenerateAllAudio,
    pendingAudioCount,
    batchGenerating,
    batchProgress,
    visualConfig,
    planningVisualId,
    batchPlanning,
    visualBatchProgress,
    pendingVisualCount,
    loadVisualConfig,
    exportingPrompts,
    exportInfo,
    planVisual,
    expandVisualRhythm,
    planPendingVisual,
    regenerateAllVisualPrompts,
    regenerateVisualRange,
    exportImagePrompts,
    exportingNarration,
    exportUnifiedNarration,
  } = useSceneEditor(workApplied);

  const [rangeFrom, setRangeFrom] = useState("4");
  const [rangeTo, setRangeTo] = useState("8");
  const [resetInfo, setResetInfo] = useState<string | null>(null);

  useEffect(() => {
    void loadSavedChunks();
  }, [loadSavedChunks, reloadKey]);

  const totalMs = chunks.reduce((acc, c) => acc + (c.duration_ms ?? 0), 0);
  const doneCount = chunks.filter((c) => c.status === "done").length;
  const visualDoneCount = chunks.filter((c) => (c.ai_prompt ?? "").trim()).length;
  const narrableCount = chunks.filter((c) => c.narration_text.trim()).length;
  const isElevenLabs = ttsConfig?.provider === "elevenlabs";
  const batchBusy = batchGenerating || batchPlanning;

  return (
    <div className="space-y-4 rounded-2xl border border-slate-200 bg-slate-50/80 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">Scene Editor</h3>
          <p className="mt-1 max-w-xl text-[12px] text-slate-600">
            Bloques narrables con audio (TTS) y prompts visuales alineados. Edita, fusiona o divide antes de
            generar.
          </p>
        </div>
        <Btn
          type="button"
          className="bg-violet-600 text-white hover:bg-violet-500 disabled:opacity-50"
          disabled={parsing || batchBusy}
          onClick={() => void parseScript()}
        >
          {parsing ? "Parseando…" : "Parsear guion"}
        </Btn>
      </div>

      {ttsConfig ? (
        <div
          className={`rounded-xl border px-3 py-2 text-[12px] ${
            isElevenLabs
              ? "border-emerald-200 bg-emerald-50 text-emerald-900"
              : "border-amber-200 bg-amber-50 text-amber-900"
          }`}
        >
          {isElevenLabs ? (
            <>
              <strong>TTS: ElevenLabs</strong>
              {ttsConfig.model_id ? ` · ${ttsConfig.model_id}` : ""}
              {voices.length > 0 ? (
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <label className="text-[11px] font-medium">Voz</label>
                  <Select
                    className="max-w-xs text-[12px]"
                    value={selectedVoiceId}
                    onChange={(e) => setSelectedVoiceId(e.target.value)}
                  >
                    {voices.map((v) => (
                      <option key={v.voice_id} value={v.voice_id}>
                        {v.name}
                        {v.category ? ` (${v.category})` : ""}
                      </option>
                    ))}
                  </Select>
                </div>
              ) : ttsConfig.voice_id ? (
                <span className="ml-1 font-mono text-[11px]">· {ttsConfig.voice_id}</span>
              ) : null}
            </>
          ) : (
            <>
              <strong>TTS: mock</strong> — Añade <code className="rounded bg-white/70 px-1">ELEVENLABS_API_KEY</code>{" "}
              y <code className="rounded bg-white/70 px-1">ELEVENLABS_VOICE_ID</code> en{" "}
              <code className="rounded bg-white/70 px-1">.env</code> y reinicia el backend.
            </>
          )}
        </div>
      ) : null}

      <p className="rounded-xl border border-violet-200 bg-violet-50/90 px-3 py-2 text-[12px] text-violet-950">
        El <strong>estilo visual</strong> (estilo base, protagonista, expresiones, avoid) está en{" "}
        <strong>Create → Image Prompt Writer → sección «Estilo visual y avatar»</strong>. Guarda ahí antes de planificar
        bloques o generar miniaturas en Metadata.
      </p>

      {visualConfig && !visualConfig.has_style_settings ? (
        <p className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-[12px] text-amber-900">
          Falta <strong>estilo base</strong> guardado — configúralo en Image Prompt Writer (sección avatar).
        </p>
      ) : null}

      {error ? (
        <p className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-[12px] text-rose-800">
          {error}
        </p>
      ) : null}

      {exportInfo ? (
        <p className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-[12px] text-emerald-800">
          Exportado: {exportInfo}
        </p>
      ) : null}

      {resetInfo ? (
        <p className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-[12px] text-rose-800">
          {resetInfo}
        </p>
      ) : null}

      {chunks.length > 0 ? (
        <>
          <div className="flex flex-wrap items-center gap-3 rounded-xl border border-violet-200 bg-violet-50/80 px-3 py-3">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-violet-800">Audio</span>
            <Btn
              type="button"
              className="bg-violet-700 text-white hover:bg-violet-600 disabled:opacity-50"
              disabled={batchBusy || parsing || pendingAudioCount === 0}
              onClick={() => void generatePendingAudio()}
            >
              {batchGenerating
                ? "Generando audio…"
                : `Generar pendientes (${pendingAudioCount})`}
            </Btn>
            <button
              type="button"
              className="rounded-lg border border-violet-300 bg-white px-2.5 py-1.5 text-[11px] font-medium text-violet-900 hover:bg-violet-50 disabled:cursor-not-allowed disabled:opacity-40"
              disabled={batchBusy || parsing || narrableCount === 0}
              onClick={() => regenerateAllAudio()}
            >
              Regenerar todo
            </button>
            {batchGenerating && batchProgress ? (
              <div className="flex min-w-[160px] flex-1 flex-col gap-1">
                <div className="flex justify-between text-[11px] text-violet-900">
                  <span>Audio</span>
                  <span>
                    {batchProgress.done}/{batchProgress.total}
                  </span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-violet-200">
                  <div
                    className="h-full rounded-full bg-violet-600 transition-all duration-500"
                    style={{
                      width: `${batchProgress.total > 0 ? (100 * batchProgress.done) / batchProgress.total : 0}%`,
                    }}
                  />
                </div>
              </div>
            ) : pendingAudioCount > 0 ? (
              <span className="text-[11px] text-slate-600">{pendingAudioCount} bloques sin audio</span>
            ) : narrableCount > 0 ? (
              <span className="text-[11px] text-emerald-700">Audio completo</span>
            ) : null}
            <Btn
              type="button"
              className="border border-violet-400 bg-white text-violet-900 hover:bg-violet-50 disabled:opacity-50"
              disabled={batchBusy || parsing || doneCount === 0}
              onClick={() => void exportUnifiedNarration()}
            >
              {exportingNarration ? "Uniendo…" : "Unificar → narracion.wav"}
            </Btn>
          </div>

          <div className="flex flex-wrap items-center gap-3 rounded-xl border border-sky-200 bg-sky-50/80 px-3 py-3">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-sky-800">Visual</span>
            <Btn
              type="button"
              className="bg-sky-700 text-white hover:bg-sky-600 disabled:opacity-50"
              disabled={batchBusy || parsing || pendingVisualCount === 0}
              onClick={() => void planPendingVisual()}
            >
              {batchPlanning
                ? "Planificando visuales…"
                : `Planificar pendientes (${pendingVisualCount})`}
            </Btn>
            <button
              type="button"
              className="rounded-lg border border-sky-300 bg-white px-2.5 py-1.5 text-[11px] font-medium text-sky-900 hover:bg-sky-50 disabled:cursor-not-allowed disabled:opacity-40"
              disabled={batchBusy || parsing || chunks.length === 0}
              onClick={() => regenerateAllVisualPrompts()}
            >
              Regenerar todo
            </button>
            <div className="flex flex-wrap items-center gap-1.5 rounded-lg border border-sky-200 bg-white px-2 py-1">
              <span className="text-[10px] font-medium text-sky-800">Rango</span>
              <input
                type="number"
                min={1}
                max={chunks.length || 1}
                className="w-12 rounded border border-sky-200 px-1.5 py-0.5 text-[11px]"
                value={rangeFrom}
                onChange={(e) => setRangeFrom(e.target.value)}
                aria-label="Bloque inicial"
              />
              <span className="text-[10px] text-sky-700">–</span>
              <input
                type="number"
                min={1}
                max={chunks.length || 1}
                className="w-12 rounded border border-sky-200 px-1.5 py-0.5 text-[11px]"
                value={rangeTo}
                onChange={(e) => setRangeTo(e.target.value)}
                aria-label="Bloque final"
              />
              <button
                type="button"
                className="rounded border border-sky-300 px-2 py-0.5 text-[10px] font-medium text-sky-900 hover:bg-sky-50 disabled:opacity-40"
                disabled={batchBusy || parsing || chunks.length === 0}
                onClick={() => {
                  const from = parseInt(rangeFrom, 10);
                  const to = parseInt(rangeTo, 10);
                  regenerateVisualRange(from, to);
                }}
              >
                Regenerar rango
              </button>
            </div>
            <Btn
              type="button"
              className="border border-sky-300 bg-white text-sky-900 hover:bg-sky-100 disabled:opacity-50"
              disabled={batchBusy || exportingPrompts || visualDoneCount === 0}
              onClick={() => void exportImagePrompts()}
            >
              {exportingPrompts ? "Exportando…" : "Exportar → image_prompts.json"}
            </Btn>
            <ProductionResetButton
              workApplied={workApplied}
              scope="scene_editor_visual"
              label="Limpiar prompts visuales"
              disabled={batchBusy || parsing || visualDoneCount === 0}
              className="rounded-lg border border-rose-300 bg-white px-2.5 py-1.5 text-[11px] font-medium text-rose-800 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-40"
              onDone={async (msg) => {
                setResetInfo(msg);
                await loadSavedChunks();
              }}
            />
            {batchPlanning && visualBatchProgress ? (
              <div className="flex min-w-[160px] flex-1 flex-col gap-1">
                <div className="flex justify-between text-[11px] text-sky-900">
                  <span>Visual</span>
                  <span>
                    {visualBatchProgress.done}/{visualBatchProgress.total}
                  </span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-sky-200">
                  <div
                    className="h-full rounded-full bg-sky-600 transition-all duration-500"
                    style={{
                      width: `${visualBatchProgress.total > 0 ? (100 * visualBatchProgress.done) / visualBatchProgress.total : 0}%`,
                    }}
                  />
                </div>
              </div>
            ) : pendingVisualCount > 0 ? (
              <span className="text-[11px] text-slate-600">
                {pendingVisualCount} bloques sin prompt · usa «Regenerar rango» para forzar 4–8
              </span>
            ) : visualDoneCount > 0 ? (
              <span className="text-[11px] text-emerald-700">Prompts visuales completos</span>
            ) : null}
          </div>

          <div className="flex flex-wrap gap-3 text-[11px] text-slate-600">
            <span>{chunks.length} bloques</span>
            <span>{doneCount} con audio</span>
            <span>{visualDoneCount} con prompt visual</span>
            {totalMs > 0 ? (
              <span>
                ~{Math.round(totalMs / 1000 / 60)} min audio
                {isElevenLabs ? "" : " (mock)"}
              </span>
            ) : null}
          </div>
        </>
      ) : (
        <p className="text-[12px] text-slate-500">
          Pulsa <strong>Parsear guion</strong> para cargar el SCRIPT desde la sesión y crear los bloques.
        </p>
      )}

      <div className="space-y-3">
        {chunks.map((chunk, i) => (
          <ChunkCard
            key={chunk.id}
            chunk={chunk}
            index={i}
            total={chunks.length}
            generating={generatingId === chunk.id || batchGenerating}
            planningVisual={planningVisualId === chunk.id || batchPlanning}
            batchBusy={batchBusy}
            onTextChange={(text) => updateChunkText(chunk.id, text)}
            onAiPromptChange={(prompt) => updateAiPrompt(chunk.id, prompt)}
            onSplit={(cursor) => splitChunk(chunk.id, cursor)}
            onGenerate={() => void generateAudio(chunk.id)}
            onPlanVisual={() => void planVisual(chunk.id)}
            onExpandRhythm={
              chunk.visual_rhythm_ok === false && (chunk.duration_ms ?? 0) > 0
                ? () => void expandVisualRhythm(chunk.id)
                : undefined
            }
            onMergePrevious={i > 0 ? () => mergeWithPrevious(chunk.id) : undefined}
            onMergeNext={i < chunks.length - 1 ? () => mergeWithNext(chunk.id) : undefined}
            onDelete={() => deleteChunk(chunk.id)}
          />
        ))}
      </div>
    </div>
  );
}
