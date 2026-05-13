import { useCallback, useEffect, useState } from "react";
import { Btn } from "../../../components/ui";
import type { Session } from "../../../types/session";

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
}: {
  session: Session | null;
  renderNoMusic: boolean;
  setRenderNoMusic: (v: boolean) => void;
  workApplied: string;
  renderStepState: StepState;
  renderStepDetail?: string;
  pipelineLastError?: string | null;
}) {
  const hasDraft = session?.draft_exists;
  const draftUrl = `/work-file?work=${encodeURIComponent(workApplied)}&name=draft.mp4`;
  const generationRunning = renderStepState === "running";
  const imgCount = session?.pipeline_images_count ?? 0;
  const [artifact, setArtifact] = useState<RenderDraftArtifact | null>(null);
  const [artifactLoading, setArtifactLoading] = useState(false);

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

  const stepError = renderStepState === "error";
  const errMsg = [pipelineLastError, renderStepDetail].map((x) => (x || "").trim()).filter(Boolean).join("\n\n");
  const showPipelineError = stepError && errMsg.length > 0;

  return (
    <div className="space-y-3">
      <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700">
        Monta <strong>draft.mp4</strong> con MoviePy: <code className="rounded bg-white px-1">narracion.wav</code> + imágenes en{" "}
        <code className="rounded bg-white px-1">pipeline/images/</code> (Ken Burns) si existen; si no, fondo sólido con el audio. Música opcional desde{" "}
        <code className="rounded bg-white px-1">musica_libre/</code>.
      </div>

      {generationRunning ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-950 space-y-1">
          <p className="font-semibold">Renderizando vídeo…</p>
          <p>
            MoviePy puede tardar varios minutos. El avance detallado (<code className="rounded bg-white/80 px-1">t: …%</code>) sale en la{" "}
            <strong>consola del backend</strong>; aquí el paso de la pipeline queda en «running».
          </p>
          {renderStepDetail ? <p className="text-amber-900/90">Detalle: {renderStepDetail}</p> : null}
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
                usa las <strong>{imgCount}</strong> imagen{imgCount === 1 ? "" : "es"} en <code className="rounded bg-white px-1">pipeline/images/</code> con Ken Burns repartiendo el tiempo; si no alcanza, repite planos.
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
