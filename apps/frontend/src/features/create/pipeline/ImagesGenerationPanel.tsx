import { useCallback, useEffect, useState } from "react";
import { Btn } from "../../../components/ui";
import { putJson } from "../../../services/api";
import type { RunFn } from "../types";
import { PipelineSection as Section } from "./PipelineSection";

type ImageEntry = {
  id: string; filename: string; act: string; order: number;
  timestamp_hint: string; duration_hint_s: number; role: string;
  scene_description_es: string; ai_prompt: string;
  status: "generated" | "pending" | "error" | string; selected: boolean;
};

type Manifest = {
  version: number; generated_at?: string; generator?: string;
  style?: string; total: number; selected_count: number; images: ImageEntry[];
};

const ACT_LABELS: Record<string, { label: string; color: string }> = {
  hook:  { label: "Hook",   color: "bg-violet-900/60 text-violet-300 border border-violet-500/30" },
  act2:  { label: "Acto 2", color: "bg-blue-900/60   text-blue-300   border border-blue-500/30"  },
  act3:  { label: "Acto 3", color: "bg-amber-900/60  text-amber-300  border border-amber-500/30" },
  act4:  { label: "Acto 4", color: "bg-emerald-900/60 text-emerald-300 border border-emerald-500/30" },
};

function ImageCard({ img, workApplied, onToggle, onPreview }: {
  img: ImageEntry; workApplied: string; onToggle: (id: string) => void; onPreview: (img: ImageEntry) => void;
}) {
  const imgUrl = `/api/pipeline/images-generation/image?work=${encodeURIComponent(workApplied)}&filename=${encodeURIComponent(img.filename)}`;
  const act = ACT_LABELS[img.act] ?? { label: img.act, color: "bg-slate-700 text-slate-300 border border-slate-500" };

  return (
    <div
      className={`group relative flex flex-col overflow-hidden rounded-xl border-2 transition-all cursor-pointer ${img.selected ? "border-indigo-500 shadow-md shadow-indigo-900/50" : "border-slate-600 hover:border-slate-500"}`}
      onClick={() => onToggle(img.id)}
    >
      <div className="relative aspect-video bg-slate-800 overflow-hidden">
        {img.status === "generated" ? (
          <img src={imgUrl} alt={img.scene_description_es} className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105" loading="lazy" />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-xs text-slate-500">Pendiente</div>
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
      <div className="flex flex-col gap-1 p-2 bg-slate-800">
        <div className="flex items-center gap-1 flex-wrap">
          <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-semibold ${act.color}`}>{act.label}</span>
          <span className="text-[10px] text-slate-500">{img.timestamp_hint}</span>
          <span className="text-[10px] text-slate-500">· {img.duration_hint_s}s</span>
        </div>
        <p className="text-xs text-slate-300 line-clamp-2 leading-tight">{img.scene_description_es}</p>
      </div>
    </div>
  );
}

function PromptModal({ img, onClose }: { img: ImageEntry; onClose: () => void }) {
  return (
    <div className="fixed inset-y-0 left-[280px] right-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={onClose}>
      <div className="relative max-w-2xl w-full rounded-2xl bg-white p-5 shadow-2xl space-y-3" onClick={(e) => e.stopPropagation()}>
        <button className="absolute right-4 top-4 text-slate-400 hover:text-slate-700" onClick={onClose}>✕</button>
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-slate-900">#{img.order} — {img.role}</span>
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-600">{img.act}</span>
        </div>
        <p className="text-sm text-slate-700">{img.scene_description_es}</p>
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
  const [previewImg, setPreviewImg] = useState<ImageEntry | null>(null);
  const generationRunning = imagesStepState === "running";

  const loadManifest = useCallback(async () => {
    const r = await fetch(`/api/pipeline/images-generation?work=${encodeURIComponent(workApplied)}`);
    if (!r.ok) return;
    const j = (await r.json()) as { exists?: boolean; manifest?: Manifest | null };
    if (j.exists && j.manifest) { setManifest(j.manifest); setHasManifest(true); }
    else { setManifest(null); setHasManifest(false); }
  }, [workApplied]);

  useEffect(() => { void loadManifest(); }, [loadManifest, imagesStepState, workApplied]);

  const toggleImage = (id: string) => {
    if (!manifest) return;
    const updated: Manifest = { ...manifest, images: manifest.images.map((img) => img.id === id ? { ...img, selected: !img.selected } : img) };
    updated.selected_count = updated.images.filter((i) => i.selected).length;
    setManifest(updated);
  };

  const selectAll = (val: boolean) => {
    if (!manifest) return;
    setManifest({ ...manifest, images: manifest.images.map((img) => ({ ...img, selected: val })), selected_count: val ? manifest.images.length : 0 });
  };

  const saveManifest = async () => {
    if (!manifest) return;
    await putJson("/api/pipeline/images-generation", { work: workApplied, manifest });
    await loadManifest();
    await refreshPipeline();
  };

  const selectedCount = manifest?.images.filter((i) => i.selected).length ?? 0;
  const totalCount = manifest?.images.length ?? 0;

  return (
    <div className="rounded-2xl bg-slate-900 p-4 space-y-4">

      {/* Info */}
      <div className="rounded-xl border border-slate-600 bg-slate-800 px-3 py-2 text-xs text-slate-400">
        <span className="font-semibold text-white">Images Generation</span> muestra las imágenes
        generadas por IA para el vídeo. Selecciona las que quieres usar en el montaje final. Cada imagen corresponde a una escena del guion con su{" "}
        <code className="rounded bg-slate-700 px-1">timestamp_hint</code> y{" "}
        <code className="rounded bg-slate-700 px-1">ai_prompt</code>. El resultado se guarda en{" "}
        <code className="rounded bg-slate-700 px-1">pipeline/images_generation.json</code>.
      </div>

      {generationRunning && (
        <div className="rounded-xl border border-amber-500/40 bg-amber-950/30 px-3 py-2 text-xs text-amber-300">
          Generando imágenes…
        </div>
      )}

      {/* Process info */}
      <Section id="images-process" title="Proceso De Generación" description="Motor, estilo y distribución de imágenes por acto.">
        <ul className="list-disc pl-4 space-y-0.5 text-[11px] text-slate-400">
          <li>Las imágenes se generan a partir de los <code className="rounded bg-slate-700 px-1">ai_prompt</code> del <strong className="text-slate-300">Image Prompt Writer</strong></li>
          <li>Estilo consistente: 35mm film, grano cinematográfico, iluminación ámbar y sombras profundas</li>
          <li>Una imagen por escena clave — hook (3), acto 2 (1), acto 3 por coste (2×5), acto 4 (2)</li>
          <li>Formato 16:9, sin texto — listo para Ken Burns + subtítulos en el montaje</li>
          <li>Selecciona o deselecciona imágenes antes de pasar al montaje de vídeo</li>
        </ul>
      </Section>

      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400">
            {hasManifest ? `${selectedCount} de ${totalCount} seleccionadas` : "Sin imágenes generadas"}
          </span>
          {hasManifest && (
            <>
              <Btn type="button" className="border border-slate-500 bg-slate-700 text-slate-200 hover:bg-slate-600 text-xs" onClick={() => selectAll(true)}>Seleccionar todas</Btn>
              <Btn type="button" className="border border-slate-500 bg-slate-700 text-slate-200 hover:bg-slate-600 text-xs" onClick={() => selectAll(false)}>Deseleccionar todas</Btn>
            </>
          )}
        </div>
        <div className="flex gap-2">
          <Btn type="button" className="border border-slate-600 bg-slate-800 text-slate-200 hover:bg-slate-700" onClick={() => void loadManifest()}>Recargar</Btn>
          <Btn type="button" className="bg-white text-slate-900 hover:bg-slate-100 disabled:opacity-40"
            disabled={generationRunning || !hasManifest}
            onClick={() => run("Guardar selección de imágenes", saveManifest)}>
            Guardar selección
          </Btn>
        </div>
      </div>

      {/* Image grid */}
      {hasManifest && manifest ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {manifest.images.slice().sort((a, b) => a.order - b.order).map((img) => (
            <ImageCard key={img.id} img={img} workApplied={workApplied} onToggle={toggleImage} onPreview={setPreviewImg} />
          ))}
        </div>
      ) : (
        <div className="rounded-xl border border-dashed border-slate-600 bg-slate-800/50 p-8 text-center text-sm text-slate-500">
          No hay imágenes generadas. Ejecuta «Start step» para generarlas, o súbelas manualmente a{" "}
          <code className="rounded bg-slate-700 px-1">pipeline/images/</code> y recarga.
        </div>
      )}

      {previewImg && <PromptModal img={previewImg} onClose={() => setPreviewImg(null)} />}
    </div>
  );
}
