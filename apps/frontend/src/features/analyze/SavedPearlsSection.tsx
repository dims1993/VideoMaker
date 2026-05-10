import { deleteReq, postJson, putJson } from "../../services/api";
import type { RunFn } from "../../types/run";
import { fmtK } from "../../utils";
import { SavedChannelDetail } from "../dashboard/saved/SavedChannelDetail";
import type { AnalyzeChannelsApi } from "./useAnalyzeChannels";

export function SavedPearlsSection({ api, workApplied, run }: { api: AnalyzeChannelsApi; workApplied: string; run: RunFn }) {
  const {
    selectedSavedChannelId,
    selectedSavedChannel,
    selectedChannelSyncState,
    syncMaxVideos,
    setSyncMaxVideos,
    editCat,
    setEditCat,
    editLang,
    setEditLang,
    isEditingClassification,
    setIsEditingClassification,
    categoryOptions,
    savedChannelVideos,
    selectedVideoIds,
    setSelectedVideoIds,
    allSelected,
    allVisibleVideoIds,
    opportunityGrade,
    opportunityLabel,
    opportunityPillClass,
    metricPill,
    gradeViewsPerDay,
    gradeVph,
    gradeEngagement,
    gradeLikeRate,
    gradeCommentRate,
    gradeEngagementPerSub,
    setSelectedSavedChannelId,
    setSavedChannelVideos,
    refreshSavedChannels,
    refreshSavedChannelVideos,
    waitForTask,
    waitForChannelJob,
    savedChannels,
  } = api;

  return selectedSavedChannelId ? (
    <SavedChannelDetail
      selectedSavedChannelId={selectedSavedChannelId}
      selectedSavedChannel={selectedSavedChannel}
      selectedChannelSyncState={selectedChannelSyncState}
      workApplied={workApplied}
      syncMaxVideos={syncMaxVideos}
      setSyncMaxVideos={setSyncMaxVideos}
      editCat={editCat}
      setEditCat={setEditCat}
      editLang={editLang}
      setEditLang={setEditLang}
      isEditingClassification={isEditingClassification}
      setIsEditingClassification={setIsEditingClassification}
      CATEGORY_OPTIONS={categoryOptions}
      savedChannelVideos={savedChannelVideos}
      selectedVideoIds={selectedVideoIds}
      setSelectedVideoIds={setSelectedVideoIds}
      allSelected={allSelected}
      allVisibleVideoIds={allVisibleVideoIds}
      opportunityGrade={opportunityGrade}
      opportunityLabel={opportunityLabel}
      opportunityPillClass={opportunityPillClass}
      fmtK={fmtK}
      metricPill={metricPill}
      gradeViewsPerDay={gradeViewsPerDay}
      gradeVph={gradeVph}
      gradeEngagement={gradeEngagement}
      gradeLikeRate={gradeLikeRate}
      gradeCommentRate={gradeCommentRate}
      gradeEngagementPerSub={gradeEngagementPerSub}
      onBack={() => {
        setSelectedSavedChannelId(null);
        setSavedChannelVideos([]);
      }}
      onRefresh={() =>
        run("Refrescar canal", async () => {
          await refreshSavedChannels();
          await refreshSavedChannelVideos(selectedSavedChannelId);
        })
      }
      onSaveClassification={() =>
        run("Guardar clasificación", async () => {
          await putJson(`/api/channels/${encodeURIComponent(selectedSavedChannelId)}`, {
            internal_category: editCat || null,
            language: editLang || null,
          });
          await refreshSavedChannels();
          setIsEditingClassification(false);
        })
      }
      onSyncNow={(maxVideos) =>
        run("Sync canal", async () => {
          const mv = Math.max(1, Math.min(Number.isFinite(maxVideos) ? Math.floor(maxVideos) : 50, 200));
          const res = await postJson<{ mode?: string; task_id?: string }>(
            `/api/channels/${encodeURIComponent(selectedSavedChannelId)}/sync?work=${encodeURIComponent(workApplied)}&max_videos=${encodeURIComponent(String(mv))}`,
            {}
          );
          if (res?.mode === "celery" && res.task_id) {
            await waitForTask(res.task_id, 240_000);
          } else {
            await waitForChannelJob("channel_sync", selectedSavedChannelId, 240_000);
          }
          await refreshSavedChannels();
          await refreshSavedChannelVideos(selectedSavedChannelId);
        })
      }
      onBackfill={() =>
        run("Backfill desc/tags", async () => {
          await postJson(`/api/channels/${encodeURIComponent(selectedSavedChannelId)}/backfill`, { work: workApplied, limit: 200 });
          await waitForChannelJob("channel_backfill", selectedSavedChannelId, 180_000);
          await refreshSavedChannelVideos(selectedSavedChannelId);
        })
      }
      onDownloadTranscriptsJson={() =>
        run("Descargar transcripts JSON", async () => {
          const ids = selectedVideoIds.length ? selectedVideoIds : [];
          const r = await fetch(`/api/channels/${encodeURIComponent(selectedSavedChannelId)}/transcripts.json`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ work: workApplied, video_ids: ids, limit: 50, lang: editLang || "es" }),
          });
          if (!r.ok) return;
          const text = await r.text();
          const blob = new Blob([text], { type: "application/json" });
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = `transcripts_${selectedSavedChannelId}.json`;
          document.body.appendChild(a);
          a.click();
          a.remove();
          URL.revokeObjectURL(url);
        })
      }
    />
  ) : (
    <div className="space-y-2">
      {savedChannels.length ? (
        savedChannels.map((c) => (
          <div
            key={c.channel_id}
            className="flex w-full items-center gap-3 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-left transition hover:bg-slate-50"
          >
            <div className="h-10 w-10 overflow-hidden rounded-xl bg-slate-100">
              {c.avatar_url ? <img src={c.avatar_url} alt="" className="h-10 w-10 object-cover" /> : null}
            </div>
            <button
              type="button"
              onClick={() => {
                setSelectedSavedChannelId(c.channel_id);
                setSyncMaxVideos(50);
                setIsEditingClassification(!(c.internal_category || c.language));
                setEditCat(c.internal_category || "");
                setEditLang((c.language as "" | "es" | "en") || "");
                void refreshSavedChannelVideos(c.channel_id);
              }}
              className="min-w-0 flex-1 text-left"
              title="Abrir canal"
            >
              <div className="truncate text-sm font-semibold text-slate-900">{c.title || c.channel_id}</div>
              {c.internal_category ? <div className="mt-0.5 text-[10px] text-slate-500">cat: {c.internal_category}</div> : null}
            </button>

            <button
              type="button"
              className="inline-flex items-center justify-center rounded-xl bg-white px-3 py-2 text-xs font-medium text-slate-700 ring-1 ring-slate-200 hover:bg-rose-50 hover:text-rose-700"
              title="Eliminar canal"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                const ok = window.confirm(`¿Eliminar el canal "${c.title || c.channel_id}"?\n\nEsto borrará también vídeos y assets asociados.`);
                if (!ok) return;
                void run("Eliminar canal", async () => {
                  await deleteReq(`/api/channels/${encodeURIComponent(c.channel_id)}`);
                  setSelectedSavedChannelId(null);
                  setSavedChannelVideos([]);
                  await refreshSavedChannels();
                });
              }}
            >
              Eliminar
            </button>
          </div>
        ))
      ) : (
        <p className="text-sm text-slate-600">No hay canales guardados todavía.</p>
      )}
    </div>
  );
}
