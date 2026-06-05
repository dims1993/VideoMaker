import { useCallback, useEffect, useMemo, useState } from "react";
import { Btn } from "../../../components/ui";
import { postJson, putJson } from "../../../services/api";
import type { Chunk, ParseScriptResponse } from "../sceneEditor/types";
import type { RunFn } from "../types";
import {
  buildChunkById,
  resolveImageChunkAudio,
  type ImageChunkAudio,
} from "./imagesGenerationChunkAudio";
import { ProductionResetButton } from "./ProductionResetButton";
import { PipelineStepConfirmBar } from "./PipelineStepConfirmBar";
import { PipelineSection as Section } from "./PipelineSection";

type ImageEntry = {
  id: string; filename: string; act: string; order: number;
  timestamp_hint: string; duration_hint_s: number; role: string;
  scene_description_es: string; ai_prompt: string;
  status: "generated" | "pending" | "error" | string; selected: boolean;
  placeholder_alt?: string;
  prompt_id?: string;
  section?: string | null;
  error?: string;
  local_url?: string;
};

type Manifest = {
  version: number; generated_at?: string; generator?: string;
  style?: string; total: number; selected_count: number; images: ImageEntry[];
  image_prompts_source?: string;
};

type ImagenConfig = {
  mock: boolean;
  model: string;
  has_api_key: boolean;
};

const ACT_LABELS: Record<string, { label: string; color: string }> = {
  thumbnail: { label: "Miniatura", color: "bg-amber-900/60 text-amber-200 border border-amber-500/40" },
  hook:  { label: "Hook",   color: "bg-violet-900/60 text-violet-300 border border-violet-500/30" },
  intro: { label: "Intro",  color: "bg-purple-900/60 text-purple-300 border border-purple-500/30" },
  body:  { label: "Body",   color: "bg-blue-900/60   text-blue-300   border border-blue-500/30"  },
  cta:   { label: "CTA",    color: "bg-sky-900/60    text-sky-300    border border-sky-500/30"   },
  outro: { label: "Outro",  color: "bg-emerald-900/60 text-emerald-300 border border-emerald-500/30" },
  act2:  { label: "Acto 2", color: "bg-blue-900/60   text-blue-300   border border-blue-500/30"  },
  act3:  { label: "Acto 3", color: "bg-amber-900/60  text-amber-300  border border-amber-500/30" },
  act4:  { label: "Acto 4", color: "bg-emerald-900/60 text-emerald-300 border border-emerald-500/30" },
};

const PLACEHOLDER_ALT = "Imagen por desarrollar";

function formatImagenError(detail: string): string {
  if (detail.includes("429") || detail.includes("RESOURCE_EXHAUSTED") || detail.toLowerCase().includes("credits are depleted")) {
    return "Créditos de Google Imagen agotados. Recarga en AI Studio o activa GOOGLE_IMAGEN_MOCK=1 en .env para pruebas.";
  }
  return detail.length > 220 ? `${detail.slice(0, 220)}…` : detail;
}

type GeminiWebJob = {
  state?: string;
  total?: number;
  done?: number;
  failed?: number;
  current_order?: number | null;
  current_id?: string | null;
  page_url?: string | null;
  error?: string;
  last_log?: string;
  log_lines?: string[];
  batch_mode?: boolean;
  batch_size?: number | null;
  batch_total?: number;
  batch_index?: number;
  items?: { id: string; order: number; status: string; detail?: string }[];
};

function ImageChunkAudioBar({ audio }: { audio: ImageChunkAudio }) {
  if (!audio.hasAudio) {
    return (
      <div
        className="border-t border-slate-700/80 bg-slate-900/90 px-2 py-2"
        onClick={(e) => e.stopPropagation()}
      >
        <p className="text-[10px] text-slate-500">Sin audio TTS — genera el bloque en Scene Editor</p>
      </div>
    );
  }
  return (
    <div
      className="border-t border-slate-700/80 bg-slate-900/90 px-2 py-2 space-y-1"
      onClick={(e) => e.stopPropagation()}
    >
      <div className="flex items-center gap-2">
        <span className="shrink-0 text-[10px] font-medium uppercase tracking-wide text-violet-300/90">
          Locución
        </span>
        {audio.durationLabel ? (
          <span className="text-[10px] text-slate-500">{audio.durationLabel}</span>
        ) : null}
      </div>
      <audio
        key={audio.audioUrl ?? audio.chunkId}
        controls
        className="w-full h-8 max-h-8"
        src={audio.audioUrl ?? undefined}
        preload="none"
      />
      {audio.narrationText ? (
        <p className="text-[10px] leading-snug text-slate-400 line-clamp-3" title={audio.narrationText}>
          {audio.narrationText}
        </p>
      ) : null}
    </div>
  );
}

function ImageCard({ img, workApplied, cacheBust, chunkAudio, onToggle, onPreview, geminiProcessing }: {
  img: ImageEntry; workApplied: string; cacheBust: number;
  chunkAudio: ImageChunkAudio;
  onToggle: (id: string) => void; onPreview: (img: ImageEntry) => void;
  geminiProcessing?: boolean;
}) {
  const imgUrl = `/api/pipeline/images-generation/image?work=${encodeURIComponent(workApplied)}&filename=${encodeURIComponent(img.filename)}&t=${cacheBust}`;
  const actKey = img.role === "thumbnail" ? "thumbnail" : img.act;
  const act = ACT_LABELS[actKey] ?? { label: actKey, color: "bg-slate-700 text-slate-300 border border-slate-500" };
  const placeholderAlt = img.placeholder_alt?.trim() || PLACEHOLDER_ALT;
  const isGenerated = img.status === "generated";
  const isError = img.status === "error";

  return (
    <div
      className={`group relative flex flex-col overflow-hidden rounded-xl border-2 transition-all cursor-pointer ${geminiProcessing ? "border-amber-400 shadow-md shadow-amber-900/50 animate-pulse" : img.selected ? "border-indigo-500 shadow-md shadow-indigo-900/50" : "border-slate-600 hover:border-slate-500"} ${isError ? "border-rose-500/60" : ""}`}
      onClick={() => onToggle(img.id)}
    >
      <div className="relative aspect-video bg-slate-800 overflow-hidden">
        {isGenerated ? (
          <img src={imgUrl} alt={img.scene_description_es || placeholderAlt} className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105" loading="lazy" />
        ) : (
          <div
            className="flex h-full w-full flex-col items-center justify-center gap-1.5 bg-gradient-to-br from-slate-800 to-slate-900 px-2 text-center"
            role="img"
            aria-label={placeholderAlt}
          >
            <div className={`rounded-lg border border-dashed px-2 py-1 text-[10px] font-medium uppercase tracking-wide ${isError ? "border-rose-500/50 text-rose-400" : "border-slate-600 text-slate-500"}`}>
              {isError ? "Error" : "Pendiente"}
            </div>
            <p className="text-[11px] leading-snug text-slate-400">{isError ? formatImagenError(img.error ?? "Error al generar") : placeholderAlt}</p>
          </div>
        )}
        <div className={`absolute inset-0 transition-colors ${img.selected ? "bg-indigo-600/10" : "bg-transparent"}`} />
        <div className="absolute top-2 left-2">
          <div className={`h-5 w-5 rounded border-2 flex items-center justify-center transition-colors ${img.selected ? "border-indigo-500 bg-indigo-600" : "border-slate-400 bg-black/60"}`}>
            {img.selected && (
              <svg className="h-3 w-3 text-white" viewBox="0 0 12 12" fill="none">
                <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
          </div>
        </div>
        <div className="absolute top-2 right-2 h-5 min-w-5 rounded bg-black/70 px-1.5 text-[10px] font-bold text-white flex items-center justify-center">{img.order}</div>
        <button className="absolute bottom-2 right-2 rounded bg-black/70 px-2 py-0.5 text-[10px] text-white opacity-0 group-hover:opacity-100 transition-opacity"
          onClick={(e) => { e.stopPropagation(); onPreview(img); }}>
          Ver prompt
        </button>
      </div>
      <ImageChunkAudioBar audio={chunkAudio} />
      <div className="flex flex-col gap-1 p-2 bg-slate-800">
        <div className="flex items-center gap-1 flex-wrap">
          <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-semibold ${act.color}`}>{act.label}</span>
          <span className="text-[10px] text-slate-500">{img.timestamp_hint}</span>
          <span className="text-[10px] text-slate-500">· {img.duration_hint_s}s</span>
          <span className="text-[10px] font-mono text-slate-600">{img.filename}</span>
        </div>
        <p className="text-xs text-slate-300 line-clamp-2 leading-tight">{img.scene_description_es}</p>
      </div>
    </div>
  );
}

function PromptModal({
  img,
  chunkAudio,
  onClose,
}: {
  img: ImageEntry;
  chunkAudio: ImageChunkAudio;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-y-0 left-[280px] right-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={onClose}>
      <div className="relative max-w-2xl w-full rounded-2xl bg-white p-5 shadow-2xl space-y-3" onClick={(e) => e.stopPropagation()}>
        <button className="absolute right-4 top-4 text-slate-400 hover:text-slate-700" onClick={onClose}>✕</button>
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-slate-900">#{img.order} — {img.role}</span>
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-600">{img.act}</span>
        </div>
        <p className="text-sm text-slate-700">{img.scene_description_es}</p>
        <div className="rounded-xl border border-violet-200 bg-violet-50/50 p-3">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-violet-700">Locución del bloque</p>
          {chunkAudio.hasAudio ? (
            <audio controls className="w-full" src={chunkAudio.audioUrl ?? undefined} preload="none" />
          ) : (
            <p className="text-xs text-slate-500">Sin audio en Scene Editor para este bloque.</p>
          )}
          {chunkAudio.narrationText ? (
            <p className="mt-2 text-xs text-slate-600 leading-relaxed">{chunkAudio.narrationText}</p>
          ) : null}
        </div>
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">AI Prompt (en)</p>
          <p className="text-xs text-slate-700 leading-relaxed">{img.ai_prompt}</p>
        </div>
        <p className="text-[10px] text-slate-400">
          Archivo: <code>{img.filename}</code> · {img.timestamp_hint} · {img.duration_hint_s}s
        </p>
      </div>
    </div>
  );
}

export function ImagesGenerationPanel({
  run, workApplied, refreshPipeline, imagesStepState,
}: {
  run: RunFn; workApplied: string; refreshPipeline: () => Promise<void>; imagesStepState: string;
}) {
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [hasManifest, setHasManifest] = useState(false);
  const [chunkById, setChunkById] = useState<Map<string, Chunk>>(() => new Map());
  const [previewImg, setPreviewImg] = useState<ImageEntry | null>(null);
  const [imagenConfig, setImagenConfig] = useState<ImagenConfig | null>(null);
  const [generating, setGenerating] = useState(false);
  const [geminiStarting, setGeminiStarting] = useState(false);
  const [generateInfo, setGenerateInfo] = useState<string | null>(null);
  const [geminiInfo, setGeminiInfo] = useState<string | null>(null);
  const [geminiJob, setGeminiJob] = useState<GeminiWebJob | null>(null);
  const [geminiCdpOk, setGeminiCdpOk] = useState<boolean | null>(null);
  const [geminiCdpDetail, setGeminiCdpDetail] = useState<string | null>(null);
  const [chromeHint, setChromeHint] = useState<string | null>(null);
  const [cacheBust, setCacheBust] = useState(() => Date.now());
  const [deleteInfo, setDeleteInfo] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [batchMode, setBatchMode] = useState(true);
  const [batchSize, setBatchSize] = useState(1);
  const [orderFrom, setOrderFrom] = useState<number>(1);
  const [orderTo, setOrderTo] = useState<number>(1);
  const [rangeInitialized, setRangeInitialized] = useState(false);
  const [removingWatermark, setRemovingWatermark] = useState(false);
  const [watermarkInfo, setWatermarkInfo] = useState<string | null>(null);
  const [imagesResetInfo, setImagesResetInfo] = useState<string | null>(null);
  const chunkAudioFor = useCallback(
    (img: ImageEntry) => resolveImageChunkAudio(workApplied, img, chunkById),
    [workApplied, chunkById],
  );

  const previewChunkAudio = useMemo(
    () => (previewImg ? chunkAudioFor(previewImg) : null),
    [previewImg, chunkAudioFor],
  );

  const geminiRunning = geminiJob?.state === "running";
  const generationRunning =
    imagesStepState === "running" || generating || geminiRunning || geminiStarting || deleting || removingWatermark;

  const loadSceneChunks = useCallback(async () => {
    const r = await fetch(`/api/scene-editor/chunks?work=${encodeURIComponent(workApplied)}`);
    if (!r.ok) {
      setChunkById(new Map());
      return;
    }
    const j = (await r.json()) as ParseScriptResponse;
    setChunkById(buildChunkById(Array.isArray(j.chunks) ? j.chunks : []));
  }, [workApplied]);

  const loadManifest = useCallback(async () => {
    const r = await fetch(`/api/pipeline/images-generation?work=${encodeURIComponent(workApplied)}`);
    if (!r.ok) return;
    const j = (await r.json()) as { exists?: boolean; manifest?: Manifest | null };
    if (j.exists && j.manifest) { setManifest(j.manifest); setHasManifest(true); }
    else { setManifest(null); setHasManifest(false); }
    void loadSceneChunks();
  }, [workApplied, loadSceneChunks]);

  const loadImagenConfig = useCallback(async () => {
    const r = await fetch("/api/pipeline/images-generation/config");
    if (!r.ok) return;
    setImagenConfig((await r.json()) as ImagenConfig);
  }, []);

  const loadGeminiStatus = useCallback(async () => {
    const r = await fetch(`/api/pipeline/images-generation/gemini-web/status?work=${encodeURIComponent(workApplied)}`);
    if (!r.ok) return;
    const j = (await r.json()) as {
      cdp?: { cdp_connected?: boolean; port_open?: boolean; detail?: string };
      job?: GeminiWebJob | null;
      chrome_hint?: string;
    };
    setGeminiCdpOk(j.cdp?.cdp_connected ?? false);
    setGeminiCdpDetail(j.cdp?.detail ?? null);
    setGeminiJob(j.job ?? null);
    if (j.chrome_hint) setChromeHint(j.chrome_hint);
    if (j.job?.state === "running") {
      setCacheBust(Date.now());
      await loadManifest();
    }
    if (j.job?.state === "done" || j.job?.state === "error" || j.job?.state === "cancelled") {
      setCacheBust(Date.now());
      await loadManifest();
      await refreshPipeline();
    }
  }, [workApplied, loadManifest, refreshPipeline]);

  useEffect(() => {
    void loadManifest();
    void loadImagenConfig();
    void loadGeminiStatus();
  }, [loadManifest, loadImagenConfig, loadGeminiStatus, imagesStepState, workApplied]);

  useEffect(() => {
    void loadSceneChunks();
  }, [loadSceneChunks, workApplied]);

  useEffect(() => {
    if (!manifest || rangeInitialized) return;
    const pending = manifest.images.filter((i) => i.status === "pending" || i.status === "error" || !i.status);
    if (pending.length === 0) return;
    const orders = pending.map((i) => i.order);
    setOrderFrom(Math.min(...orders));
    setOrderTo(Math.max(...orders));
    setRangeInitialized(true);
  }, [manifest, rangeInitialized]);

  useEffect(() => {
    if (!geminiRunning) return;
    const t = window.setInterval(() => { void loadGeminiStatus(); }, 2500);
    return () => window.clearInterval(t);
  }, [geminiRunning, loadGeminiStatus]);

  const toggleImage = (id: string) => {
    if (!manifest) return;
    const updated: Manifest = { ...manifest, images: manifest.images.map((img) => img.id === id ? { ...img, selected: !img.selected } : img) };
    updated.selected_count = updated.images.filter((i) => i.selected).length;
    setManifest(updated);
  };

  const selectAll = async (val: boolean) => {
    if (!manifest) return;
    const updated: Manifest = {
      ...manifest,
      images: manifest.images.map((img) => ({ ...img, selected: val })),
      selected_count: val ? manifest.images.length : 0,
    };
    setManifest(updated);
    try {
      await putJson("/api/pipeline/images-generation", { work: workApplied, manifest: updated });
    } catch (e) {
      setDeleteInfo(e instanceof Error ? e.message : "No se pudo guardar la selección");
      await loadManifest();
    }
  };

  const deselectAllAndClearErrors = async () => {
    if (!manifest) return;
    const updated: Manifest = {
      ...manifest,
      images: manifest.images.map((img) => ({
        ...img,
        selected: false,
        ...(img.status === "error" ? { status: "pending" as const, error: undefined } : {}),
      })),
      selected_count: 0,
    };
    setManifest(updated);
    await putJson("/api/pipeline/images-generation", { work: workApplied, manifest: updated });
    await loadManifest();
  };

  const saveManifest = async () => {
    if (!manifest) return;
    await putJson("/api/pipeline/images-generation", { work: workApplied, manifest });
    await loadManifest();
    await refreshPipeline();
  };

  const selectedPendingCount =
    manifest?.images.filter((i) => i.selected && (i.status === "pending" || i.status === "error" || !i.status)).length ?? 0;
  const selectedAlreadyDoneCount =
    manifest?.images.filter((i) => i.selected && i.status === "generated").length ?? 0;
  const selectedCount = manifest?.images.filter((i) => i.selected).length ?? 0;
  const totalCount = manifest?.images.length ?? 0;
  const generatedCount = manifest?.images.filter((i) => i.status === "generated").length ?? 0;
  const pendingCount = totalCount - generatedCount;

  const selectedGeneratedCount =
    manifest?.images.filter((i) => i.selected && i.status === "generated").length ?? 0;

  const deleteSelectedImages = async () => {
    if (!manifest) return;
    const selected = manifest.images.filter((i) => i.selected);
    if (selected.length === 0) {
      const msg = "No hay tarjetas seleccionadas. Marca al menos una con ✓ o pulsa «Seleccionar todas».";
      setDeleteInfo(msg);
      throw new Error(msg);
    }
    const imageIds = selected.map((i) => i.id);
    const withFile = selected.filter((i) => i.status === "generated").length;
    const msg =
      withFile > 0
        ? `¿Eliminar ${withFile} archivo(s) PNG del disco (${selected.length} tarjeta(s) seleccionada(s))? Las tarjetas volverán a «Pendiente».`
        : `¿Resetear ${selected.length} tarjeta(s) seleccionada(s) a «Pendiente»? (no hay PNG en disco)`;
    if (!window.confirm(msg)) return;

    setDeleting(true);
    setDeleteInfo(null);
    try {
      const toSave: Manifest = {
        ...manifest,
        images: manifest.images.map((img) => ({
          ...img,
          selected: imageIds.includes(img.id),
        })),
        selected_count: imageIds.length,
      };
      await putJson("/api/pipeline/images-generation", { work: workApplied, manifest: toSave });
      setManifest(toSave);

      const res = (await postJson<{
        deleted: number;
        updated: number;
        files_missing?: number;
        manifest: Manifest;
      }>("/api/pipeline/images-generation/delete-selected", {
        work: workApplied,
        image_ids: imageIds,
      })) as {
        deleted: number;
        updated: number;
        files_missing?: number;
        manifest: Manifest;
      };
      setCacheBust(Date.now());
      await loadManifest();
      setDeleteInfo(
        res.deleted > 0
          ? `Eliminados ${res.deleted} archivo(s) PNG · ${res.updated} tarjeta(s) en pendiente`
          : withFile === 0
            ? `${res.updated} tarjeta(s) ya estaban pendientes (no había PNG en disco)`
            : `${res.updated} tarjeta(s) reseteadas · ${res.files_missing ?? 0} archivo(s) no encontrados en disco`,
      );
      await refreshPipeline();
    } catch (e) {
      const detail = e instanceof Error ? e.message : "Error al eliminar imágenes";
      setDeleteInfo(detail);
      throw e instanceof Error ? e : new Error(detail);
    } finally {
      setDeleting(false);
    }
  };

  const pendingInRangeCount =
    manifest?.images.filter(
      (i) =>
        i.order >= orderFrom &&
        i.order <= orderTo &&
        (i.status === "pending" || i.status === "error" || !i.status),
    ).length ?? 0;
  const batchCount = batchMode && pendingInRangeCount > 0 ? Math.ceil(pendingInRangeCount / batchSize) : 1;
  const geminiTargetCount = batchMode ? pendingInRangeCount : selectedPendingCount;

  const startGeminiQueue = async () => {
    if (!manifest) return;
    let targets: ImageEntry[];
    if (batchMode) {
      targets = manifest.images.filter(
        (i) =>
          i.order >= orderFrom &&
          i.order <= orderTo &&
          (i.status === "pending" || i.status === "error" || !i.status),
      );
    } else {
      const selected = manifest.images.filter((i) => i.selected);
      targets = selected.filter((i) => i.status === "pending" || i.status === "error" || !i.status);
    }
    if (targets.length === 0) return;
    const imageIds = targets.map((i) => i.id);
    setGeminiStarting(true);
    setGeminiInfo(null);
    try {
      const toSave: Manifest = {
        ...manifest,
        images: manifest.images.map((img) => ({
          ...img,
          selected: imageIds.includes(img.id),
        })),
        selected_count: imageIds.length,
      };
      await putJson("/api/pipeline/images-generation", { work: workApplied, manifest: toSave });
      setManifest(toSave);
      await postJson("/api/pipeline/images-generation/gemini-web/start", {
        work: workApplied,
        image_ids: imageIds,
        skip_generated: true,
        batch_mode: batchMode,
        batch_size: batchSize,
        order_from: batchMode ? orderFrom : undefined,
        order_to: batchMode ? orderTo : undefined,
      });
      const batchMsg =
        batchMode && batchCount > 1
          ? `${batchCount} lotes de hasta ${batchSize} · conversación nueva entre lotes`
          : batchMode
            ? "1 lote en la misma conversación"
            : "misma conversación de Gemini";
      const rangeMsg = batchMode ? ` (#${Math.min(orderFrom, orderTo)}–#${Math.max(orderFrom, orderTo)})` : "";
      setGeminiInfo(`Cola iniciada: ${imageIds.length} imágenes${rangeMsg} · ${batchMsg}.`);
      await loadGeminiStatus();
    } catch (e) {
      setGeminiInfo(e instanceof Error ? e.message : "No se pudo iniciar la cola Gemini");
    } finally {
      setGeminiStarting(false);
    }
  };

  const removeGeminiWatermarks = async () => {
    if (!manifest) return;
    const selected = manifest.images.filter((i) => i.selected && i.status === "generated");
    const count = selected.length > 0 ? selected.length : generatedCount;
    if (count === 0) return;
    const msg =
      selected.length > 0
        ? `¿Quitar marca de agua Gemini en ${selected.length} imagen(es) seleccionada(s)? Se guardará copia en _backup_before_watermark.`
        : `¿Quitar marca de agua en las ${generatedCount} imágenes generadas? Se guardará copia de seguridad.`;
    if (!window.confirm(msg)) return;

    setRemovingWatermark(true);
    setWatermarkInfo(null);
    try {
      const res = (await postJson<{
        processed?: number;
        failed?: number;
        backup_dir?: string | null;
        errors?: { filename?: string; detail: string }[];
      }>("/api/pipeline/images-generation/remove-gemini-watermark", {
        work: workApplied,
        image_ids: selected.map((i) => i.id),
        backup: true,
      })) as {
        processed?: number;
        failed?: number;
        backup_dir?: string | null;
        errors?: { filename?: string; detail: string }[];
      };
      const firstErr = res.errors?.[0]?.detail;
      setWatermarkInfo(
        `Marca de agua: ${res.processed ?? 0} procesadas` +
          ((res.failed ?? 0) > 0 ? ` · ${res.failed} fallos` : "") +
          (res.backup_dir ? ` · backup en images/_backup_before_watermark` : "") +
          (firstErr ? ` — ${firstErr}` : ""),
      );
      setCacheBust(Date.now());
      await loadManifest();
      await refreshPipeline();
    } catch (e) {
      setWatermarkInfo(e instanceof Error ? e.message : "Error al quitar marca de agua");
    } finally {
      setRemovingWatermark(false);
    }
  };

  const cancelGeminiQueue = async () => {
    setGeminiJob((prev) =>
      prev
        ? {
            ...prev,
            state: "cancelled",
            current_order: null,
            current_id: null,
            last_log: "Cancelando cola…",
          }
        : prev,
    );
    setGeminiInfo("Cancelando cola…");
    try {
      await postJson("/api/pipeline/images-generation/gemini-web/cancel", { work: workApplied });
      await loadGeminiStatus();
      await loadManifest();
      setGeminiInfo("Cola cancelada.");
    } catch (e) {
      setGeminiInfo(e instanceof Error ? e.message : "No se pudo cancelar la cola");
      await loadGeminiStatus();
    }
  };

  const generateSelected = async (regenerate = false) => {
    if (!manifest) return;
    const selected = manifest.images.filter((i) => i.selected);
    const targets = regenerate
      ? selected
      : selected.filter((i) => i.status === "pending" || i.status === "error" || !i.status);
    if (targets.length === 0) return;

    const imageIds = targets.map((i) => i.id);
    setGenerating(true);
    setGenerateInfo(null);
    try {
      // Persistir selección actual antes de generar (evita usar las 92 selected=true del disco)
      const toSave: Manifest = {
        ...manifest,
        images: manifest.images.map((img) => ({
          ...img,
          selected: imageIds.includes(img.id),
        })),
        selected_count: imageIds.length,
      };
      await putJson("/api/pipeline/images-generation", { work: workApplied, manifest: toSave });
      setManifest(toSave);

      const res = (await postJson("/api/pipeline/images-generation/generate-selected", {
        work: workApplied,
        image_ids: imageIds,
        skip_generated: !regenerate,
        regenerate,
      })) as {
        generated?: number;
        failed?: number;
        total_requested?: number;
        stale_errors_cleared?: number;
        mock?: boolean;
        errors?: { id?: string; detail: string }[];
      };
      const mockLabel = res.mock ? " (mock)" : "";
      const firstErr = res.errors?.[0]?.detail;
      let msg = `Solicitadas: ${res.total_requested ?? imageIds.length} · Generadas: ${res.generated ?? 0}${mockLabel}`;
      if ((res.stale_errors_cleared ?? 0) > 0) {
        msg += ` · ${res.stale_errors_cleared} errores antiguos limpiados`;
      }
      if ((res.failed ?? 0) > 0) {
        msg += ` · Fallos: ${res.failed}`;
        if (firstErr) msg += ` — ${formatImagenError(firstErr)}`;
      }
      if ((res.generated ?? 0) === 0 && (res.failed ?? 0) > 0) {
        setGenerateInfo(msg);
      } else {
        setGenerateInfo(msg);
      }
      setCacheBust(Date.now());
      await loadManifest();
      await refreshPipeline();
    } catch (e) {
      setGenerateInfo(e instanceof Error ? formatImagenError(e.message) : "Error al generar imágenes");
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="rounded-2xl bg-slate-900 p-4 space-y-4">

      <PipelineStepConfirmBar
        stepId="images_generation"
        stepLabel="Images Generation"
        workApplied={workApplied}
        stepState={imagesStepState}
        run={run}
        onAfterRun={refreshPipeline}
      />

      {manifest?.image_prompts_source === "validation_sample" ? (
        <p className="rounded-xl border border-cyan-500/40 bg-cyan-950/30 px-3 py-2 text-xs text-cyan-200">
          <strong className="text-cyan-100">Muestra de validación.</strong> Tarjetas con borde azul ya están
          preseleccionadas. Pulsa <strong className="text-cyan-100">Generar con Gemini Pro</strong> — por defecto
          cada imagen usa <strong className="text-cyan-100">su propia conversación</strong> (lote de 1) para
          variar escena.
        </p>
      ) : null}

      <div className="rounded-xl border border-slate-600 bg-slate-800 px-3 py-2 text-xs text-slate-400 space-y-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
          <span className="font-semibold text-white">Images Generation</span> — dos motores:
          <span className="ml-1 text-violet-300">Gemini Pro (navegador, cola)</span>
          {" · "}
          <span className="text-slate-300">Google Imagen API</span>{" "}
          <code className="rounded bg-slate-700 px-1">GOOGLE_API_KEY</code>.
          {imagenConfig ? (
            <span className="ml-1">
              {imagenConfig.mock ? (
                <span className="text-amber-300">Mock Imagen</span>
              ) : imagenConfig.has_api_key ? (
                <span className="text-emerald-300">API · {imagenConfig.model}</span>
              ) : (
                <span className="text-rose-300">Sin API key Imagen</span>
              )}
            </span>
          ) : null}
          </div>
          <ProductionResetButton
            workApplied={workApplied}
            scope="images_generation"
            label="Nuevo proyecto (imágenes)"
            disabled={generationRunning}
            onDone={async (msg) => {
              setImagesResetInfo(msg);
              setManifest(null);
              setHasManifest(false);
              setPreviewImg(null);
              setCacheBust(Date.now());
              await loadManifest();
              await refreshPipeline();
            }}
          />
        </div>
        <div className="rounded-lg border border-violet-500/30 bg-violet-950/20 p-2 space-y-1.5">
          <p className="text-violet-200 font-medium">Gemini Pro (cola automatizada)</p>
          <p>
            Chrome con depuración remota:{" "}
            {geminiCdpOk === null ? (
              <span className="text-slate-500">comprobando…</span>
            ) : geminiCdpOk ? (
              <span className="text-emerald-300">conectado</span>
            ) : (
              <span className="text-rose-300">no conectado</span>
            )}
          </p>
          <div className="rounded-md border border-violet-500/20 bg-slate-900/40 p-2 space-y-2">
            <label className="flex items-center gap-2 text-[11px] text-violet-100 cursor-pointer">
              <input
                type="checkbox"
                checked={batchMode}
                onChange={(e) => setBatchMode(e.target.checked)}
                disabled={generationRunning}
                className="rounded border-violet-400"
              />
              Conversación nueva por lote (recomendado)
            </label>
            <p className="text-[10px] leading-snug text-slate-500">
              Por defecto <strong className="text-slate-400">lote de 1</strong> = una conversación Gemini por imagen
              (mejor variedad de escena). Sube el lote (p. ej. 15–20) en producción masiva para más cohesión de
              personaje.
            </p>
            {batchMode ? (
              <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-300">
                <span>Desde</span>
                <input
                  type="number"
                  min={1}
                  value={orderFrom}
                  onChange={(e) => setOrderFrom(Math.max(1, parseInt(e.target.value, 10) || 1))}
                  disabled={generationRunning}
                  className="w-16 rounded border border-slate-600 bg-slate-800 px-2 py-1 text-center text-slate-100"
                />
                <span>hasta</span>
                <input
                  type="number"
                  min={1}
                  value={orderTo}
                  onChange={(e) => setOrderTo(Math.max(1, parseInt(e.target.value, 10) || 1))}
                  disabled={generationRunning}
                  className="w-16 rounded border border-slate-600 bg-slate-800 px-2 py-1 text-center text-slate-100"
                />
                <span>· lote de</span>
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={batchSize}
                  onChange={(e) => setBatchSize(Math.min(50, Math.max(1, parseInt(e.target.value, 10) || 20)))}
                  disabled={generationRunning}
                  className="w-14 rounded border border-slate-600 bg-slate-800 px-2 py-1 text-center text-slate-100"
                />
                <span>imágenes</span>
                {pendingInRangeCount > 0 ? (
                  <span className="text-violet-300">
                    → {pendingInRangeCount} pendientes · {batchCount} lote{batchCount !== 1 ? "s" : ""}
                  </span>
                ) : (
                  <span className="text-amber-300">Sin pendientes en ese rango</span>
                )}
              </div>
            ) : (
              <p className="text-[11px] text-amber-200/90">
                Sin lotes: todas las imágenes en la <strong>misma</strong> conversación (personaje muy estable,
                escenas que se repiten). Usa tarjetas ✓ ({selectedPendingCount} pendientes).
              </p>
            )}
          </div>
          {geminiCdpDetail && !geminiCdpOk ? (
            <p className="text-[11px] text-amber-200/90 leading-snug">{geminiCdpDetail}</p>
          ) : null}
          {geminiRunning && geminiJob ? (
            <p className="text-amber-200">
              Cola activa: {geminiJob.done ?? 0}/{geminiJob.total ?? 0} listas
              {(geminiJob.failed ?? 0) > 0 ? ` · ${geminiJob.failed} fallos` : ""}
              {geminiJob.batch_mode && (geminiJob.batch_total ?? 0) > 1
                ? ` · lote ${(geminiJob.batch_index ?? 0) + 1}/${geminiJob.batch_total}`
                : ""}
              {geminiJob.current_order != null ? ` · generando #${geminiJob.current_order}` : ""}
            </p>
          ) : null}
          {geminiJob?.last_log ? (
            <p className="text-[11px] text-slate-300 font-mono leading-snug">{geminiJob.last_log}</p>
          ) : null}
          {chromeHint ? (
            <pre className="mt-1 max-h-28 overflow-auto rounded bg-slate-900/80 p-2 text-[10px] text-slate-400 whitespace-pre-wrap">{chromeHint}</pre>
          ) : null}
          {geminiInfo ? (
            <p className={`text-[11px] ${geminiInfo.includes("Cola iniciada") ? "text-emerald-300" : "text-rose-300"}`}>{geminiInfo}</p>
          ) : null}
          <div className="flex flex-wrap gap-2 pt-1">
            <Btn
              type="button"
              className="bg-violet-600 text-white hover:bg-violet-500 disabled:opacity-40 text-xs"
              disabled={generationRunning || !hasManifest || geminiTargetCount === 0 || geminiCdpOk === false}
              onClick={() => run(`Cola Gemini (${geminiTargetCount})`, () => startGeminiQueue())}
            >
              {geminiRunning ? "Cola Gemini en curso…" : `Generar con Gemini Pro (${geminiTargetCount})`}
            </Btn>
            {geminiRunning ? (
              <Btn type="button" className="border border-rose-500/50 text-rose-200 text-xs" onClick={() => void cancelGeminiQueue()}>
                Cancelar cola
              </Btn>
            ) : null}
            <Btn type="button" className="border border-slate-500 bg-slate-700 text-slate-200 text-xs" onClick={() => void loadGeminiStatus()}>
              Comprobar Chrome
            </Btn>
          </div>
        </div>
      </div>

      {generationRunning && (
        <div className="rounded-xl border border-amber-500/40 bg-amber-950/30 px-3 py-2 text-xs text-amber-300">
          {generating ? "Generando imágenes seleccionadas con Google Imagen…" : "Generando imágenes…"}
        </div>
      )}

      {generateInfo ? (
        <div
          className={`rounded-xl border px-3 py-2 text-xs ${
            /Generadas: 0/.test(generateInfo) || generateInfo.includes("Fallos")
              ? "border-rose-500/40 bg-rose-950/30 text-rose-200"
              : "border-emerald-500/40 bg-emerald-950/30 text-emerald-200"
          }`}
        >
          {generateInfo}
        </div>
      ) : null}

      {watermarkInfo ? (
        <div
          className={`rounded-xl border px-3 py-2 text-xs ${
            watermarkInfo.includes("fallos") || watermarkInfo.includes("Error")
              ? "border-rose-500/40 bg-rose-950/30 text-rose-200"
              : "border-amber-500/40 bg-amber-950/30 text-amber-200"
          }`}
        >
          {watermarkInfo}
        </div>
      ) : null}

      {imagesResetInfo ? (
        <p className="rounded-xl border border-rose-500/40 bg-rose-950/30 px-3 py-2 text-xs text-rose-200">
          {imagesResetInfo}
        </p>
      ) : null}

      {deleteInfo ? (
        <div
          className={`rounded-xl border px-3 py-2 text-xs ${
            deleteInfo.includes("Error") || deleteInfo.includes("error")
              ? "border-rose-500/40 bg-rose-950/30 text-rose-200"
              : "border-slate-500/40 bg-slate-800/80 text-slate-200"
          }`}
        >
          {deleteInfo}
        </div>
      ) : null}

      <Section id="images-process" title="Proceso De Generación" description="Motor, estilo y distribución de imágenes por acto.">
        <ul className="list-disc pl-4 space-y-0.5 text-[11px] text-slate-400">
          <li>Prompts desde <strong className="text-slate-300">Image Prompt Writer</strong> → botón Enviar a Images Generation</li>
          <li><strong className="text-slate-300">Gemini Pro</strong>: Chrome con puerto 9222 — cola automatizada; con lotes activos abre conversación nueva cada ~20 imágenes</li>
          <li><strong className="text-slate-300">Imagen API</strong>: selecciona escenas y pulsa Generar seleccionadas (prepago)</li>
          <li>Se guardan como <code className="rounded bg-slate-700 px-1">001.png</code>, <code className="rounded bg-slate-700 px-1">002.png</code>… en <code className="rounded bg-slate-700 px-1">pipeline/images/</code></li>
          <li><strong className="text-slate-300">Marca de agua</strong>: botón para quitar la estrella Gemini (esquina inferior derecha; backup automático)</li>
          <li>Mock: <code className="rounded bg-slate-700 px-1">GOOGLE_IMAGEN_MOCK=1</code> en .env</li>
        </ul>
      </Section>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-slate-400">
            {hasManifest
              ? `${selectedCount} de ${totalCount} marcadas para generar · ${generatedCount} generadas · ${pendingCount} pendientes`
              : "Sin manifest — envía prompts desde Image Prompt Writer"}
          </span>
          {hasManifest && selectedCount > 0 ? (
            <span className="text-[10px] text-violet-300">
              Solo se generan las tarjetas con ✓ azul
            </span>
          ) : null}
          {hasManifest && (
            <>
              <Btn type="button" className="border border-slate-500 bg-slate-700 text-slate-200 hover:bg-slate-600 text-xs" onClick={() => void selectAll(true)}>Seleccionar todas</Btn>
              <Btn type="button" className="border border-slate-500 bg-slate-700 text-slate-200 hover:bg-slate-600 text-xs" onClick={() => void deselectAllAndClearErrors()}>Deseleccionar y limpiar errores</Btn>
            </>
          )}
        </div>
        <div className="flex gap-2 flex-wrap">
          <Btn type="button" className="border border-slate-600 bg-slate-800 text-slate-200 hover:bg-slate-700" onClick={() => void loadManifest()}>Recargar</Btn>
          <Btn
            type="button"
            className="bg-violet-600 text-white hover:bg-violet-500 disabled:opacity-40"
            disabled={generationRunning || !hasManifest || selectedPendingCount === 0}
            onClick={() => run(`Generar ${selectedPendingCount} imágenes`, () => generateSelected(false))}
          >
            {generating ? "Generando…" : `Generar seleccionadas (${selectedPendingCount})`}
          </Btn>
          {selectedAlreadyDoneCount > 0 ? (
            <Btn
              type="button"
              className="border border-violet-500/50 bg-violet-950/40 text-violet-200 hover:bg-violet-900/50 disabled:opacity-40"
              disabled={generationRunning || !hasManifest}
              onClick={() => run(`Regenerar ${selectedAlreadyDoneCount} imágenes`, () => generateSelected(true))}
            >
              Regenerar ya generadas ({selectedAlreadyDoneCount})
            </Btn>
          ) : null}
          <Btn
            type="button"
            className="border border-amber-500/50 bg-amber-950/40 text-amber-200 hover:bg-amber-900/50 disabled:opacity-40"
            disabled={generationRunning || !hasManifest || generatedCount === 0}
            onClick={() =>
              run(
                `Quitar marca de agua (${selectedGeneratedCount > 0 ? selectedGeneratedCount : generatedCount})`,
                () => removeGeminiWatermarks(),
              )
            }
          >
            {removingWatermark
              ? "Quitando marca de agua…"
              : `Quitar marca Gemini (${selectedGeneratedCount > 0 ? selectedGeneratedCount : generatedCount})`}
          </Btn>
          <Btn
            type="button"
            className="border border-rose-500/50 bg-rose-950/40 text-rose-200 hover:bg-rose-900/50 disabled:opacity-40"
            disabled={generationRunning || !hasManifest || selectedCount === 0}
            onClick={() => run(`Eliminar ${selectedCount} imágenes`, () => deleteSelectedImages())}
          >
            {deleting
              ? "Eliminando…"
              : selectedGeneratedCount > 0
                ? `Eliminar seleccionadas (${selectedGeneratedCount})`
                : `Eliminar seleccionadas (${selectedCount})`}
          </Btn>
          <Btn type="button" className="bg-white text-slate-900 hover:bg-slate-100 disabled:opacity-40"
            disabled={generationRunning || !hasManifest}
            onClick={() => run("Guardar selección de imágenes", saveManifest)}>
            Guardar selección
          </Btn>
        </div>
      </div>

      {hasManifest && manifest ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {manifest.images.slice().sort((a, b) => a.order - b.order).map((img) => (
            <ImageCard
              key={img.id}
              img={img}
              workApplied={workApplied}
              cacheBust={cacheBust}
              chunkAudio={chunkAudioFor(img)}
              onToggle={toggleImage}
              onPreview={setPreviewImg}
              geminiProcessing={geminiRunning && (geminiJob?.current_id === img.id || geminiJob?.current_order === img.order)}
            />
          ))}
        </div>
      ) : (
        <div className="rounded-xl border border-dashed border-slate-600 bg-slate-800/50 p-8 text-center text-sm text-slate-500">
          No hay manifest de imágenes. En <strong className="text-slate-300">Image Prompt Writer</strong>, pulsa{" "}
          <strong className="text-slate-300">Enviar a Images Generation</strong> para crear las miniaturas pendientes.
        </div>
      )}

      {previewImg && previewChunkAudio ? (
        <PromptModal img={previewImg} chunkAudio={previewChunkAudio} onClose={() => setPreviewImg(null)} />
      ) : null}
    </div>
  );
}
