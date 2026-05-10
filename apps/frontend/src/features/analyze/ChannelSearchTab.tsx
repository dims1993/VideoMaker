import { Btn, Input, Label, Select } from "../../components/ui";
import { postJson, readApiError } from "../../services/api";
import type { ChannelSearchItem } from "../../types";
import type { RunFn } from "../../types/run";
import { fmtK, fmtPct } from "../../utils";
import type { AnalyzeChannelsApi } from "./useAnalyzeChannels";

export function ChannelSearchTab({ api, workApplied, run }: { api: AnalyzeChannelsApi; workApplied: string; run: RunFn }) {
  const {
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
    savedById,
    refreshSavedChannels,
    scorecard,
    gradeLabel,
    gradeClass,
  } = api;

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-900">Buscador de canales</div>
          <p className="mt-0.5 text-xs text-slate-500">Busca en YouTube por nombre y filtra por subs/views.</p>
        </div>
        <Btn
          className="bg-emerald-600 text-white hover:bg-emerald-700"
          disabled={!channelSearchQ.trim()}
          onClick={() =>
            run("Buscar canales", async () => {
              const qs = new URLSearchParams({
                q: channelSearchQ.trim(),
                min_subs: String(channelMinSubs || 0),
                min_views: String(channelMinViews || 0),
                category: channelCategory.trim(),
                language: channelLang,
                sort: channelSort,
                limit: "12",
              });
              const r = await fetch(`/api/channels/search?${qs.toString()}`);
              if (!r.ok) throw new Error(await readApiError(r));
              const j = (await r.json()) as { channels: ChannelSearchItem[] };
              const chans = j.channels || [];
              setChannelSearchResults(chans);
              await refreshSavedChannels();
            })
          }
        >
          Buscar
        </Btn>
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-6">
        <div className="md:col-span-2">
          <Label>Nombre / keyword</Label>
          <Input value={channelSearchQ} onChange={(e) => setChannelSearchQ(e.target.value)} placeholder="Deep Made Simple" />
        </div>
        <div>
          <Label>Min subs</Label>
          <Input type="number" min={0} value={channelMinSubs} onChange={(e) => setChannelMinSubs(Number(e.target.value))} />
        </div>
        <div>
          <Label>Min views</Label>
          <Input type="number" min={0} value={channelMinViews} onChange={(e) => setChannelMinViews(Number(e.target.value))} />
        </div>
        <div>
          <Label>Idioma</Label>
          <Select value={channelLang} onChange={(e) => setChannelLang(e.target.value as "" | "es" | "en")}>
            <option value="">Cualquiera</option>
            <option value="es">ES</option>
            <option value="en">EN</option>
          </Select>
        </div>
        <div className="md:col-span-2">
          <Label>Categoría interna</Label>
          <Input value={channelCategory} onChange={(e) => setChannelCategory(e.target.value)} placeholder="Fitness / Finanzas / Motivación..." />
          <p className="mt-1 text-[10px] text-slate-500">Se aplica solo a canales ya guardados (perlas) con categoría asignada.</p>
        </div>
        <div>
          <Label>Ordenar por</Label>
          <Select value={channelSort} onChange={(e) => setChannelSort(e.target.value as "subs" | "views" | "videos" | "views_per_video" | "views_per_sub")}>
            <option value="subs">Suscriptores</option>
            <option value="views">Visitas</option>
            <option value="videos">Nº vídeos</option>
            <option value="views_per_video">Views / vídeo</option>
            <option value="views_per_sub">Views / sub</option>
          </Select>
        </div>
      </div>

      {channelSearchResults.length ? (
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <div className="space-y-2">
            {channelSearchResults.map((c) => {
              const saved = savedById.get(c.channel_id);
              return (
                <button
                  key={c.channel_id}
                  type="button"
                  onClick={() => setSelectedChannel(c)}
                  className={`flex w-full items-center gap-3 rounded-2xl border px-3 py-2 text-left transition ${
                    selectedChannel?.channel_id === c.channel_id ? "border-emerald-200 bg-emerald-50" : "border-slate-200 bg-white hover:bg-slate-50"
                  }`}
                >
                  <div className="h-10 w-10 overflow-hidden rounded-xl bg-slate-100">
                    {c.avatar_url ? <img src={c.avatar_url} alt="" className="h-10 w-10 object-cover" /> : null}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-semibold text-slate-900">{c.title}</div>
                    <div className="mt-0.5 flex flex-wrap gap-x-2 gap-y-0.5 text-[10px] text-slate-500">
                      <span className="font-mono">{c.channel_id}</span>
                      {typeof c.subscribers === "number" ? <span>· subs {c.subscribers}</span> : null}
                      {typeof c.total_views === "number" ? <span>· views {c.total_views}</span> : null}
                    </div>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {saved?.is_pearl ? (
                        <>
                          <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] text-slate-700">
                            score {typeof saved.opportunity_score === "number" ? saved.opportunity_score.toFixed(2) : "—"}
                          </span>
                          <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] text-slate-700">
                            Δ30d views {fmtK(saved.views_delta_30d)}
                          </span>
                          <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] text-slate-700">
                            median {fmtK(saved.median_views)}
                          </span>
                          <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] text-slate-700">
                            hit {fmtPct(saved.hit_rate)}
                          </span>
                          <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] text-slate-700">
                            up/mo {typeof saved.uploads_per_month_90d === "number" ? saved.uploads_per_month_90d.toFixed(1) : "—"}
                          </span>
                        </>
                      ) : (
                        <span className="rounded-lg border border-slate-200 bg-white px-2 py-0.5 text-[10px] text-slate-500">
                          sin métricas (marca perla + Sync)
                        </span>
                      )}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="h-12 w-12 overflow-hidden rounded-2xl bg-slate-100">
                  {selectedChannel?.avatar_url ? <img src={selectedChannel.avatar_url} alt="" className="h-12 w-12 object-cover" /> : null}
                </div>
                <div>
                  <div className="text-sm font-semibold text-slate-900">{selectedChannel?.title || "Selecciona un canal"}</div>
                  <div className="mt-0.5 font-mono text-[11px] text-slate-500">{selectedChannel?.channel_id || ""}</div>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Btn
                  className="bg-slate-900 text-white hover:bg-slate-800"
                  disabled={!selectedChannel}
                  onClick={() =>
                    run("Guardar canal", async () => {
                      if (!selectedChannel) return;
                      await postJson(`/api/channels/save`, {
                        channel_id: selectedChannel.channel_id,
                        handle: selectedChannel.handle || "",
                        title: selectedChannel.title || "",
                        avatar_url: selectedChannel.avatar_url || "",
                        description: selectedChannel.description || "",
                      });
                      await refreshSavedChannels();
                    })
                  }
                >
                  Guardar
                </Btn>
                <Btn
                  className="bg-emerald-600 text-white hover:bg-emerald-700"
                  disabled={!selectedChannel}
                  onClick={() =>
                    run("Guardar como perla + Sync", async () => {
                      if (!selectedChannel) return;
                      await postJson(`/api/channels/save`, {
                        channel_id: selectedChannel.channel_id,
                        handle: selectedChannel.handle || "",
                        title: selectedChannel.title || "",
                        avatar_url: selectedChannel.avatar_url || "",
                        description: selectedChannel.description || "",
                      });
                      await postJson(`/api/channels/${encodeURIComponent(selectedChannel.channel_id)}/sync`, {
                        work: workApplied,
                      });
                      await refreshSavedChannels();
                    })
                  }
                >
                  Guardar + Sync
                </Btn>
                {selectedChannel ? (
                  <a
                    className="inline-flex items-center justify-center rounded-xl px-4 py-2 text-sm font-medium ring-1 ring-slate-200 hover:bg-slate-50"
                    href={`https://www.youtube.com/channel/${encodeURIComponent(selectedChannel.channel_id)}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Open on YouTube
                  </a>
                ) : null}
              </div>
            </div>

            <div className="mt-4 grid gap-2 text-xs text-slate-600 sm:grid-cols-2">
              <div className="rounded-xl border border-slate-100 bg-slate-50 p-3">
                <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Subs</div>
                <div className="mt-1 text-sm font-semibold text-slate-900">{selectedChannel?.subscribers ?? "—"}</div>
              </div>
              <div className="rounded-xl border border-slate-100 bg-slate-50 p-3">
                <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Views</div>
                <div className="mt-1 text-sm font-semibold text-slate-900">{selectedChannel?.total_views ?? "—"}</div>
              </div>
            </div>

            <div className="mt-3 rounded-2xl border border-slate-200 bg-white p-4">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Checklist Perla</div>
                  <div className="mt-1 text-sm font-semibold text-slate-900">
                    {(() => {
                      const saved = selectedChannel ? savedById.get(selectedChannel.channel_id) : null;
                      return scorecard(saved).decision;
                    })()}
                  </div>
                </div>
                <div className="text-[11px] text-slate-500">Regla: perla si 3/4 (mediana+hit+comentarios+uploads) salen bien.</div>
              </div>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {(() => {
                  const saved = selectedChannel ? savedById.get(selectedChannel.channel_id) : null;
                  const sc = scorecard(saved);
                  return sc.rows.map((r) => (
                    <div key={r.k} className="rounded-xl border border-slate-100 bg-slate-50 p-3">
                      <div className="flex items-center justify-between gap-2">
                        <div className="text-[11px] font-semibold text-slate-700">{r.k}</div>
                        <span className={`rounded-lg border px-2 py-0.5 text-[10px] ${gradeClass(r.g)}`}>{gradeLabel(r.g)}</span>
                      </div>
                      <div className="mt-1 text-sm font-semibold text-slate-900">{r.v}</div>
                      <div className="mt-0.5 text-[10px] text-slate-500">{r.rule}</div>
                    </div>
                  ));
                })()}
              </div>
              <p className="mt-3 text-xs text-slate-500">
                Para ver métricas, primero marca el canal como perla y ejecuta <b>Guardar + Sync</b>.
              </p>
            </div>
            <p className="mt-3 text-xs text-slate-500">
              Monetización/RPM: se estimará y se podrá editar cuando implementemos el directorio completo.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Btn
                className="bg-emerald-600 text-white hover:bg-emerald-700"
                disabled={!selectedChannel}
                onClick={() =>
                  run("Sync now", async () => {
                    if (!selectedChannel) return;
                    await postJson(`/api/channels/${encodeURIComponent(selectedChannel.channel_id)}/sync`, {
                      work: workApplied,
                    });
                    await refreshSavedChannels();
                  })
                }
              >
                Sync now
              </Btn>
              <a
                className={`inline-flex items-center justify-center rounded-xl px-4 py-2 text-sm font-medium ring-1 ring-slate-200 hover:bg-slate-50 ${
                  selectedChannel ? "" : "pointer-events-none opacity-50"
                }`}
                href={
                  selectedChannel ? `/api/channels/${encodeURIComponent(selectedChannel.channel_id)}/thumbnails.zip?work=${encodeURIComponent(workApplied)}` : "#"
                }
              >
                Download thumbnails zip
              </a>
              <a
                className={`inline-flex items-center justify-center rounded-xl px-4 py-2 text-sm font-medium ring-1 ring-slate-200 hover:bg-slate-50 ${
                  selectedChannel ? "" : "pointer-events-none opacity-50"
                }`}
                href={
                  selectedChannel ? `/api/channels/${encodeURIComponent(selectedChannel.channel_id)}/scripts.zip?work=${encodeURIComponent(workApplied)}` : "#"
                }
              >
                Download scripts zip
              </a>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
