import { Btn, InfoTip, Label, Select, StatusBadge } from "../../../components/ui";
import type { ChannelVideoItem, SavedChannelItem } from "../../../types";

type TaskOrStatus = { state: string; detail: string } | null;

type OpportunityGrade = "bajo" | "medio" | "alto" | "perla" | "sin_datos";

export function SavedChannelDetail(props: {
  selectedSavedChannelId: string;
  selectedSavedChannel: SavedChannelItem | null | undefined;
  selectedChannelSyncState: TaskOrStatus;
  workApplied: string;

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

  metricPill: (text: string, grade: "good" | "mid" | "bad" | "na") => unknown;
  gradeViewsPerDay: (x: number | null | undefined) => "good" | "mid" | "bad" | "na";
  gradeVph: (x: number | null | undefined) => "good" | "mid" | "bad" | "na";
  gradeEngagement: (x: number | null | undefined) => "good" | "mid" | "bad" | "na";
  gradeLikeRate: (x: number | null | undefined) => "good" | "mid" | "bad" | "na";
  gradeCommentRate: (x: number | null | undefined) => "good" | "mid" | "bad" | "na";
  gradeEngagementPerSub: (x: number | null | undefined) => "good" | "mid" | "bad" | "na";

  onBack: () => void;
  onRefresh: () => void;
  onSaveClassification: () => void;
  onSyncNow: () => void;
  onBackfill: () => void;
  onDownloadTranscriptsJson: () => void;
}) {
  const {
    selectedSavedChannelId,
    selectedSavedChannel,
    selectedChannelSyncState,
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
    onDownloadTranscriptsJson,
    workApplied,
  } = props;

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
              <div className="mt-0.5 text-[11px] text-slate-500 font-mono">{selectedSavedChannelId}</div>
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
          <span className="text-xs text-slate-500">
            Perfil activo: <b>{selectedSavedChannel?.internal_category || "(default)"}</b>
          </span>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <Btn className="bg-emerald-600 text-white hover:bg-emerald-700" onClick={onSyncNow}>
          Sync now
        </Btn>
        <Btn className="bg-slate-900 text-white hover:bg-slate-800" onClick={onBackfill}>
          Backfill desc/tags
        </Btn>
        <Btn className="bg-indigo-600 text-white hover:bg-indigo-700" onClick={onDownloadTranscriptsJson}>
          Transcripts JSON
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

      <div className="mt-4 overflow-hidden rounded-2xl border border-slate-200 bg-white">
        <div className="bg-slate-50 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Vídeos (preview)</div>
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
                  <th className="px-3 py-2">Vídeo</th>
                  <th className="px-3 py-2">Publicado</th>
                  <th className="px-3 py-2">Duración</th>
                  <th className="px-3 py-2">Views</th>
                  <th className="px-3 py-2">Likes</th>
                  <th className="px-3 py-2">
                    <span className="inline-flex items-center gap-1 whitespace-nowrap">
                      Com
                      <InfoTip text="Comments count." />
                    </span>
                  </th>
                  <th className="px-3 py-2">
                    <span className="inline-flex items-center gap-1 whitespace-nowrap">
                      V/D
                      <InfoTip text="Views per day (views / age_days)." />
                    </span>
                  </th>
                  <th className="px-3 py-2">
                    <span className="inline-flex items-center gap-1 whitespace-nowrap">
                      VPH
                      <InfoTip text="Views per hour (views / age_hours)." />
                    </span>
                  </th>
                  <th className="px-3 py-2">
                    <span className="inline-flex items-center gap-1 whitespace-nowrap">
                      Eng
                      <InfoTip text="Engagement rate = (likes + comments) / views." />
                    </span>
                  </th>
                  <th className="px-3 py-2">
                    <span className="inline-flex items-center gap-1 whitespace-nowrap">
                      Like%
                      <InfoTip text="Like rate = likes / views." />
                    </span>
                  </th>
                  <th className="px-3 py-2">
                    <span className="inline-flex items-center gap-1 whitespace-nowrap">
                      Com%
                      <InfoTip text="Comment rate = comments / views." />
                    </span>
                  </th>
                  <th className="px-3 py-2">
                    <span className="inline-flex items-center gap-1 whitespace-nowrap">
                      Eng/Sub
                      <InfoTip text="Engagement per subscriber = (likes + comments) / subscribers." />
                    </span>
                  </th>
                  <th className="px-3 py-2 text-right">Acción</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {savedChannelVideos.slice(0, 100).map((v) => (
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
                      <a
                        className="text-xs font-medium text-emerald-700 hover:underline"
                        href={`https://www.youtube.com/watch?v=${encodeURIComponent(v.video_id)}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Abrir
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-4 text-sm text-slate-600">No hay vídeos todavía. Pulsa “Sync now”.</div>
        )}
      </div>
    </div>
  );
}

