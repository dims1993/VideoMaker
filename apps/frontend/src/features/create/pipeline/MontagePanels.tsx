import { useCallback, useEffect, useState } from "react";
import { Btn } from "../../../components/ui";
import { postJson } from "../../../services/api";
import type { Session } from "../../../types/session";
import { PipelineStepConfirmBar } from "./PipelineStepConfirmBar";
import type { RunFn } from "../types";
import { DraftSlideshowPreview } from "./DraftSlideshowPreview";

type StepState = "idle" | "running" | "done" | "error";

export type RenderDraftArtifact = {
  version?: number;
  completed_at?: string;
  visual_branch?: string;
  images_manifest_preferred?: boolean;
  images_resolved_count?: number;
  stock_video_count?: number;
  narration_duration_s?: number;
  output_bytes?: number;
  frame_width?: number;
  frame_height?: number;
  music_track?: string | null;
  pick_music_from_project?: boolean;
  render_no_music?: boolean;
  output_file?: string;
};

function formatBytes(n: number | undefined): string {
  if (n === undefined || Number.isNaN(n) || n <= 0) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(2)} MB`;
}

function formatDuration(sec: number | undefined): string {
  if (sec === undefined || Number.isNaN(sec) || sec <= 0) return "—";
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return m > 0 ? `${m} min ${s} s` : `${s} s`;
}

type RenderProgressPayload = {
  kind?: string;
  phase?: string;
  current?: number;
  total?: number;
  percent?: number;
  message?: string;
  updated_at?: string;
};

function formatElapsed(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return m > 0 ? `${m}:${String(s).padStart(2, "0")}` : `${s}s`;
}

function phaseLabel(phase: string | undefined): string {
  switch (phase) {
    case "segment":
      return "Generando planos";
    case "concat":
      return "Uniendo secuencia";
    case "encode":
      return "Codificando MP4";
    case "done":
      return "Finalizado";
    default:
      return "En curso";
  }
}

function branchLabel(branch: string | undefined): string {
  switch (branch) {
    case "images":
      return "Imágenes (Ken Burns)";
    case "stock":
      return "Vídeos en stock/ (legacy)";
    case "narration_only":
      return "Solo narración (fondo sólido)";
    default:
      return branch || "—";
  }
}

export function RenderDraftPanel({
  session,
  renderNoMusic,
  setRenderNoMusic,
  workApplied,
  renderStepState,
  renderStepDetail,
  pipelineLastError,
  run,
  onRefreshSession,
  refreshPipeline,
}: {
  session: Session | null;
  renderNoMusic: boolean;
  setRenderNoMusic: (v: boolean) => void;
  workApplied: string;
  renderStepState: StepState;
  renderStepDetail?: string;
  pipelineLastError?: string | null;
  run: RunFn;
  onRefreshSession?: () => Promise<void>;
  refreshPipeline?: () => Promise<void>;
}) {
  const hasDraft = session?.draft_exists;
  const previewUrlBase = `/work-file?work=${encodeURIComponent(workApplied)}&name=preview_draft.mp4`;
  const generationRunning = renderStepState === "running";
  const [hasPreviewMp4, setHasPreviewMp4] = useState(false);
  const [previewSegments, setPreviewSegments] = useState(12);
  const [previewMp4Busy, setPreviewMp4Busy] = useState(false);
  const [previewMp4Msg, setPreviewMp4Msg] = useState<string | null>(null);
  const [previewProgress, setPreviewProgress] = useState<RenderProgressPayload | null>(null);
  const [previewElapsedSec, setPreviewElapsedSec] = useState(0);
  const [previewUrlBust, setPreviewUrlBust] = useState(0);
  const [draftProgress, setDraftProgress] = useState<RenderProgressPayload | null>(null);
  const [draftElapsedSec, setDraftElapsedSec] = useState(0);
  const imgCount = session?.pipeline_images_count ?? 0;
  const [artifact, setArtifact] = useState<RenderDraftArtifact | null>(null);
  const [artifactLoading, setArtifactLoading] = useState(false);

  const draftCacheBust =
    artifact?.completed_at?.trim() ||
    (renderStepState === "done" ? String(Date.now()) : "");
  const draftUrl = `/work-file?work=${encodeURIComponent(workApplied)}&name=draft.mp4${
    draftCacheBust ? `&t=${encodeURIComponent(draftCacheBust)}` : ""
  }`;

  const loadArtifact = useCallback(async () => {
    setArtifactLoading(true);
    try {
      const r = await fetch(`/api/pipeline/render-draft?work=${encodeURIComponent(workApplied)}`);
      if (!r.ok) {
        setArtifact(null);
        return;
      }
      const j = (await r.json()) as { exists?: boolean; artifact?: RenderDraftArtifact | null };
      if (j.exists && j.artifact && typeof j.artifact === "object") {
        setArtifact(j.artifact);
      } else {
        setArtifact(null);
      }
    } catch {
      setArtifact(null);
    } finally {
      setArtifactLoading(false);
    }
  }, [workApplied]);

  useEffect(() => {
    void loadArtifact();
  }, [loadArtifact, renderStepState, workApplied]);

  const checkPreviewMp4 = useCallback(async () => {
    try {
      const r = await fetch(
        `/work-file?work=${encodeURIComponent(workApplied)}&name=preview_draft.mp4`,
        { method: "HEAD" },
      );
      setHasPreviewMp4(r.ok);
      return r.ok;
    } catch {
      setHasPreviewMp4(false);
      return false;
    }
  }, [workApplied]);

  useEffect(() => {
    void checkPreviewMp4();
  }, [checkPreviewMp4, renderStepState, workApplied]);

  const startFastPreviewMp4 = useCallback(async () => {
    setPreviewMp4Busy(true);
    setPreviewMp4Msg(null);
    setPreviewProgress({ phase: "segment", current: 0, total: previewSegments, percent: 2, message: "Iniciando…" });
    setPreviewElapsedSec(0);
    try {
      await postJson<{ started?: boolean }>("/api/render-preview", {
        work: workApplied,
        no_music: renderNoMusic,
        max_segments: previewSegments,
        max_duration_s: 120,
      });
    } catch (e) {
      setPreviewMp4Msg(e instanceof Error ? e.message : String(e));
      setPreviewMp4Busy(false);
      setPreviewProgress(null);
    }
  }, [workApplied, renderNoMusic, previewSegments]);

  useEffect(() => {
    if (!previewMp4Busy) return;

    const startedAt = Date.now();
    let cancelled = false;

    const poll = async () => {
      if (cancelled) return;
      setPreviewElapsedSec(Math.floor((Date.now() - startedAt) / 1000));

      try {
        const pr = await fetch(
          `/api/pipeline/render-progress?work=${encodeURIComponent(workApplied)}`,
        );
        if (pr.ok) {
          const j = (await pr.json()) as { exists?: boolean; progress?: RenderProgressPayload | null };
          if (j.exists && j.progress) {
            setPreviewProgress(j.progress);
          }
        }
      } catch {
        /* ignore */
      }

      await onRefreshSession?.();
      await refreshPipeline?.();

      if (await checkPreviewMp4()) {
        setPreviewUrlBust(Date.now());
        setPreviewMp4Msg("Preview MP4 listo.");
        setPreviewProgress({ phase: "done", percent: 100, message: "Completado" });
        setPreviewMp4Busy(false);
        return;
      }

      try {
        const sr = await fetch(`/api/session?work=${encodeURIComponent(workApplied)}`);
        if (sr.ok) {
          const data = (await sr.json()) as {
            status?: { state?: string; step?: string; detail?: string };
          };
          const st = data.status;
          if (st?.state === "error" && st?.step === "render") {
            setPreviewMp4Msg(st.detail || "Error al generar preview MP4");
            setPreviewMp4Busy(false);
            setPreviewProgress(null);
            return;
          }
          if (st?.state === "done" && (st?.detail ?? "").includes("Preview MP4 listo")) {
            if (await checkPreviewMp4()) {
              setPreviewUrlBust(Date.now());
              setPreviewMp4Msg("Preview MP4 listo.");
              setPreviewProgress({ phase: "done", percent: 100, message: "Completado" });
              setPreviewMp4Busy(false);
            }
          }
        }
      } catch {
        /* ignore */
      }
    };

    const interval = window.setInterval(() => void poll(), 1200);
    void poll();

    const timeout = window.setTimeout(() => {
      if (!cancelled) {
        setPreviewMp4Msg("Tiempo de espera agotado (10 min). Revisa la consola del backend.");
        setPreviewMp4Busy(false);
        setPreviewProgress(null);
      }
    }, 10 * 60 * 1000);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
      window.clearTimeout(timeout);
    };
  }, [
    previewMp4Busy,
    workApplied,
    onRefreshSession,
    refreshPipeline,
    checkPreviewMp4,
  ]);

  useEffect(() => {
    if (!generationRunning || previewMp4Busy) {
      setDraftProgress(null);
      setDraftElapsedSec(0);
      return;
    }

    const startedAt = Date.now();
    let cancelled = false;

    const poll = async () => {
      if (cancelled) return;
      setDraftElapsedSec(Math.floor((Date.now() - startedAt) / 1000));
      try {
        const pr = await fetch(
          `/api/pipeline/render-progress?work=${encodeURIComponent(workApplied)}`,
        );
        if (pr.ok) {
          const j = (await pr.json()) as { exists?: boolean; progress?: RenderProgressPayload | null };
          if (j.exists && j.progress) {
            setDraftProgress(j.progress);
          }
        }
      } catch {
        /* ignore */
      }
      await onRefreshSession?.();
      await refreshPipeline?.();
      if (renderStepState !== "running") {
        void loadArtifact();
      }
    };

    const interval = window.setInterval(() => void poll(), 1500);
    void poll();
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [
    generationRunning,
    previewMp4Busy,
    workApplied,
    onRefreshSession,
    refreshPipeline,
    renderStepState,
    loadArtifact,
  ]);

  const stepError = renderStepState === "error";
  const previewBusy = previewMp4Busy;
  const renderActivelyProgressing =
    generationRunning ||
    (draftProgress?.phase != null && draftProgress.phase !== "done");
  const errParts = [pipelineLastError, renderStepDetail]
    .map((x) => (x || "").trim())
    .filter(Boolean);
  const errMsg = [...new Set(errParts)].join("\n\n");
  const showPipelineError = stepError && errMsg.length > 0 && !renderActivelyProgressing;

  return (
    <div className="space-y-3">
      <PipelineStepConfirmBar
        stepId="render_draft"
        stepLabel="Render draft"
        workApplied={workApplied}
        stepState={renderStepState}
        run={run}
        onAfterRun={refreshPipeline}
      />
      <DraftSlideshowPreview workApplied={workApplied} />

      <div className="rounded-xl border border-violet-100 bg-violet-50/60 px-3 py-2 text-xs text-violet-950 space-y-2">
        <p className="font-semibold">Preview MP4 rápido (opcional)</p>
        <p className="text-violet-800/90">
          Codifica los primeros planos en <code className="rounded bg-white/80 px-1">preview_draft.mp4</code> (720p,
          con el mismo Ken Burns y sincronía que el draft; codificación ultrafast). Tarda menos que el vídeo completo.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <label className="text-violet-900">
            Planos máx.
            <input
              type="number"
              min={1}
              max={40}
              value={previewSegments}
              onChange={(e) => setPreviewSegments(Math.min(40, Math.max(1, parseInt(e.target.value, 10) || 12)))}
              disabled={previewBusy || generationRunning}
              className="ml-1 w-14 rounded border border-violet-200 px-1.5 py-0.5"
            />
          </label>
          <Btn
            type="button"
            className="bg-violet-600 text-white hover:bg-violet-500 text-xs disabled:opacity-40"
            disabled={previewBusy || generationRunning}
            onClick={() => void startFastPreviewMp4()}
          >
            {previewMp4Busy ? "Generando preview…" : "Generar preview MP4"}
          </Btn>
        </div>
        {previewMp4Busy ? (
          <div className="rounded-lg border border-violet-300/60 bg-white/70 px-3 py-2.5 space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-violet-950">
              <span className="font-semibold">{phaseLabel(previewProgress?.phase)}</span>
              <span className="tabular-nums text-violet-800">
                {previewProgress?.phase === "segment" && (previewProgress.total ?? 0) > 0
                  ? `Plano ${previewProgress.current ?? 0} / ${previewProgress.total}`
                  : null}
                {previewProgress?.phase === "segment" && (previewProgress.total ?? 0) > 0 ? " · " : ""}
                {formatElapsed(previewElapsedSec)} transcurrido
              </span>
            </div>
            <div className="h-2.5 w-full overflow-hidden rounded-full bg-violet-200/80">
              <div
                className="h-full rounded-full bg-violet-600 transition-[width] duration-500 ease-out"
                style={{ width: `${Math.max(4, previewProgress?.percent ?? 5)}%` }}
              />
            </div>
            <p className="text-[11px] text-violet-900/90 leading-snug">
              {previewProgress?.message ??
                (renderStepDetail?.includes("Preview MP4") ? renderStepDetail : null) ??
                "Preparando preview MP4…"}
            </p>
            <p className="text-[10px] text-violet-700/80">
              Ken Burns + sync por bloque · 720p · no cierres esta pestaña. La barra avanza por cada plano y luego en la codificación.
            </p>
          </div>
        ) : null}
        {previewMp4Msg ? (
          <p
            className={`text-[11px] leading-snug ${
              previewMp4Msg.includes("listo")
                ? "text-emerald-800"
                : previewMp4Msg.includes("Error") || previewMp4Msg.includes("agotado")
                  ? "text-rose-800"
                  : "text-violet-900"
            }`}
          >
            {previewMp4Msg}
          </p>
        ) : null}
        {hasPreviewMp4 ? (
          <div className="overflow-hidden rounded-lg border border-violet-200 bg-black">
            <video
              key={previewUrlBust}
              className="max-h-[280px] w-full object-contain"
              src={`${previewUrlBase}&t=${previewUrlBust}`}
              controls
              playsInline
              preload="metadata"
            />
          </div>
        ) : null}
      </div>

      <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700">
        Monta <strong>draft.mp4</strong> con MoviePy: <code className="rounded bg-white px-1">narracion.wav</code> + imágenes en{" "}
        <code className="rounded bg-white px-1">pipeline/images/</code> (Ken Burns) si existen; si no, fondo sólido con el audio. Música opcional desde{" "}
        <code className="rounded bg-white px-1">musica_libre/</code>.
      </div>

      {generationRunning && !previewMp4Busy ? (
        <div className="rounded-xl border border-amber-300/70 bg-white/80 px-3 py-2.5 text-xs text-amber-950 space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-semibold">{phaseLabel(draftProgress?.phase ?? "segment")} · draft.mp4</p>
            <span className="tabular-nums text-amber-800">
              {draftProgress?.phase === "segment" && (draftProgress.total ?? 0) > 0
                ? `Plano ${draftProgress.current ?? 0} / ${draftProgress.total}`
                : null}
              {draftProgress?.phase === "segment" && (draftProgress.total ?? 0) > 0 ? " · " : ""}
              {formatElapsed(draftElapsedSec)} transcurrido
            </span>
          </div>
          <div className="h-2.5 w-full overflow-hidden rounded-full bg-amber-200/80">
            <div
              className="h-full rounded-full bg-amber-600 transition-[width] duration-500 ease-out"
              style={{ width: `${Math.max(4, draftProgress?.percent ?? 8)}%` }}
            />
          </div>
          <p className="text-[11px] text-amber-900/90 leading-snug">
            {draftProgress?.message ??
              (renderStepDetail?.includes("Render draft") ? renderStepDetail : null) ??
              "Renderizando vídeo completo (92 planos puede tardar 30–60+ min)…"}
          </p>
          <p className="text-[10px] text-amber-800/80">
            No cierres la pestaña. Si el servidor se reinició con <code className="rounded bg-white/80 px-1">--reload</code> el paso puede quedar en «running» aunque el MP4 ya exista — recarga la página para sincronizar el estado.
          </p>
        </div>
      ) : null}

      {showPipelineError ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-900">
          <p className="font-semibold">Error en el paso</p>
          <p className="mt-1 whitespace-pre-wrap">{errMsg}</p>
        </div>
      ) : null}

      <div className="rounded-xl border border-indigo-100 bg-indigo-50/60 px-3 py-2 text-xs text-indigo-900 space-y-1">
        <p className="font-semibold">Proceso de render (MoviePy)</p>
        <ol className="list-decimal pl-4 space-y-1 text-indigo-800">
          <li>
            <strong>Audio guía</strong> — lee <code className="rounded bg-white px-1">narracion.wav</code> y fija la duración del vídeo.
          </li>
          <li>
            <strong>Capa visual</strong> — si hay vídeos en <code className="rounded bg-white px-1">stock/</code> (legacy), monta cortes 4–6s; si no,{" "}
            {imgCount > 0 ? (
              <>
                usa las <strong>{imgCount}</strong> imagen{imgCount === 1 ? "" : "es"} en <code className="rounded bg-white px-1">pipeline/images/</code> con zoom Ken Burns suave (recorte PIL; en <code className="rounded bg-white px-1">.env</code>{" "}
                <code className="rounded bg-white px-1">RENDER_KEN_BURNS=0</code> = plano fijo).
              </>
            ) : (
              <>
                no hay imágenes en <code className="rounded bg-white px-1">pipeline/images/</code>: se usa <strong>fondo sólido</strong> 16:9 con el audio.
              </>
            )}
          </li>
          <li>
            <strong>Mezcla sonora</strong> — voz + música en bucle y fade (salvo «Sin música de fondo» y si hay pistas en{" "}
            <code className="rounded bg-white px-1">musica_libre/</code>).
          </li>
          <li>
            <strong>Salida</strong> — codifica <code className="rounded bg-white px-1">libx264</code> + AAC → raíz de la sesión como{" "}
            <code className="rounded bg-white px-1">draft.mp4</code>.
          </li>
        </ol>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-800">
          <input type="checkbox" checked={renderNoMusic} onChange={(e) => setRenderNoMusic(e.target.checked)} className="rounded border-slate-300" />
          Sin música de fondo
        </label>
        <Btn
          type="button"
          className="bg-white text-slate-900 ring-1 ring-slate-200 hover:bg-slate-50 text-xs"
          disabled={artifactLoading}
          onClick={() => void loadArtifact()}
        >
          {artifactLoading ? "Cargando…" : "Recargar resumen"}
        </Btn>
      </div>

      {artifact && (renderStepState === "done" || hasDraft) ? (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50/80 px-3 py-2 text-xs text-emerald-950 space-y-1">
          <p className="font-semibold text-emerald-900">Último render</p>
          <ul className="list-none space-y-0.5 pl-0 text-emerald-900">
            <li>
              <strong>Modo:</strong> {branchLabel(artifact.visual_branch)}
              {artifact.images_manifest_preferred ? " · prioridad manifest imágenes" : null}
            </li>
            <li>
              <strong>Narración:</strong> {formatDuration(artifact.narration_duration_s)} · <strong>Tamaño MP4:</strong>{" "}
              {formatBytes(artifact.output_bytes)}
            </li>
            <li>
              <strong>Resolución:</strong>{" "}
              {artifact.frame_width && artifact.frame_height ? `${artifact.frame_width}×${artifact.frame_height}` : "—"}
            </li>
            <li>
              <strong>Imágenes resueltas:</strong> {artifact.images_resolved_count ?? 0} · <strong>Clips stock:</strong>{" "}
              {artifact.stock_video_count ?? 0}
            </li>
            <li>
              <strong>Música:</strong>{" "}
              {artifact.render_no_music
                ? "desactivada (opción)"
                : artifact.music_track
                  ? `sí (${artifact.music_track})`
                  : artifact.pick_music_from_project
                    ? "no (sin pistas o no encontrada)"
                    : "no"}
            </li>
            {artifact.completed_at ? (
              <li className="text-emerald-800/90">
                <strong>Completado:</strong> {artifact.completed_at}
                {artifact.output_bytes ? (
                  <> · <strong>{formatBytes(artifact.output_bytes)}</strong> en disco</>
                ) : null}
              </li>
            ) : null}
          </ul>
          <p className="text-[10px] text-emerald-800/80">
            Datos de <code className="rounded bg-white/60 px-1">pipeline/render_draft.json</code>. Vuelve a ejecutar el paso para actualizarlos.
          </p>
        </div>
      ) : null}

      {!artifact && hasDraft && renderStepState !== "running" ? (
        <p className="text-[11px] text-slate-500">
          Hay <code className="rounded bg-slate-100 px-1">draft.mp4</code> pero no hay resumen en disco (render anterior a esta versión). Ejecuta de nuevo el paso para generar{" "}
          <code className="rounded bg-slate-100 px-1">render_draft.json</code>.
        </p>
      ) : null}

      {hasDraft ? (
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <Btn
              type="button"
              className="bg-emerald-600 text-white hover:bg-emerald-500"
              onClick={() => window.open(draftUrl, "_blank", "noopener,noreferrer")}
            >
              Abrir / descargar draft.mp4
            </Btn>
            <span className="text-xs text-slate-500">{session?.draft_path}</span>
          </div>
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-black">
            <video
              key={draftUrl}
              className="max-h-[360px] w-full object-contain"
              src={draftUrl}
              title={artifact?.completed_at ? `draft.mp4 · ${artifact.completed_at}` : "draft.mp4"}
              controls
              playsInline
              preload="metadata"
            />
          </div>
        </div>
      ) : (
        <p className="text-xs text-amber-800">Aún no hay draft en esta sesión. Ejecuta el paso cuando tengas narración (y opcionalmente imágenes).</p>
      )}
    </div>
  );
}
