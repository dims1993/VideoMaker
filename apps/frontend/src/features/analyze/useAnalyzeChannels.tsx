import { useCallback, useEffect, useMemo, useState } from "react";
import type { ChannelSearchItem, ChannelVideoItem, SavedChannelItem, Session, TaskStatus } from "../../types";
import { MetricPill } from "./metrics/MetricPill";
import {
  CATEGORY_OPTIONS,
  createVideoMetricGraders,
  opportunityGrade,
  opportunityLabel,
  opportunityPillClass,
  profileForCategory,
  scorecard,
  gradeLabel,
  gradeClass,
  type MetricGrade,
} from "./metrics/channelMetrics";

export function useAnalyzeChannels(opts: { workApplied: string; session: Session | null }) {
  const { workApplied, session } = opts;

  const [channelSearchQ, setChannelSearchQ] = useState("");
  const [channelMinSubs, setChannelMinSubs] = useState(0);
  const [channelMinViews, setChannelMinViews] = useState(0);
  const [channelSort, setChannelSort] = useState<"subs" | "views" | "videos" | "views_per_video" | "views_per_sub">("subs");
  const [channelLang, setChannelLang] = useState<"" | "es" | "en">("");
  const [channelCategory, setChannelCategory] = useState("");
  const [channelSearchResults, setChannelSearchResults] = useState<ChannelSearchItem[]>([]);
  const [selectedChannel, setSelectedChannel] = useState<ChannelSearchItem | null>(null);
  const [savedChannels, setSavedChannels] = useState<SavedChannelItem[]>([]);
  const [selectedSavedChannelId, setSelectedSavedChannelId] = useState<string | null>(null);
  const [analyzePanel, setAnalyzePanel] = useState<"search" | "saved">("search");
  const [savedChannelVideos, setSavedChannelVideos] = useState<ChannelVideoItem[]>([]);
  const [selectedVideoIds, setSelectedVideoIds] = useState<string[]>([]);
  const [editCat, setEditCat] = useState("");
  const [editLang, setEditLang] = useState<"" | "es" | "en">("");
  const [syncMaxVideos, setSyncMaxVideos] = useState(50);
  const [isEditingClassification, setIsEditingClassification] = useState(true);

  const sleep = useCallback((ms: number) => new Promise((r) => setTimeout(r, ms)), []);

  const fetchSession = useCallback(async (): Promise<Session | null> => {
    try {
      const r = await fetch(`/api/session?work=${encodeURIComponent(workApplied)}`);
      if (!r.ok) return null;
      return (await r.json()) as Session;
    } catch {
      return null;
    }
  }, [workApplied]);

  const waitForChannelJob = useCallback(
    async (step: "channel_sync" | "channel_backfill", channelId: string, timeoutMs: number = 120_000) => {
      const startedAt = Date.now();
      while (Date.now() - startedAt < timeoutMs) {
        await sleep(1000);
        const s = await fetchSession();
        if (!s?.status) continue;
        const st = s.status;
        const detail = String(st.detail || "");
        if (st.step === step && detail.includes(channelId) && (st.state === "done" || st.state === "error")) return st;
      }
      return null;
    },
    [fetchSession, sleep]
  );

  const waitForTask = useCallback(
    async (taskId: string, timeoutMs: number = 180_000) => {
      const startedAt = Date.now();
      while (Date.now() - startedAt < timeoutMs) {
        await sleep(1200);
        const r = await fetch(`/api/tasks/${encodeURIComponent(taskId)}`);
        if (!r.ok) continue;
        const j = (await r.json()) as TaskStatus;
        const st = String(j.state || "").toLowerCase();
        if (st === "success" || st === "failure") return j;
      }
      return null;
    },
    [sleep]
  );

  const refreshSavedChannels = useCallback(async () => {
    try {
      const qs = new URLSearchParams({
        limit: "100",
        pearls_only: "true",
        window_videos: "50",
      });
      const r = await fetch(`/api/channels?${qs.toString()}`);
      if (!r.ok) return;
      const j = (await r.json()) as { channels: SavedChannelItem[] };
      setSavedChannels(j.channels || []);
    } catch {
      /* ignore */
    }
  }, []);

  const refreshSavedChannelVideos = useCallback(async (channelId: string) => {
    try {
      const r = await fetch(`/api/channels/${encodeURIComponent(channelId)}?videos_limit=100`);
      if (!r.ok) return;
      const j = (await r.json()) as { videos?: ChannelVideoItem[] };
      setSavedChannelVideos(j.videos || []);
      setSelectedVideoIds([]);
    } catch {
      /* ignore */
    }
  }, []);

  const selectedSavedChannel = useMemo(
    () => (selectedSavedChannelId ? savedChannels.find((x) => x.channel_id === selectedSavedChannelId) ?? null : null),
    [savedChannels, selectedSavedChannelId]
  );

  const activeThresholdProfile = useMemo(() => profileForCategory(selectedSavedChannel?.internal_category), [selectedSavedChannel?.internal_category]);

  const graders = useMemo(() => createVideoMetricGraders(activeThresholdProfile), [activeThresholdProfile]);

  const savedById = useMemo(() => {
    const m = new Map<string, SavedChannelItem>();
    for (const c of savedChannels) m.set(c.channel_id, c);
    return m;
  }, [savedChannels]);

  useEffect(() => {
    if (!selectedSavedChannelId) return;
    try {
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch {
      window.scrollTo(0, 0);
    }
  }, [selectedSavedChannelId]);

  useEffect(() => {
    if (!selectedSavedChannel) return;
    setEditCat(selectedSavedChannel.internal_category || "");
    setEditLang(((selectedSavedChannel.language as "" | "es" | "en") || "") as "" | "es" | "en");
  }, [selectedSavedChannel]);

  const selectedChannelSyncState = useMemo(() => {
    const st = session?.status;
    if (!st || !selectedSavedChannelId) return null;
    const mentionsChannel = (st.detail || "").includes(selectedSavedChannelId);
    if (!mentionsChannel) return null;
    if (st.step === "channel_sync" || st.step === "channel_scan") return st;
    return null;
  }, [session?.status, selectedSavedChannelId]);

  const allVisibleVideoIds = useMemo(() => savedChannelVideos.slice(0, 100).map((v) => v.video_id), [savedChannelVideos]);
  const allSelected = useMemo(
    () => allVisibleVideoIds.length > 0 && allVisibleVideoIds.every((id) => selectedVideoIds.includes(id)),
    [allVisibleVideoIds, selectedVideoIds]
  );

  const metricPillFn = useCallback((value: string, g: MetricGrade) => <MetricPill value={value} grade={g} />, []);

  return {
    categoryOptions: [...CATEGORY_OPTIONS],
    analyzePanel,
    setAnalyzePanel,
    channelSearchQ,
    setChannelSearchQ,
    channelMinSubs,
    setChannelMinSubs,
    channelMinViews,
    setChannelMinViews,
    channelSort,
    setChannelSort,
    channelLang,
    setChannelLang,
    channelCategory,
    setChannelCategory,
    channelSearchResults,
    setChannelSearchResults,
    selectedChannel,
    setSelectedChannel,
    savedChannels,
    savedById,
    selectedSavedChannelId,
    setSelectedSavedChannelId,
    savedChannelVideos,
    setSavedChannelVideos,
    selectedVideoIds,
    setSelectedVideoIds,
    editCat,
    setEditCat,
    editLang,
    setEditLang,
    syncMaxVideos,
    setSyncMaxVideos,
    isEditingClassification,
    setIsEditingClassification,
    selectedSavedChannel,
    refreshSavedChannels,
    refreshSavedChannelVideos,
    selectedChannelSyncState,
    allVisibleVideoIds,
    allSelected,
    scorecard,
    opportunityGrade,
    opportunityLabel,
    opportunityPillClass,
    gradeLabel,
    gradeClass,
    metricPill: metricPillFn,
    ...graders,
    waitForTask,
    waitForChannelJob,
  };
}

export type AnalyzeChannelsApi = ReturnType<typeof useAnalyzeChannels>;
