import { useCallback, useEffect, useState } from "react";
import { postJson, putJson } from "../../../services/api";
import { mergeTwoChunks } from "./chunkMerge";
import { countPendingAudio } from "./chunkAudio";
import { countPendingVisual, chunkIsPlannable } from "./chunkVisual";
import type {
  Chunk,
  ElevenLabsVoice,
  ExportImagePromptsResponse,
  ExportNarrationResponse,
  GenerateAllChunksResponse,
  ParseScriptResponse,
  PlanAllVisualResponse,
  TtsConfig,
  VisualPlannerConfig,
} from "./types";

export function useSceneEditor(work: string) {
  const [chunks, setChunks] = useState<Chunk[]>([]);
  const [parsing, setParsing] = useState(false);
  const [generatingId, setGeneratingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ttsConfig, setTtsConfig] = useState<TtsConfig | null>(null);
  const [voices, setVoices] = useState<ElevenLabsVoice[]>([]);
  const [selectedVoiceId, setSelectedVoiceId] = useState<string>("");
  const [batchGenerating, setBatchGenerating] = useState(false);
  const [batchProgress, setBatchProgress] = useState<{ done: number; total: number } | null>(
    null,
  );
  const [planningVisualId, setPlanningVisualId] = useState<string | null>(null);
  const [batchPlanning, setBatchPlanning] = useState(false);
  const [visualBatchProgress, setVisualBatchProgress] = useState<{ done: number; total: number } | null>(
    null,
  );
  const [visualConfig, setVisualConfig] = useState<VisualPlannerConfig | null>(null);
  const [exportingPrompts, setExportingPrompts] = useState(false);
  const [exportingNarration, setExportingNarration] = useState(false);
  const [exportInfo, setExportInfo] = useState<string | null>(null);

  const persistChunks = useCallback(
    async (next: Chunk[]) => {
      await putJson("/api/scene-editor/chunks", { work, chunks: next });
    },
    [work],
  );

  const loadTtsConfig = useCallback(async () => {
    try {
      const r = await fetch("/api/audio/tts-config");
      if (!r.ok) return;
      const cfg = (await r.json()) as TtsConfig;
      setTtsConfig(cfg);
      if (cfg.voice_id) setSelectedVoiceId(cfg.voice_id);
      if (cfg.provider === "elevenlabs") {
        const vr = await fetch("/api/audio/elevenlabs-voices");
        if (vr.ok) {
          const vj = (await vr.json()) as { voices?: ElevenLabsVoice[] };
          setVoices(vj.voices ?? []);
        }
      }
    } catch {
      /* ignore */
    }
  }, []);

  const loadSavedChunks = useCallback(async () => {
    setError(null);
    try {
      const r = await fetch(`/api/scene-editor/chunks?work=${encodeURIComponent(work)}`);
      if (!r.ok) return;
      const data = (await r.json()) as ParseScriptResponse;
      if (Array.isArray(data.chunks) && data.chunks.length > 0) {
        setChunks(data.chunks);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al cargar chunks");
    }
  }, [work]);

  useEffect(() => {
    void loadTtsConfig();
  }, [loadTtsConfig]);

  const loadVisualConfig = useCallback(async () => {
    try {
      const r = await fetch(`/api/visual/planner-config?work=${encodeURIComponent(work)}`);
      if (!r.ok) return;
      setVisualConfig((await r.json()) as VisualPlannerConfig);
    } catch {
      /* ignore */
    }
  }, [work]);

  useEffect(() => {
    void loadVisualConfig();
  }, [loadVisualConfig]);

  const parseScript = useCallback(
    async (text?: string) => {
      setParsing(true);
      setError(null);
      try {
        const data = await postJson<ParseScriptResponse>("/api/script/parse", {
          work,
          text: text?.trim() || undefined,
        });
        setChunks(data.chunks ?? []);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Error al parsear el guion");
      } finally {
        setParsing(false);
      }
    },
    [work],
  );

  const updateChunkText = useCallback(
    (id: string, text: string) => {
      setChunks((prev) => {
        const next = prev.map((c) => (c.id === id ? { ...c, narration_text: text } : c));
        void persistChunks(next);
        return next;
      });
    },
    [persistChunks],
  );

  const updateAiPrompt = useCallback(
    (id: string, prompt: string) => {
      setChunks((prev) => {
        const next = prev.map((c) =>
          c.id === id
            ? {
                ...c,
                ai_prompt: prompt.trim() || null,
                visual_status: prompt.trim() ? ("done" as const) : ("idle" as const),
              }
            : c,
        );
        void persistChunks(next);
        return next;
      });
    },
    [persistChunks],
  );

  const splitChunk = useCallback(
    (id: string, cursorIndex: number) => {
      setChunks((prev) => {
        const idx = prev.findIndex((c) => c.id === id);
        if (idx < 0) return prev;
        const chunk = prev[idx];
        const text = chunk.narration_text;
        const pos = Math.max(0, Math.min(cursorIndex, text.length));
        const left = text.slice(0, pos).trimEnd();
        const right = text.slice(pos).trimStart();
        if (!left || !right) return prev;

        const newChunk: Chunk = {
          id: crypto.randomUUID(),
          narration_text: right,
          section: chunk.section ?? null,
          director_note: null,
          audio_url: null,
          duration_ms: null,
          status: "idle",
          visual_status: "idle",
          situation_es: null,
          scene_prompt_en: null,
          ai_prompt: null,
          negative_prompt: null,
        };
        const next = [...prev];
        next[idx] = {
          ...chunk,
          narration_text: left,
          audio_url: null,
          duration_ms: null,
          status: "idle",
          visual_status: "idle",
          situation_es: null,
          scene_prompt_en: null,
          ai_prompt: null,
          negative_prompt: null,
        };
        next.splice(idx + 1, 0, newChunk);
        void persistChunks(next);
        return next;
      });
    },
    [persistChunks],
  );

  const deleteChunk = useCallback(
    (id: string) => {
      setChunks((prev) => {
        if (prev.length <= 1) return prev;
        const next = prev.filter((c) => c.id !== id);
        if (next.length === prev.length) return prev;
        void persistChunks(next);
        return next;
      });
    },
    [persistChunks],
  );

  const mergeWithPrevious = useCallback(
    (id: string) => {
      setChunks((prev) => {
        const idx = prev.findIndex((c) => c.id === id);
        if (idx <= 0) return prev;
        const prevChunk = prev[idx - 1];
        const cur = prev[idx];
        const merged = mergeTwoChunks(prevChunk, cur);
        const next = [...prev];
        next[idx - 1] = merged;
        next.splice(idx, 1);
        void persistChunks(next);
        return next;
      });
    },
    [persistChunks],
  );

  const mergeWithNext = useCallback(
    (id: string) => {
      setChunks((prev) => {
        const idx = prev.findIndex((c) => c.id === id);
        if (idx < 0 || idx >= prev.length - 1) return prev;
        const cur = prev[idx];
        const nxt = prev[idx + 1];
        const merged = mergeTwoChunks(cur, nxt);
        const next = [...prev];
        next[idx] = merged;
        next.splice(idx + 1, 1);
        void persistChunks(next);
        return next;
      });
    },
    [persistChunks],
  );

  const generateAudio = useCallback(
    async (id: string) => {
      const chunk = chunks.find((c) => c.id === id);
      if (!chunk?.narration_text.trim()) {
        setError("Escribe texto narrable antes de generar audio.");
        return;
      }
      setGeneratingId(id);
      setError(null);
      setChunks((prev) =>
        prev.map((c) => (c.id === id ? { ...c, status: "generating" as const } : c)),
      );
      try {
        const data = await postJson<{ chunk: Chunk }>("/api/audio/generate-chunk", {
          work,
          chunk_id: id,
          narration_text: chunk.narration_text,
          voice_id: selectedVoiceId.trim() || undefined,
        });
        setChunks((prev) => prev.map((c) => (c.id === id ? data.chunk : c)));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Error al generar audio");
        setChunks((prev) =>
          prev.map((c) => (c.id === id ? { ...c, status: "error" as const } : c)),
        );
      } finally {
        setGeneratingId(null);
      }
    },
    [chunks, work, selectedVoiceId],
  );

  const runBatchAudio = useCallback(
    async (regenerateAll: boolean) => {
      const narrable = chunks.filter((c) => c.narration_text.trim());
      if (narrable.length === 0) {
        setError("No hay bloques con texto narrable.");
        return;
      }
      const pending = countPendingAudio(chunks);
      if (!regenerateAll && pending === 0) {
        setError("No hay bloques pendientes de audio.");
        return;
      }

      const progressTotal = regenerateAll ? narrable.length : pending;

      setBatchGenerating(true);
      setError(null);
      setBatchProgress({ done: 0, total: progressTotal });

      const poll = window.setInterval(() => {
        void (async () => {
          try {
            const r = await fetch(`/api/scene-editor/chunks?work=${encodeURIComponent(work)}`);
            if (!r.ok) return;
            const data = (await r.json()) as ParseScriptResponse;
            if (!Array.isArray(data.chunks)) return;
            setChunks(data.chunks);
            if (regenerateAll) {
              const withText = data.chunks.filter((c) => c.narration_text.trim());
              setBatchProgress({
                done: withText.filter((c) => c.status === "done").length,
                total: withText.length,
              });
            } else {
              const left = countPendingAudio(data.chunks);
              setBatchProgress({
                done: Math.max(0, progressTotal - left),
                total: progressTotal,
              });
            }
          } catch {
            /* ignore poll errors */
          }
        })();
      }, 1500);

      try {
        const res = await postJson<GenerateAllChunksResponse>("/api/audio/generate-all-chunks", {
          work,
          voice_id: selectedVoiceId.trim() || undefined,
          skip_with_audio: !regenerateAll,
          regenerate_all: regenerateAll,
        });
        setChunks(res.chunks);
        if (res.failed > 0) {
          const first = res.errors[0];
          setError(
            `Completado con ${res.failed} error(es). ${res.generated} generados, ${res.skipped} omitidos.` +
              (first ? ` Ej.: ${first.detail}` : ""),
          );
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Error en generación masiva");
      } finally {
        window.clearInterval(poll);
        setBatchGenerating(false);
        setBatchProgress(null);
      }
    },
    [chunks, work, selectedVoiceId],
  );

  const generatePendingAudio = useCallback(() => runBatchAudio(false), [runBatchAudio]);

  const regenerateAllAudio = useCallback(() => {
    const narrable = chunks.filter((c) => c.narration_text.trim()).length;
    if (
      !window.confirm(
        `¿Regenerar audio de los ${narrable} bloques narrables? Los MP3 actuales se sustituirán.`,
      )
    ) {
      return;
    }
    void runBatchAudio(true);
  }, [chunks, runBatchAudio]);

  const expandVisualRhythm = useCallback(
    async (id: string) => {
      setPlanningVisualId(id);
      setError(null);
      try {
        const data = await postJson<{ chunk: Chunk }>("/api/visual/expand-rhythm", {
          work,
          chunk_id: id,
          auto_plan: true,
        });
        setChunks((prev) => prev.map((c) => (c.id === id ? data.chunk : c)));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Error al dividir ritmo visual");
      } finally {
        setPlanningVisualId(null);
      }
    },
    [work],
  );

  const planVisual = useCallback(
    async (id: string) => {
      const chunk = chunks.find((c) => c.id === id);
      if (!chunk) return;
      if (!chunk.narration_text.trim()) {
        setError("Añade narración antes de planificar el visual.");
        return;
      }
      setPlanningVisualId(id);
      setError(null);
      setChunks((prev) =>
        prev.map((c) => (c.id === id ? { ...c, visual_status: "planning" as const } : c)),
      );
      try {
        const data = await postJson<{ chunk: Chunk }>("/api/visual/plan-chunk", {
          work,
          chunk_id: id,
          narration_text: chunk.narration_text,
        });
        setChunks((prev) => prev.map((c) => (c.id === id ? data.chunk : c)));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Error al planificar visual");
        setChunks((prev) =>
          prev.map((c) => (c.id === id ? { ...c, visual_status: "error" as const } : c)),
        );
      } finally {
        setPlanningVisualId(null);
      }
    },
    [chunks, work],
  );

  const runBatchVisual = useCallback(
    async (regenerateAll: boolean, chunkIds?: string[]) => {
      const plannable = chunks.filter((c) => c.narration_text.trim());
      if (plannable.length === 0) {
        setError("No hay bloques con narración.");
        return;
      }
      const isRange = Boolean(chunkIds?.length);
      const regenerate = regenerateAll || isRange;
      const pending = countPendingVisual(chunks);
      if (!regenerate && pending === 0) {
        setError("No hay bloques pendientes de prompt visual.");
        return;
      }

      const progressTotal = isRange
        ? (chunkIds?.length ?? 0)
        : regenerateAll
          ? plannable.length
          : pending;

      setBatchPlanning(true);
      setError(null);
      setVisualBatchProgress({ done: 0, total: progressTotal });

      const poll = window.setInterval(() => {
        void (async () => {
          try {
            const r = await fetch(`/api/scene-editor/chunks?work=${encodeURIComponent(work)}`);
            if (!r.ok) return;
            const data = (await r.json()) as ParseScriptResponse;
            if (!Array.isArray(data.chunks)) return;
            setChunks(data.chunks);
            if (regenerateAll && !isRange) {
              const withInput = data.chunks.filter((c) => c.narration_text.trim());
              setVisualBatchProgress({
                done: withInput.filter((c) => (c.ai_prompt ?? "").trim()).length,
                total: withInput.length,
              });
            } else if (isRange && chunkIds) {
              const idSet = new Set(chunkIds);
              const inRange = data.chunks.filter((c) => idSet.has(c.id));
              setVisualBatchProgress({
                done: inRange.filter(
                  (c) =>
                    c.visual_status === "done" &&
                    Boolean((c.scene_prompt_en ?? "").trim()) &&
                    Boolean((c.ai_prompt ?? "").trim()),
                ).length,
                total: inRange.length,
              });
            } else {
              const left = countPendingVisual(data.chunks);
              setVisualBatchProgress({
                done: Math.max(0, progressTotal - left),
                total: progressTotal,
              });
            }
          } catch {
            /* ignore */
          }
        })();
      }, 1500);

      try {
        const res = await postJson<PlanAllVisualResponse>("/api/visual/plan-all-chunks", {
          work,
          skip_with_prompt: !regenerate,
          regenerate_all: regenerateAll && !isRange,
          chunk_ids: isRange ? chunkIds : undefined,
        });
        setChunks(res.chunks);
        if (res.failed > 0) {
          const first = res.errors[0];
          setError(
            `Visual completado con ${res.failed} error(es). ${res.planned} planificados, ${res.skipped} omitidos.` +
              (first ? ` Ej.: ${first.detail}` : ""),
          );
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Error en planificación masiva");
      } finally {
        window.clearInterval(poll);
        setBatchPlanning(false);
        setVisualBatchProgress(null);
      }
    },
    [chunks, work],
  );

  const planPendingVisual = useCallback(() => runBatchVisual(false), [runBatchVisual]);

  const regenerateAllVisualPrompts = useCallback(() => {
    const plannable = chunks.filter((c) => c.narration_text.trim()).length;
    if (
      !window.confirm(
        `¿Regenerar prompts visuales de los ${plannable} bloques planificables? Se sustituirán los prompts actuales.`,
      )
    ) {
      return;
    }
    void runBatchVisual(true);
  }, [chunks, runBatchVisual]);

  const regenerateVisualRange = useCallback(
    (fromBlock: number, toBlock: number) => {
      if (chunks.length === 0) {
        setError("No hay bloques cargados.");
        return;
      }
      if (fromBlock < 1 || toBlock < fromBlock || toBlock > chunks.length) {
        setError(`Rango inválido. Usa bloques del 1 al ${chunks.length}.`);
        return;
      }
      const slice = chunks.slice(fromBlock - 1, toBlock);
      const plannableInRange = slice.filter(chunkIsPlannable);
      if (plannableInRange.length === 0) {
        setError("El rango no tiene bloques con narración.");
        return;
      }
      if (
        !window.confirm(
          `¿Regenerar prompts visuales de bloques ${fromBlock}–${toBlock}? Los prompts actuales de ese rango se borrarán y se crearán de nuevo desde la narración.`,
        )
      ) {
        return;
      }
      void runBatchVisual(false, plannableInRange.map((c) => c.id));
    },
    [chunks, runBatchVisual],
  );

  const exportUnifiedNarration = useCallback(async () => {
    const withAudio = chunks.filter((c) => c.audio_url?.trim());
    if (withAudio.length === 0) {
      setError("No hay bloques con audio. Genera audio en los bloques primero.");
      return;
    }
    if (
      !window.confirm(
        `¿Unir ${withAudio.length} audios en narracion.wav? Se usará para el render del vídeo.`,
      )
    ) {
      return;
    }
    setExportingNarration(true);
    setError(null);
    setExportInfo(null);
    try {
      const res = await postJson<ExportNarrationResponse>("/api/audio/export-narration", {
        work,
        chunk_gap_ms: 0,
      });
      const min = res.duration_s != null ? (res.duration_s / 60).toFixed(1) : "?";
      const miss =
        res.chunks_missing && res.chunks_missing.length > 0
          ? ` · ${res.chunks_missing.length} bloques sin archivo`
          : "";
      setExportInfo(
        `narracion.wav · ${res.chunks_used ?? withAudio.length} bloques · ~${min} min${miss}`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al unificar narración");
    } finally {
      setExportingNarration(false);
    }
  }, [chunks, work]);

  const exportImagePrompts = useCallback(async () => {
    const withPrompt = chunks.filter((c) => (c.ai_prompt ?? "").trim());
    if (withPrompt.length === 0) {
      setError("No hay prompts visuales para exportar. Planifica al menos un bloque.");
      return;
    }
    setExportingPrompts(true);
    setError(null);
    setExportInfo(null);
    try {
      const res = await postJson<ExportImagePromptsResponse>("/api/visual/export-image-prompts", {
        work,
      });
      setExportInfo(`${res.prompt_count} prompts → ${res.path}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al exportar prompts");
    } finally {
      setExportingPrompts(false);
    }
  }, [chunks, work]);

  return {
    chunks,
    parsing,
    generatingId,
    error,
    ttsConfig,
    voices,
    selectedVoiceId,
    setSelectedVoiceId,
    batchGenerating,
    batchProgress,
    pendingAudioCount: countPendingAudio(chunks),
    pendingVisualCount: countPendingVisual(chunks),
    visualConfig,
    planningVisualId,
    batchPlanning,
    visualBatchProgress,
    loadVisualConfig,
    exportingPrompts,
    exportingNarration,
    exportUnifiedNarration,
    exportInfo,
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
    planVisual,
    expandVisualRhythm,
    planPendingVisual,
    regenerateAllVisualPrompts,
    regenerateVisualRange,
    exportImagePrompts,
    setError,
  };
}
