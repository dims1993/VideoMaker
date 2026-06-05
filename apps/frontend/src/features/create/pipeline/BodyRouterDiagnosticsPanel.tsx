import { useCallback, useEffect, useState } from "react";
import { Btn } from "../../../components/ui";
import {
  fetchBodyRouterDiagnostics,
  type BodyRouterDiagnostics,
  type SectionDensityPlanSummary,
} from "./bodyRouterDiagnostics";

export function BodyRouterDiagnosticsPanel({
  workApplied,
  refreshToken = "",
}: {
  workApplied: string;
  refreshToken?: string;
}) {
  const [diag, setDiag] = useState<BodyRouterDiagnostics | null>(null);
  const [plan, setPlan] = useState<SectionDensityPlanSummary | null>(null);
  const [exists, setExists] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const j = await fetchBodyRouterDiagnostics(workApplied);
      setExists(Boolean(j.exists));
      setDiag(j.diagnostics);
      setPlan(j.visual_density_plan ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al cargar diagnóstico");
      setDiag(null);
      setPlan(null);
    } finally {
      setLoading(false);
    }
  }, [workApplied]);

  useEffect(() => {
    void load();
  }, [load, refreshToken, workApplied]);

  const ts = diag?.track_summary;
  const density = diag?.density;
  const hookTarget = plan?.hook_target_images ?? density?.hook_target_images;
  const bodyTarget = plan?.body_target_images ?? density?.body_target_images;
  const totalTarget = plan?.total_target_images ?? density?.total_target_images;

  return (
    <div className="rounded-2xl border border-violet-100 bg-violet-50/40 p-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-violet-950">Plan de imágenes (audio)</h3>
          <p className="text-[11px] text-violet-800/90 mt-0.5">
            Gancho denso (~3.5 s/plano), cuerpo más relajado (~6.5 s, máx. 8 s). Sin tope fijo de 48.
          </p>
        </div>
        <Btn
          type="button"
          className="border border-violet-200 bg-white text-violet-900 text-xs"
          disabled={loading}
          onClick={() => void load()}
        >
          {loading ? "Analizando…" : "Actualizar"}
        </Btn>
      </div>

      {error && (
        <p className="text-xs text-red-700 rounded-lg bg-red-50 px-2 py-1">{error}</p>
      )}

      {plan && (
        <div className="rounded-xl border border-violet-200/80 bg-white/90 px-3 py-2 text-[11px] text-violet-950 space-y-1">
          <p>
            <strong>Objetivo total ~{totalTarget ?? "—"} imágenes</strong>
            {plan.total_narration_min != null && (
              <span> · narración ~{plan.total_narration_min} min</span>
            )}
            {plan.audio_source && (
              <span className="text-violet-600"> ({plan.audio_source})</span>
            )}
          </p>
          <p>
            Gancho: <strong>{hookTarget ?? "—"}</strong> planos
            {plan.hook_pool_min != null && ` · ~${plan.hook_pool_min} min`}
            {plan.hook_target_hold_s != null && ` · ~${plan.hook_target_hold_s}s corte`}
          </p>
          <p>
            Cuerpo: <strong>{bodyTarget ?? "—"}</strong> macro_beats
            {plan.body_pool_min != null && ` · ~${plan.body_pool_min} min`}
            {plan.body_target_hold_s != null && ` · ~${plan.body_target_hold_s}s corte`}
            {plan.body_max_hold_s != null && ` (máx. ${plan.body_max_hold_s}s/plano)`}
          </p>
          {plan.notes && <p className="text-violet-700">{plan.notes}</p>}
        </div>
      )}

      {!exists && !loading && !plan && (
        <p className="text-xs text-violet-800">
          Tras ejecutar routers verás el plan según guion o TTS medido.
        </p>
      )}

      {diag && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
            <Stat label="Beats actuales" value={String(diag.macro_beat_count ?? "—")} />
            <Stat
              label="Insert / avatar"
              value={`${ts?.insert ?? 0} / ${ts?.avatar ?? 0}`}
            />
            <Stat
              label="Objetivo cuerpo"
              value={String(bodyTarget ?? density?.target_beat_count ?? "—")}
              sub={
                density?.beats_deficit
                  ? `faltan ${density.beats_deficit}`
                  : "OK"
              }
            />
            <Stat
              label="~s / beat"
              value={
                density?.avg_sec_per_beat_if_equal != null
                  ? String(density.avg_sec_per_beat_if_equal)
                  : "—"
              }
              sub={
                density?.body_max_hold_s != null
                  ? `máx ${density.body_max_hold_s}s`
                  : undefined
              }
            />
          </div>

          {diag.warnings && diag.warnings.length > 0 ? (
            <ul className="list-disc pl-4 space-y-1 text-[11px] text-amber-950">
              {diag.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          ) : (
            <p className="text-[11px] text-emerald-800 bg-emerald-50 border border-emerald-100 rounded-lg px-2 py-1">
              Estructura del cuerpo alineada con el plan de densidad.
            </p>
          )}
        </>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="rounded-xl bg-white/90 border border-violet-100 px-2 py-2">
      <div className="text-[10px] uppercase tracking-wide text-violet-600">{label}</div>
      <div className="text-lg font-semibold text-violet-950">{value}</div>
      {sub && <div className="text-[10px] text-violet-700">{sub}</div>}
    </div>
  );
}
