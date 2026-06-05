import { useCallback, useEffect, useState } from "react";
import { Btn } from "../../../components/ui";
import { postJson } from "../../../services/api";
import type { RunFn } from "../types";

type ThumbFile = {
  index: number;
  id: string;
  filename: string;
  idea: string;
  exists: boolean;
  bytes: number;
  status?: string;
  error?: string | null;
};

type ThumbGenJob = {
  state?: string;
  current?: number;
  total?: number;
  current_id?: string;
  detail?: string;
  result?: {
    generated?: number;
    failed?: number;
    mock?: boolean;
    errors?: { id?: string; detail?: string }[];
  };
};

type ThumbnailsStatus = {
  ideas: string[];
  hook_text: string | null;
  idea_count: number;
  files: ThumbFile[];
  manifest_thumbnail_rows: number;
  ready_to_generate: boolean;
  job?: ThumbGenJob;
};

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export function MetadataThumbnailsSection({
  run,
  workApplied,
  generationRunning,
  artifactExists,
  refreshPipeline,
}: {
  run: RunFn;
  workApplied: string;
  generationRunning: boolean;
  artifactExists: boolean;
  refreshPipeline: () => Promise<void>;
}) {
  const [status, setStatus] = useState<ThumbnailsStatus | null>(null);
  const [includeVisualStyle, setIncludeVisualStyle] = useState(true);
  const [busy, setBusy] = useState(false);
  const [thumbGenRunning, setThumbGenRunning] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const loadStatus = useCallback(async () => {
    try {
      const r = await fetch(
        `/api/pipeline/metadata/thumbnail-generation-job?work=${encodeURIComponent(workApplied)}`,
      );
      if (!r.ok) return;
      const j = (await r.json()) as ThumbnailsStatus;
      setStatus({
        ideas: j.ideas ?? [],
        hook_text: j.hook_text ?? null,
        idea_count: j.idea_count ?? 0,
        files: j.files ?? [],
        manifest_thumbnail_rows: j.manifest_thumbnail_rows ?? 0,
        ready_to_generate: Boolean(j.ready_to_generate),
        job: j.job,
      });
      setThumbGenRunning(j.job?.state === "running");
    } catch {
      /* ignore */
    }
  }, [workApplied]);

  const formatJobResult = (job: ThumbGenJob | undefined) => {
    const res = job?.result;
    if (!res) return job?.detail ?? "Completado.";
    const errLines = (res.errors ?? [])
      .map((e) => `${e.id ?? "?"}: ${e.detail ?? "error"}`)
      .filter(Boolean);
    let text =
      `Generación OpenAI${res.mock ? " (mock)" : ""}: ${res.generated ?? 0} OK` +
      (res.failed ? `, ${res.failed} error(es).` : ".");
    if (errLines.length) text += " " + errLines.join(" · ");
    return text;
  };

  const pollThumbnailJob = useCallback(async () => {
    const deadline = Date.now() + 15 * 60 * 1000;
    while (Date.now() < deadline) {
      const r = await fetch(
        `/api/pipeline/metadata/thumbnail-generation-job?work=${encodeURIComponent(workApplied)}`,
      );
      if (!r.ok) throw new Error("No se pudo leer el progreso de miniaturas.");
      const j = (await r.json()) as ThumbnailsStatus;
      const job = j.job ?? {};
      setStatus({
        ideas: j.ideas ?? [],
        hook_text: j.hook_text ?? null,
        idea_count: j.idea_count ?? 0,
        files: j.files ?? [],
        manifest_thumbnail_rows: j.manifest_thumbnail_rows ?? 0,
        ready_to_generate: Boolean(j.ready_to_generate),
        job,
      });
      if (job.detail) setMsg(job.detail);
      if (job.state === "done") return formatJobResult(job);
      if (job.state === "error") {
        throw new Error(job.detail?.trim() || "Error generando miniaturas.");
      }
      if (job.state !== "running") break;
      await sleep(2000);
    }
    throw new Error(
      "Tiempo de espera agotado (15 min). Revisa el terminal del backend o vuelve a intentar.",
    );
  }, [workApplied]);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus, artifactExists]);

  // Si recargas la página mientras el backend sigue generando, reanuda el polling.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const r = await fetch(
        `/api/pipeline/metadata/thumbnail-generation-job?work=${encodeURIComponent(workApplied)}`,
      );
      if (!r.ok || cancelled) return;
      const j = (await r.json()) as ThumbnailsStatus;
      if (j.job?.state !== "running") return;
      setThumbGenRunning(true);
      setMsg(j.job.detail ?? "Reanudando seguimiento de generación…");
      try {
        const finalMsg = await pollThumbnailJob();
        if (!cancelled) {
          setMsg(finalMsg);
          await refreshPipeline();
        }
      } catch (e) {
        if (!cancelled) setMsg(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) {
          setThumbGenRunning(false);
          await loadStatus();
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [workApplied, pollThumbnailJob, refreshPipeline, loadStatus]);

  const handlePrepare = () =>
    run("Preparar miniaturas desde metadata", async () => {
      setBusy(true);
      setMsg(null);
      try {
        const res = await postJson<{
          push?: { count?: number; thumbnail_ids?: string[] };
          manifest?: { thumbnail_count?: number; pending?: number };
        }>("/api/pipeline/metadata/prepare-thumbnails", {
          work: workApplied,
          include_avatar: includeVisualStyle,
          merge: true,
        });
        const n = res.push?.count ?? res.manifest?.thumbnail_count ?? 0;
        setMsg(
          `Listo: ${n} prompt(s) de miniatura fusionados en image_prompts.json. ` +
            `Los ${res.manifest?.scene_rows_preserved ?? "92"} planos de escena no se tocaron.`,
        );
        await loadStatus();
        await refreshPipeline();
      } catch (e) {
        setMsg(e instanceof Error ? e.message : String(e));
      } finally {
        setBusy(false);
      }
    });

  const handleGenerate = async () => {
    if (thumbGenRunning) return;
    setThumbGenRunning(true);
    setMsg("Encolando generación con OpenAI… (1–3 min por miniatura)");
    try {
      const start = await postJson<{
        queued?: boolean;
        already_running?: boolean;
        detail?: string;
      }>("/api/pipeline/metadata/generate-thumbnails", {
        work: workApplied,
        regenerate: false,
      });
      if (start.detail) setMsg(start.detail);
      const finalMsg = await pollThumbnailJob();
      setMsg(finalMsg);
      await refreshPipeline();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setThumbGenRunning(false);
      await loadStatus();
    }
  };

  const ideas = status?.ideas ?? [];
  const disabled = generationRunning || busy || thumbGenRunning || !artifactExists;
  const job = status?.job;

  return (
    <div className="overflow-hidden rounded-xl border border-amber-200/80 bg-amber-50/40 shadow-sm">
      <div className="border-b border-amber-100 bg-amber-50/80 px-4 py-3">
        <h3 className="text-sm font-semibold text-amber-950">Miniaturas (YouTube)</h3>
        <p className="mt-1 text-xs text-amber-900/85 leading-snug">
          Usa <code className="rounded bg-white/70 px-1">editorial.thumbnail_ideas</code> y{" "}
          <code className="rounded bg-white/70 px-1">marketing.thumbnail_hook_text</code>. El estilo
          visual sale de <strong>Image Prompt Writer → Modo avatar</strong>. Las PNG se generan con{" "}
          <strong>OpenAI Images API</strong> (<code className="rounded bg-white/60 px-1">OPENAI_API_KEY</code>
          , modelo <code className="rounded bg-white/60 px-1">OPENAI_IMAGE_MODEL</code>). Los planos del vídeo siguen
          en Images Generation (Google/Gemini).
        </p>
      </div>

      <div className="space-y-3 p-4">
        {!artifactExists ? (
          <p className="text-xs text-amber-800">Genera o guarda metadata.json primero.</p>
        ) : ideas.length === 0 ? (
          <p className="text-xs text-amber-800">
            No hay <strong>thumbnail_ideas</strong> en el JSON. Añade 2–4 ideas en{" "}
            <code className="rounded bg-white/60 px-1">editorial</code> o vuelve a generar
            metadatos.
          </p>
        ) : (
          <ul className="space-y-2 text-xs text-amber-950">
            {status?.hook_text ? (
              <li className="rounded-lg border border-amber-200/60 bg-white/60 px-2.5 py-2">
                <span className="font-semibold uppercase tracking-wide text-amber-800">
                  Texto en miniatura
                </span>
                <p className="mt-0.5 font-medium">{status.hook_text}</p>
              </li>
            ) : null}
            {ideas.map((idea, i) => {
              const file = status?.files?.find((f) => f.index === i);
              return (
                <li
                  key={i}
                  className="rounded-lg border border-amber-100 bg-white/50 px-2.5 py-2"
                >
                  <div className="flex flex-wrap items-center justify-between gap-1">
                    <span className="font-mono text-[10px] text-amber-700">#{i + 1}</span>
                    {file?.exists ? (
                      <span className="text-[10px] font-medium text-emerald-700">
                        PNG listo · {file.filename}
                      </span>
                    ) : file?.status === "generating" ? (
                      <span className="text-[10px] font-medium text-sky-700">Generando…</span>
                    ) : file?.status === "error" ? (
                      <span className="text-[10px] font-medium text-rose-700">Error al generar</span>
                    ) : status?.ready_to_generate ? (
                      <span className="text-[10px] text-amber-700">Pendiente de generar</span>
                    ) : null}
                  </div>
                  <p className="mt-1 leading-snug">{idea}</p>
                  {file?.error ? (
                    <p className="mt-1 rounded border border-rose-200 bg-rose-50/80 px-2 py-1.5 text-[10px] leading-snug text-rose-900">
                      {file.error}
                    </p>
                  ) : null}
                  {file?.exists ? (
                    <img
                      src={`/api/pipeline/images-generation/image?work=${encodeURIComponent(workApplied)}&filename=${encodeURIComponent(file.filename)}&t=${file.bytes}`}
                      alt={`Miniatura ${i + 1}`}
                      className="mt-2 max-h-28 rounded border border-amber-100 object-contain"
                    />
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}

        <label className="flex cursor-pointer items-center gap-2 text-xs text-amber-950">
          <input
            type="checkbox"
            checked={includeVisualStyle}
            disabled={disabled}
            onChange={(e) => setIncludeVisualStyle(e.target.checked)}
            className="rounded border-amber-300 text-amber-600 focus:ring-amber-500"
          />
          Aplicar estilo visual de Image Prompt Writer (sección «Estilo visual y avatar»)
        </label>
        <p className="text-[10px] text-amber-800/90 -mt-1">
          Protagonista, expresiones, avoid y estilo base guardados ahí (mismo JSON que Scene Editor).
        </p>

        <div className="flex flex-wrap gap-2">
          <Btn
            type="button"
            className="bg-amber-600 text-white hover:bg-amber-500 disabled:opacity-40 text-xs"
            disabled={disabled || ideas.length === 0}
            onClick={() => void handlePrepare()}
          >
            {busy ? "Procesando…" : "1. Preparar miniaturas"}
          </Btn>
          <Btn
            type="button"
            className="border border-amber-400 bg-white text-amber-900 hover:bg-amber-50 disabled:opacity-40 text-xs"
            disabled={disabled || ideas.length === 0}
            onClick={() => void handleGenerate()}
          >
            {thumbGenRunning ? "Generando miniaturas…" : "2. Generar PNG (OpenAI)"}
          </Btn>
        </div>

        {thumbGenRunning && job?.state === "running" ? (
          <p className="rounded-lg border border-sky-200 bg-sky-50/90 px-2.5 py-2 text-[11px] leading-snug text-sky-900">
            <strong>En curso</strong> — no está colgado: OpenAI tarda bastante por imagen.
            {job.total ? (
              <>
                {" "}
                Progreso: {job.current ?? 0}/{job.total}
                {job.current_id ? ` (${job.current_id})` : ""}.
              </>
            ) : null}
            {job.detail ? <> {job.detail}</> : null}
          </p>
        ) : null}

        {status?.manifest_thumbnail_rows ? (
          <p className="text-[10px] text-amber-800/90">
            Manifest: {status.manifest_thumbnail_rows} fila(s) thumbnail · también en Images
            Generation.
          </p>
        ) : null}

        {msg ? (
          <p
            className={`text-[11px] leading-snug ${msg.includes("error") || msg.includes("Error") || msg.includes("Falta") || msg.includes("agotados") || msg.includes("Créditos") ? "text-rose-800" : "text-emerald-800"}`}
          >
            {msg}
          </p>
        ) : null}
      </div>
    </div>
  );
}
