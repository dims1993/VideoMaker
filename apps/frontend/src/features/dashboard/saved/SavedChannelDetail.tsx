import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import { TranscriptsSessionPanel } from "../../analyze/TranscriptsSessionPanel";
import { Btn, InfoTip, Input, Label, Select, StatusBadge } from "../../../components/ui";
import type { ChannelVideoItem, SavedChannelItem } from "../../../types";
import type { RunFn } from "../../../types/run";

type TaskOrStatus = { state: string; detail: string } | null;

type OpportunityGrade = "bajo" | "medio" | "alto" | "perla" | "sin_datos";

/** Orden de la lista: primer criterio en el array gana; cada columna es descendente (mayor → menor). */
type VideoSortColumn =
  | "title"
  | "published"
  | "duration"
  | "views"
  | "likes"
  | "comments"
  | "views_per_day"
  | "vph"
  | "engagement"
  | "like_rate"
  | "comment_rate"
  | "engagement_per_sub"
  | "outlier";

const SORT_COLUMN_LABEL: Record<VideoSortColumn, string> = {
  title: "Vídeo",
  published: "Publicado",
  duration: "Duración",
  views: "Views",
  likes: "Likes",
  comments: "Com",
  views_per_day: "V/D",
  vph: "VPH",
  engagement: "Eng",
  like_rate: "Like%",
  comment_rate: "Com%",
  engagement_per_sub: "Eng/Sub",
  outlier: "Outlier",
};

/** Ratio views / mediana del canal (>1 = por encima de la mediana). Requiere mediana > 0. */
function viewsVsChannelMedian(v: ChannelVideoItem, medianViews: number | null): number | null {
  if (medianViews == null || medianViews <= 0) return null;
  const views = typeof v.views === "number" && Number.isFinite(v.views) ? v.views : null;
  if (views == null) return null;
  return views / medianViews;
}

type SortContext = { medianViews: number | null };

function sortKey(v: ChannelVideoItem, col: VideoSortColumn, ctx: SortContext): number | string | null {
  switch (col) {
    case "title":
      return (v.title || v.video_id || "").toLowerCase();
    case "published": {
      const t = v.published_at ? Date.parse(String(v.published_at)) : NaN;
      return Number.isFinite(t) ? t : null;
    }
    case "duration":
      return typeof v.duration_s === "number" && Number.isFinite(v.duration_s) ? v.duration_s : null;
    case "views":
      return typeof v.views === "number" && Number.isFinite(v.views) ? v.views : null;
    case "likes":
      return typeof v.likes === "number" && Number.isFinite(v.likes) ? v.likes : null;
    case "comments":
      return typeof v.comments === "number" && Number.isFinite(v.comments) ? v.comments : null;
    case "views_per_day":
      return typeof v.views_per_day === "number" && Number.isFinite(v.views_per_day) ? v.views_per_day : null;
    case "vph":
      return typeof v.vph === "number" && Number.isFinite(v.vph) ? v.vph : null;
    case "engagement":
      return typeof v.engagement === "number" && Number.isFinite(v.engagement) ? v.engagement : null;
    case "like_rate":
      return typeof v.like_rate === "number" && Number.isFinite(v.like_rate) ? v.like_rate : null;
    case "comment_rate":
      return typeof v.comment_rate === "number" && Number.isFinite(v.comment_rate) ? v.comment_rate : null;
    case "engagement_per_sub":
      return typeof v.engagement_per_sub === "number" && Number.isFinite(v.engagement_per_sub) ? v.engagement_per_sub : null;
    case "outlier":
      return viewsVsChannelMedian(v, ctx.medianViews);
    default:
      return null;
  }
}

/** Descendente; valores ausentes al final. */
function compareDesc(a: number | string | null, b: number | string | null): number {
  const na = a === null || a === undefined || (typeof a === "number" && Number.isNaN(a));
  const nb = b === null || b === undefined || (typeof b === "number" && Number.isNaN(b));
  if (na && nb) return 0;
  if (na) return 1;
  if (nb) return -1;
  if (typeof a === "string" && typeof b === "string") return b.localeCompare(a, undefined, { sensitivity: "base" });
  return Number(b) - Number(a);
}

function compareVideos(a: ChannelVideoItem, b: ChannelVideoItem, stack: VideoSortColumn[], ctx: SortContext): number {
  for (const col of stack) {
    const c = compareDesc(sortKey(a, col, ctx), sortKey(b, col, ctx));
    if (c !== 0) return c;
  }
  return a.video_id.localeCompare(b.video_id);
}

function gradeOutlierVsMedian(r: number): "good" | "mid" | "bad" {
  if (r >= 1.25) return "good";
  if (r >= 0.85) return "mid";
  return "bad";
}

function SortHeader({
  col,
  stack,
  onToggle,
  children,
}: {
  col: VideoSortColumn;
  stack: VideoSortColumn[];
  onToggle: (c: VideoSortColumn) => void;
  children: ReactNode;
}) {
  const idx = stack.indexOf(col);
  const active = idx >= 0;
  return (
    <th className="px-3 py-2">
      <button
        type="button"
        className={`group inline-flex max-w-full items-center gap-1 whitespace-nowrap rounded-lg px-1 py-0.5 text-left transition hover:bg-slate-100 ${
          active ? "bg-emerald-50 text-emerald-900 ring-1 ring-emerald-200" : ""
        }`}
        onClick={() => onToggle(col)}
        title={
          active
            ? `Prioridad ${idx + 1}. Clic para quitar este criterio.`
            : "Clic: orden descendente (mayor → menor). Varios encabezados activos = orden combinado (1º, 2º…)."
        }
      >
        {children}
        {active ? (
          <span className="inline-flex h-4 min-w-[1rem] shrink-0 items-center justify-center rounded bg-emerald-600 px-0.5 text-[9px] font-bold leading-none text-white">
            {idx + 1}
          </span>
        ) : (
          <span className="shrink-0 text-[10px] text-slate-300 group-hover:text-slate-500">⇅</span>
        )}
      </button>
    </th>
  );
}

export function SavedChannelDetail(props: {
  selectedSavedChannelId: string;
  selectedSavedChannel: SavedChannelItem | null | undefined;
  selectedChannelSyncState: TaskOrStatus;
  workApplied: string;

  syncMaxVideos: number;
  setSyncMaxVideos: (n: number) => void;

  isEditingClassification: boolean;
  setIsEditingClassification: (v: boolean) => void;

  editCat: string;
  setEditCat: (v: string) => void;
  editLang: "" | "es" | "en";
  setEditLang: (v: "" | "es" | "en") => void;
  CATEGORY_OPTIONS: string[];

  savedChannelVideos: ChannelVideoItem[];
  selectedVideoIds: string[];
  setSelectedVideoIds: (ids: string[]) => void;
  allSelected: boolean;
  allVisibleVideoIds: string[];

  opportunityGrade: (score: number | null | undefined) => OpportunityGrade;
  opportunityLabel: (g: OpportunityGrade) => string;
  opportunityPillClass: (g: OpportunityGrade) => string;

  fmtK: (n: number | null | undefined) => string;

  metricPill: (text: string, grade: "good" | "mid" | "bad" | "na") => ReactNode;
  gradeViewsPerDay: (x: number | null | undefined) => "good" | "mid" | "bad" | "na";
  gradeVph: (x: number | null | undefined) => "good" | "mid" | "bad" | "na";
  gradeEngagement: (x: number | null | undefined) => "good" | "mid" | "bad" | "na";
  gradeLikeRate: (x: number | null | undefined) => "good" | "mid" | "bad" | "na";
  gradeCommentRate: (x: number | null | undefined) => "good" | "mid" | "bad" | "na";
  gradeEngagementPerSub: (x: number | null | undefined) => "good" | "mid" | "bad" | "na";

  onBack: () => void;
  onRefresh: () => void;
  onSaveClassification: () => void;
  onSyncNow: (maxVideos: number) => void;
  onBackfill: () => void;
  run: RunFn;
}) {
  const {
    selectedSavedChannelId,
    selectedSavedChannel,
    selectedChannelSyncState,
    syncMaxVideos,
    setSyncMaxVideos,
    isEditingClassification,
    setIsEditingClassification,
    editCat,
    setEditCat,
    editLang,
    setEditLang,
    CATEGORY_OPTIONS,
    savedChannelVideos,
    selectedVideoIds,
    setSelectedVideoIds,
    allSelected,
    allVisibleVideoIds,
    opportunityGrade,
    opportunityLabel,
    opportunityPillClass,
    fmtK,
    metricPill,
    gradeViewsPerDay,
    gradeVph,
    gradeEngagement,
    gradeLikeRate,
    gradeCommentRate,
    gradeEngagementPerSub,
    onBack,
    onRefresh,
    onSaveClassification,
    onSyncNow,
    onBackfill,
    run,
    workApplied,
  } = props;

  const [openTranscriptVideoId, setOpenTranscriptVideoId] = useState<string | null>(null);
  const [transcriptLoading, setTranscriptLoading] = useState(false);
  const [transcriptErr, setTranscriptErr] = useState<string | null>(null);
  const [transcriptText, setTranscriptText] = useState("");
  const [transcriptDurationS, setTranscriptDurationS] = useState<number | null>(null);

  const [sortStack, setSortStack] = useState<VideoSortColumn[]>([]);

  useEffect(() => {
    setSortStack([]);
  }, [selectedSavedChannelId]);

  const toggleSort = (col: VideoSortColumn) => {
    setSortStack((prev) => {
      const i = prev.indexOf(col);
      if (i >= 0) return prev.filter((_, j) => j !== i);
      return [...prev, col];
    });
  };

  /** Mediana de views del snapshot del canal (backend); si no hay, mediana de los vídeos visibles en tabla. */
  const effectiveMedianViews = useMemo(() => {
    const fromChannel =
      typeof selectedSavedChannel?.median_views === "number" && selectedSavedChannel.median_views > 0
        ? selectedSavedChannel.median_views
        : null;
    if (fromChannel != null) return fromChannel;
    const vals = savedChannelVideos.map((v) => v.views).filter((x): x is number => typeof x === "number" && Number.isFinite(x));
    if (!vals.length) return null;
    const s = [...vals].sort((a, b) => a - b);
    const mid = Math.floor(s.length / 2);
    return s.length % 2 !== 0 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
  }, [selectedSavedChannel?.median_views, savedChannelVideos]);

  const sortCtx = useMemo(() => ({ medianViews: effectiveMedianViews }), [effectiveMedianViews]);

  const displayedVideos = useMemo(() => {
    const slice = savedChannelVideos.slice(0, 100);
    if (sortStack.length === 0) return slice;
    return [...slice].sort((a, b) => compareVideos(a, b, sortStack, sortCtx));
  }, [savedChannelVideos, sortStack, sortCtx]);

  const loadTranscript = async (videoId: string) => {
    if (!videoId) return;
    setTranscriptErr(null);
    setTranscriptLoading(true);
    try {
      const r = await fetch(`/api/channels/${encodeURIComponent(selectedSavedChannelId)}/transcripts.json`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ work: workApplied, video_ids: [videoId], limit: 1, lang: editLang || "es" }),
      });
      if (!r.ok) {
        const t = await r.text();
        setTranscriptErr(t || `HTTP ${r.status}`);
        setTranscriptText("");
        setTranscriptDurationS(null);
        return;
      }
      const j = (await r.json()) as { videos?: { video_id?: string; transcript?: string; duration_s?: number | null }[] };
      const row = (j.videos || []).find((x) => x.video_id === videoId) || (j.videos || [])[0];
      setTranscriptText((row?.transcript || "").trim());
      const d = row?.duration_s;
      setTranscriptDurationS(typeof d === "number" && Number.isFinite(d) ? d : null);
    } catch (e) {
      setTranscriptErr(e instanceof Error ? e.message : String(e));
      setTranscriptText("");
      setTranscriptDurationS(null);
    } finally {
      setTranscriptLoading(false);
    }
  };

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Btn className="bg-white text-slate-900 ring-1 ring-slate-200 hover:bg-slate-50" onClick={onBack}>
          Volver
        </Btn>
        <Btn className="bg-slate-900 text-white hover:bg-slate-800" onClick={onRefresh}>
          Refrescar canal
        </Btn>
      </div>

      <div className="mt-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="flex items-start gap-3">
            <div className="h-12 w-12 overflow-hidden rounded-2xl bg-slate-100 ring-1 ring-slate-200">
              {selectedSavedChannel?.avatar_url ? <img src={selectedSavedChannel.avatar_url} alt="" className="h-12 w-12 object-cover" /> : null}
            </div>
            <div className="min-w-0">
              <div className="text-sm font-semibold text-slate-900">{selectedSavedChannel?.title || selectedSavedChannelId}</div>
              {selectedSavedChannel?.description ? (
                <div className="mt-0.5 max-w-3xl text-[11px] text-slate-600 line-clamp-2">{selectedSavedChannel.description}</div>
              ) : null}
              <a
                className="mt-0.5 inline-flex text-[11px] font-medium text-emerald-700 hover:underline"
                href={
                  selectedSavedChannel?.handle
                    ? `https://www.youtube.com/${encodeURIComponent(selectedSavedChannel.handle)}`
                    : `https://www.youtube.com/channel/${encodeURIComponent(selectedSavedChannelId)}`
                }
                target="_blank"
                rel="noreferrer"
              >
                Open channel
              </a>
            </div>
          </div>
        </div>
        {selectedChannelSyncState ? (
          <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2">
            <StatusBadge state={selectedChannelSyncState.state} />
            <span className="text-xs text-slate-600">{selectedChannelSyncState.detail}</span>
          </div>
        ) : null}
      </div>

      <div className="mt-3 grid gap-2 sm:grid-cols-3">
        <div className="rounded-xl border border-slate-100 bg-slate-50 p-3">
          <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
            Opportunity
            <InfoTip text="Channel opportunity score (composite): velocity + efficiency + consistency + engagement + longform ratio − inactivity penalty." />
          </div>
          <div className="mt-1 flex items-center gap-2">
            <div className="text-sm font-semibold text-slate-900">
              {typeof selectedSavedChannel?.opportunity_score === "number" ? selectedSavedChannel.opportunity_score.toFixed(2) : "—"}
            </div>
            {(() => {
              const g = opportunityGrade(selectedSavedChannel?.opportunity_score ?? null);
              return (
                <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold ${opportunityPillClass(g)}`}>
                  {opportunityLabel(g)}
                </span>
              );
            })()}
          </div>
        </div>
        <div className="rounded-xl border border-slate-100 bg-slate-50 p-3">
          <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
            Views/sub
            <InfoTip text="All-time views per subscriber (total_views / subscribers). High values can indicate an 'under-subscribed' channel with strong reach." />
          </div>
          <div className="mt-1 text-sm font-semibold text-slate-900">
            {typeof selectedSavedChannel?.views_per_sub === "number" ? selectedSavedChannel.views_per_sub.toFixed(1) : "—"}
          </div>
        </div>
        <div className="rounded-xl border border-slate-100 bg-slate-50 p-3">
          <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
            Duración mediana
            <InfoTip text="Median video duration (minutes) over the last synced window (default N=50). Used as a longform monetization proxy." />
          </div>
          <div className="mt-1 text-sm font-semibold text-slate-900">
            {typeof selectedSavedChannel?.median_duration_min === "number" ? `${selectedSavedChannel.median_duration_min.toFixed(1)} min` : "—"}
          </div>
        </div>
      </div>

      <div className="mt-3 rounded-2xl border border-slate-200 bg-white p-4">
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Clasificación (para thresholds)</div>

        {isEditingClassification ? (
          <>
            <div className="mt-2 grid gap-3 sm:grid-cols-3">
              <div className="sm:col-span-2">
                <Label>Categoría</Label>
                <Select value={editCat} onChange={(e) => setEditCat(e.target.value)}>
                  <option value="">(sin asignar)</option>
                  {CATEGORY_OPTIONS.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <Label>Idioma</Label>
                <Select value={editLang} onChange={(e) => setEditLang(e.target.value as "" | "es" | "en")}>
                  <option value="">(sin asignar)</option>
                  <option value="es">ES</option>
                  <option value="en">EN</option>
                </Select>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Btn className="bg-slate-900 text-white hover:bg-slate-800" onClick={onSaveClassification}>
                Guardar cambios
              </Btn>
              <Btn
                className="bg-white text-slate-900 ring-1 ring-slate-200 hover:bg-slate-50"
                onClick={() => setIsEditingClassification(false)}
              >
                Cancelar
              </Btn>
              <span className="text-xs text-slate-500">
                Perfil activo: <b>{selectedSavedChannel?.internal_category || "(default)"}</b>
              </span>
            </div>
          </>
        ) : (
          <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-700">
              <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-1">
                Categoría: <b>{selectedSavedChannel?.internal_category || "—"}</b>
              </span>
              <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-1">
                Idioma: <b>{selectedSavedChannel?.language || "—"}</b>
              </span>
            </div>
            <button
              type="button"
              className="inline-flex items-center justify-center rounded-xl bg-white px-3 py-2 text-xs font-medium text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"
              onClick={() => setIsEditingClassification(true)}
              title="Editar clasificación"
            >
              Editar
            </button>
          </div>
        )}
      </div>

      <div className="mt-3 flex flex-wrap items-end justify-between gap-2">
        <div className="flex flex-wrap gap-2">
          <Btn className="bg-slate-900 text-white hover:bg-slate-800" onClick={onBackfill}>
            Backfill desc/tags
          </Btn>
          <a
            className="inline-flex items-center justify-center rounded-xl px-4 py-2 text-sm font-medium ring-1 ring-slate-200 hover:bg-slate-50"
            href={`/api/channels/${encodeURIComponent(selectedSavedChannelId)}/thumbnails.zip?work=${encodeURIComponent(workApplied)}`}
          >
            Thumbnails ZIP
          </a>
          <a
            className="inline-flex items-center justify-center rounded-xl px-4 py-2 text-sm font-medium ring-1 ring-slate-200 hover:bg-slate-50"
            href={`/api/channels/${encodeURIComponent(selectedSavedChannelId)}/scripts.zip?work=${encodeURIComponent(workApplied)}`}
          >
            Scripts ZIP
          </a>
          <a
            className="inline-flex items-center justify-center rounded-xl px-4 py-2 text-sm font-medium ring-1 ring-slate-200 hover:bg-slate-50"
            href={`/api/channels/${encodeURIComponent(selectedSavedChannelId)}/videos.json?videos_limit=200`}
            target="_blank"
            rel="noreferrer"
          >
            Descargar JSON
          </a>
        </div>

        <div className="flex flex-wrap items-end justify-end gap-2">
          <div className="w-[120px]">
            <Label>Máx. vídeos</Label>
            <Input
              type="number"
              min={1}
              max={200}
              step={1}
              value={syncMaxVideos}
              onChange={(e) => setSyncMaxVideos(Number(e.target.value))}
            />
          </div>
          <Btn className="bg-emerald-600 text-white hover:bg-emerald-700" onClick={() => onSyncNow(syncMaxVideos)}>
            Sync now
          </Btn>
        </div>
      </div>

      <TranscriptsSessionPanel
        workApplied={workApplied}
        channelId={selectedSavedChannelId}
        videoIds={selectedVideoIds}
        lang={editLang || "es"}
        run={run}
      />

      <div className="mt-4 overflow-hidden rounded-2xl border border-slate-200 bg-white">
        <div className="bg-slate-50 px-3 py-2">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Vídeos (preview)</div>
          {sortStack.length ? (
            <div className="mt-1 text-[11px] font-normal normal-case text-slate-600">
              Orden activo (1º → último):{" "}
              <span className="font-medium text-slate-800">{sortStack.map((c) => SORT_COLUMN_LABEL[c]).join(" → ")}</span>
              <span className="text-slate-400"> · desc · clic de nuevo en un encabezado para quitarlo</span>
            </div>
          ) : null}
        </div>
        {savedChannelVideos.length ? (
          <div className="max-h-[520px] overflow-auto">
            <table className="w-full text-left text-xs">
              <thead className="sticky top-0 bg-white text-[11px] uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-3 py-2">
                    <input
                      type="checkbox"
                      checked={allSelected}
                      onChange={(e) => {
                        if (e.target.checked) setSelectedVideoIds(allVisibleVideoIds);
                        else setSelectedVideoIds([]);
                      }}
                    />
                  </th>
                  <SortHeader col="title" stack={sortStack} onToggle={toggleSort}>
                    Vídeo
                  </SortHeader>
                  <SortHeader col="published" stack={sortStack} onToggle={toggleSort}>
                    Publicado
                  </SortHeader>
                  <SortHeader col="duration" stack={sortStack} onToggle={toggleSort}>
                    Duración
                  </SortHeader>
                  <SortHeader col="views" stack={sortStack} onToggle={toggleSort}>
                    Views
                  </SortHeader>
                  <SortHeader col="outlier" stack={sortStack} onToggle={toggleSort}>
                    <span className="inline-flex items-center gap-1 whitespace-nowrap">
                      Outlier
                      <span onClick={(e) => e.stopPropagation()} className="inline-flex">
                        <InfoTip text="Views del vídeo / mediana de views del canal (backend, ventana sync). Mayor que 1 = por encima de la mediana del canal (outperform). Si el canal aún no tiene mediana, se calcula con los vídeos cargados en la tabla." />
                      </span>
                    </span>
                  </SortHeader>
                  <SortHeader col="likes" stack={sortStack} onToggle={toggleSort}>
                    Likes
                  </SortHeader>
                  <SortHeader col="comments" stack={sortStack} onToggle={toggleSort}>
                    <span className="inline-flex items-center gap-1 whitespace-nowrap">
                      Com
                      <span onClick={(e) => e.stopPropagation()} className="inline-flex">
                        <InfoTip text="Comments count." />
                      </span>
                    </span>
                  </SortHeader>
                  <SortHeader col="views_per_day" stack={sortStack} onToggle={toggleSort}>
                    <span className="inline-flex items-center gap-1 whitespace-nowrap">
                      V/D
                      <span onClick={(e) => e.stopPropagation()} className="inline-flex">
                        <InfoTip text="Views per day (views / age_days)." />
                      </span>
                    </span>
                  </SortHeader>
                  <SortHeader col="vph" stack={sortStack} onToggle={toggleSort}>
                    <span className="inline-flex items-center gap-1 whitespace-nowrap">
                      VPH
                      <span onClick={(e) => e.stopPropagation()} className="inline-flex">
                        <InfoTip text="Views per hour (views / age_hours)." />
                      </span>
                    </span>
                  </SortHeader>
                  <SortHeader col="engagement" stack={sortStack} onToggle={toggleSort}>
                    <span className="inline-flex items-center gap-1 whitespace-nowrap">
                      Eng
                      <span onClick={(e) => e.stopPropagation()} className="inline-flex">
                        <InfoTip text="Engagement rate = (likes + comments) / views." />
                      </span>
                    </span>
                  </SortHeader>
                  <SortHeader col="like_rate" stack={sortStack} onToggle={toggleSort}>
                    <span className="inline-flex items-center gap-1 whitespace-nowrap">
                      Like%
                      <span onClick={(e) => e.stopPropagation()} className="inline-flex">
                        <InfoTip text="Like rate = likes / views." />
                      </span>
                    </span>
                  </SortHeader>
                  <SortHeader col="comment_rate" stack={sortStack} onToggle={toggleSort}>
                    <span className="inline-flex items-center gap-1 whitespace-nowrap">
                      Com%
                      <span onClick={(e) => e.stopPropagation()} className="inline-flex">
                        <InfoTip text="Comment rate = comments / views." />
                      </span>
                    </span>
                  </SortHeader>
                  <SortHeader col="engagement_per_sub" stack={sortStack} onToggle={toggleSort}>
                    <span className="inline-flex items-center gap-1 whitespace-nowrap">
                      Eng/Sub
                      <span onClick={(e) => e.stopPropagation()} className="inline-flex">
                        <InfoTip text="Engagement per subscriber = (likes + comments) / subscribers." />
                      </span>
                    </span>
                  </SortHeader>
                  <th className="px-3 py-2 text-right">Acción</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {displayedVideos.map((v) => (
                  <tr key={v.video_id} className="bg-white">
                    <td className="px-3 py-2 align-top">
                      <input
                        type="checkbox"
                        checked={selectedVideoIds.includes(v.video_id)}
                        onChange={(e) => {
                          const checked = e.target.checked;
                          setSelectedVideoIds(
                            checked ? (selectedVideoIds.includes(v.video_id) ? selectedVideoIds : [...selectedVideoIds, v.video_id]) : selectedVideoIds.filter((id) => id !== v.video_id)
                          );
                        }}
                      />
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex items-start gap-2">
                        <div className="h-10 w-16 overflow-hidden rounded-lg bg-slate-100">
                          {v.thumbnail_url ? <img src={v.thumbnail_url} alt="" className="h-10 w-16 object-cover" /> : null}
                        </div>
                        <div className="min-w-0">
                          <div className="whitespace-normal break-words font-medium text-slate-900">{v.title || v.video_id}</div>
                          <div className="mt-0.5 line-clamp-2 max-w-[520px] text-[10px] text-slate-600">{v.description || ""}</div>
                          {(() => {
                            const raw = v.tags_json as unknown;
                            const tags = Array.isArray(raw)
                              ? (raw as unknown[]).map(String)
                              : Array.isArray((v as unknown as { tags?: unknown }).tags)
                                ? (v as unknown as { tags: unknown[] }).tags.map(String)
                                : [];
                            const top = tags.filter(Boolean).slice(0, 6);
                            return top.length ? (
                              <div className="mt-1 flex flex-wrap gap-1">
                                {top.map((t) => (
                                  <span key={t} className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-medium text-slate-700">
                                    {t}
                                  </span>
                                ))}
                              </div>
                            ) : null;
                          })()}
                        </div>
                      </div>
                    </td>
                    <td className="px-3 py-2 text-slate-700">{v.published_at ? String(v.published_at).slice(0, 10) : "—"}</td>
                    <td className="px-3 py-2 text-slate-700">{typeof v.duration_s === "number" ? `${Math.round(v.duration_s / 60)}m` : "—"}</td>
                    <td className="px-3 py-2 text-slate-700">{fmtK(v.views ?? null)}</td>
                    <td className="px-3 py-2 text-slate-700">
                      {(() => {
                        const r = viewsVsChannelMedian(v, effectiveMedianViews);
                        if (r == null) return "—";
                        return metricPill(`${r.toFixed(2)}×`, gradeOutlierVsMedian(r));
                      })()}
                    </td>
                    <td className="px-3 py-2 text-slate-700">{fmtK(v.likes ?? null)}</td>
                    <td className="px-3 py-2 text-slate-700">{fmtK(v.comments ?? null)}</td>
                    <td className="px-3 py-2 text-slate-700">
                      {typeof v.views_per_day === "number" ? metricPill(fmtK(v.views_per_day), gradeViewsPerDay(v.views_per_day)) : "—"}
                    </td>
                    <td className="px-3 py-2 text-slate-700">{typeof v.vph === "number" ? metricPill(fmtK(v.vph), gradeVph(v.vph)) : "—"}</td>
                    <td className="px-3 py-2 text-slate-700">
                      {typeof v.engagement === "number" ? metricPill(`${(v.engagement * 100).toFixed(2)}%`, gradeEngagement(v.engagement)) : "—"}
                    </td>
                    <td className="px-3 py-2 text-slate-700">
                      {typeof v.like_rate === "number" ? metricPill(`${(v.like_rate * 100).toFixed(2)}%`, gradeLikeRate(v.like_rate)) : "—"}
                    </td>
                    <td className="px-3 py-2 text-slate-700">
                      {typeof v.comment_rate === "number" ? metricPill(`${(v.comment_rate * 100).toFixed(2)}%`, gradeCommentRate(v.comment_rate)) : "—"}
                    </td>
                    <td className="px-3 py-2 text-slate-700">
                      {typeof v.engagement_per_sub === "number"
                        ? metricPill(`${(v.engagement_per_sub * 100).toFixed(2)}%`, gradeEngagementPerSub(v.engagement_per_sub))
                        : "—"}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <div className="flex items-center justify-end gap-3">
                        <button
                          type="button"
                          className="text-xs font-medium text-slate-700 hover:underline"
                          onClick={() => {
                            const next = openTranscriptVideoId === v.video_id ? null : v.video_id;
                            setOpenTranscriptVideoId(next);
                            if (next) void loadTranscript(next);
                          }}
                        >
                          Transcripts
                        </button>
                        <a
                          className="text-xs font-medium text-emerald-700 hover:underline"
                          href={`https://www.youtube.com/watch?v=${encodeURIComponent(v.video_id)}`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Abrir
                        </a>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {openTranscriptVideoId ? (
              <div className="border-t border-slate-200 bg-white p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="text-xs font-semibold text-slate-900">
                    Transcripts · {openTranscriptVideoId}
                    {transcriptDurationS != null ? (
                      <span className="ml-2 font-normal text-slate-500">
                        · Duración vídeo: {Math.floor(transcriptDurationS / 60)}m {transcriptDurationS % 60}s ({transcriptDurationS}s)
                      </span>
                    ) : (
                      <span className="ml-2 font-normal text-slate-400">· Duración: — (sync para rellenar)</span>
                    )}
                  </div>
                  <button
                    type="button"
                    className="text-xs font-medium text-slate-600 hover:underline"
                    onClick={() => setOpenTranscriptVideoId(null)}
                  >
                    Cerrar
                  </button>
                </div>

                {transcriptLoading ? <div className="mt-2 text-xs text-slate-600">Cargando…</div> : null}
                {transcriptErr ? <div className="mt-2 text-xs text-rose-700">{transcriptErr}</div> : null}

                {!transcriptLoading && !transcriptErr ? (
                  <div className="mt-2 rounded-xl border border-slate-200 bg-slate-50 p-3">
                    <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                      Texto ({transcriptText ? transcriptText.length : 0} chars)
                    </div>
                    <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap text-[11px] leading-snug text-slate-800">
                      {transcriptText || "— (sin transcript) —"}
                    </pre>
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        ) : (
          <div className="p-4 text-sm text-slate-600">No hay vídeos todavía. Pulsa “Sync now”.</div>
        )}
      </div>
    </div>
  );
}

