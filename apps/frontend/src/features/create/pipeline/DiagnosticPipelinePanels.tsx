import { useCallback, useEffect, useState } from "react";
import { Btn, Input } from "../../../components/ui";
import { postJson, putJson } from "../../../services/api";
import type { RunFn } from "../types";
import { PacingDirectivePresetsBar } from "./PacingDirectivePresetsBar";
import { savePacingDirectivePreset } from "./pacingPassDirectivePresets";
import { PipelineStepConfirmBar } from "./PipelineStepConfirmBar";
import { ScriptQualityBanner } from "./ScriptQualityBanner";
import { fetchScriptLint, type ScriptLintReport } from "./scriptQuality";

type ArtifactPanelProps = {
  workApplied: string;
  run: RunFn;
  locked: boolean;
  stepState: string;
  artifactUrl: string;
  title: string;
  description: string;
  onAfterRun?: () => void | Promise<void>;
  stepId: string;
};

function ArtifactPanel({
  workApplied,
  run,
  locked,
  stepState,
  artifactUrl,
  title,
  description,
  onAfterRun,
  stepId,
}: ArtifactPanelProps) {
  const [json, setJson] = useState<string>("");

  const load = useCallback(async () => {
    const r = await fetch(`${artifactUrl}?work=${encodeURIComponent(workApplied)}`);
    if (!r.ok) {
      setJson("");
      return;
    }
    const j = await r.json();
    setJson(JSON.stringify(j, null, 2));
  }, [artifactUrl, workApplied]);

  useEffect(() => {
    void load();
  }, [load, stepState, workApplied]);

  return (
    <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div>
        <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
        <p className="mt-1 text-[12px] text-slate-600">{description}</p>
      </div>
      <PipelineStepConfirmBar
        stepId={stepId}
        stepLabel={title}
        workApplied={workApplied}
        stepState={stepState}
        run={run}
        onAfterRun={onAfterRun}
      />
      <div className="flex flex-wrap gap-2">
        <Btn
          type="button"
          className="bg-violet-600 text-white hover:bg-violet-500"
          disabled={locked || stepState === "running"}
          onClick={() =>
            run(`Start ${title}`, async () => {
              await postJson("/api/pipeline/step/rerun", {
                work: workApplied,
                step_id: stepId,
              });
              await onAfterRun?.();
              await load();
            })
          }
        >
          {stepState === "running" ? "Ejecutando…" : "Start step"}
        </Btn>
        <Btn type="button" className="border border-slate-200 bg-slate-50" onClick={() => void load()}>
          Recargar
        </Btn>
      </div>
      <pre className="max-h-[360px] overflow-auto rounded-xl border border-slate-100 bg-slate-50 p-3 text-[11px] text-slate-800">
        {json.trim() || "(sin artefacto aún)"}
      </pre>
    </div>
  );
}

export { NarrativeAnglePanel } from "./NarrativeAnglePanel";

function EditorialHeuristicLint({
  workApplied,
  sessionMinutes,
  refreshToken = "",
  subtitle,
}: {
  workApplied: string;
  sessionMinutes?: number;
  /** Cambia tras Pacing Pass / guardar guion para forzar re-lint. */
  refreshToken?: string;
  subtitle?: string;
}) {
  const [report, setReport] = useState<ScriptLintReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runLint = useCallback(async (opts?: { force?: boolean }) => {
    setLoading(true);
    setError(null);
    try {
      const sr = await fetch(`/api/script?work=${encodeURIComponent(workApplied)}`);
      if (!sr.ok) {
        setReport(null);
        return;
      }
      const sj = (await sr.json()) as { text?: string; quality?: ScriptLintReport | null };
      const text = (sj.text ?? "").trim();
      if (!text) {
        setReport(null);
        return;
      }
      const report = await fetchScriptLint({
        work: workApplied,
        text,
        targetMinutes: sessionMinutes,
        persist: true,
      });
      setReport(report);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al analizar el guion");
    } finally {
      setLoading(false);
    }
  }, [workApplied, sessionMinutes]);

  useEffect(() => {
    void runLint();
  }, [runLint]);

  return (
    <div className="space-y-2">
      {subtitle ? (
        <p className="text-[11px] leading-relaxed text-slate-600">{subtitle}</p>
      ) : null}
      <ScriptQualityBanner
        report={report}
        loading={loading}
        error={error}
        onReanalyze={() => void runLint({ force: true })}
      />
    </div>
  );
}

export function EditorialAnalyzerPanel(
  props: Omit<ArtifactPanelProps, "artifactUrl" | "title" | "description" | "stepId"> & {
    sessionMinutes?: number;
  },
) {
  return (
    <div className="space-y-4">
      <EditorialHeuristicLint
        workApplied={props.workApplied}
        sessionMinutes={props.sessionMinutes}
        subtitle="Patrones de plantilla (meta-hooks, reversiones, densidad B-roll). No sustituye al Editorial Analyzer (LLM) ni se borra solo al reescribir el guion."
      />
      <ArtifactPanel
        {...props}
        stepId="editorial_analyzer"
        artifactUrl="/api/pipeline/editorial-analysis"
        title="Editorial Analyzer"
        description="Diagnóstico LLM sobre el guion terminado: pacing, retención, densidad, visual, CTA. No reescribe. Ejecuta antes del Narrative Pacing Pass."
      />
    </div>
  );
}

type PacingPassSettingsResponse = {
  settings?: {
    target_minutes?: number | null;
    trim_to_duration?: boolean;
    user_directives?: string;
  };
  resolved_target_minutes?: number;
  last_result?: {
    words_before?: number;
    words_after?: number;
    minutes_before_est?: number;
    minutes_after_est?: number;
    target_minutes?: number;
  };
};

export function NarrativePacingPassPanel({
  workApplied,
  run,
  locked,
  stepState,
  onAfterRun,
  sessionMinutes,
}: Omit<ArtifactPanelProps, "artifactUrl" | "title" | "description" | "stepId"> & {
  sessionMinutes?: number;
}) {
  const [scriptText, setScriptText] = useState("");
  const [loadingScript, setLoadingScript] = useState(false);
  const [narrableWords, setNarrableWords] = useState<number | null>(null);
  const [estMinutes, setEstMinutes] = useState<number | null>(null);
  const [lintRefreshToken, setLintRefreshToken] = useState("");
  const [targetMinutes, setTargetMinutes] = useState<string>("");
  const [trimToDuration, setTrimToDuration] = useState(true);
  const [userDirectives, setUserDirectives] = useState("");
  const [lastResult, setLastResult] = useState<PacingPassSettingsResponse["last_result"]>(null);
  const [manualEditMode, setManualEditMode] = useState(false);
  const [scriptDirty, setScriptDirty] = useState(false);
  const [savingScript, setSavingScript] = useState(false);
  const [directivePresetsRefresh, setDirectivePresetsRefresh] = useState("");

  const loadScript = useCallback(async () => {
    setLoadingScript(true);
    try {
      const r = await fetch(`/api/script?work=${encodeURIComponent(workApplied)}`);
      if (!r.ok) {
        setScriptText("");
        setNarrableWords(null);
        setEstMinutes(null);
        return;
      }
      const j = (await r.json()) as {
        text?: string;
        quality?: { narrable_word_count?: number; estimated_minutes?: number };
      };
      const text = (j.text ?? "").trim();
      setScriptText(text);
      setScriptDirty(false);
      if (
        j.quality &&
        typeof j.quality.narrable_word_count === "number" &&
        typeof j.quality.estimated_minutes === "number"
      ) {
        setNarrableWords(j.quality.narrable_word_count);
        setEstMinutes(j.quality.estimated_minutes);
      } else if (text) {
        const report = await fetchScriptLint({
          work: workApplied,
          text,
          targetMinutes: sessionMinutes,
          persist: false,
        });
        setNarrableWords(report.narrable_word_count);
        setEstMinutes(report.estimated_minutes);
      } else {
        setNarrableWords(null);
        setEstMinutes(null);
      }
    } finally {
      setLoadingScript(false);
    }
  }, [workApplied, sessionMinutes]);

  const loadPacingSettings = useCallback(async () => {
    try {
      const r = await fetch(
        `/api/pipeline/pacing-pass-settings?work=${encodeURIComponent(workApplied)}`,
      );
      if (!r.ok) return;
      const j = (await r.json()) as PacingPassSettingsResponse;
      const resolved = j.resolved_target_minutes;
      const saved = j.settings?.target_minutes;
      if (saved != null && saved > 0) {
        setTargetMinutes(String(saved));
      } else if (resolved != null && resolved > 0) {
        setTargetMinutes(String(resolved));
      } else if (sessionMinutes != null && sessionMinutes > 0) {
        setTargetMinutes(String(sessionMinutes));
      }
      if (j.settings?.trim_to_duration !== undefined) {
        setTrimToDuration(Boolean(j.settings.trim_to_duration));
      }
      setUserDirectives(j.settings?.user_directives ?? "");
      setLastResult(j.last_result ?? null);
    } catch {
      if (sessionMinutes != null && sessionMinutes > 0) {
        setTargetMinutes(String(sessionMinutes));
      }
    }
  }, [workApplied, sessionMinutes]);

  useEffect(() => {
    void loadScript();
    void loadPacingSettings();
  }, [loadScript, loadPacingSettings, stepState, workApplied]);

  const savePacingSettings = async () => {
    const tm = parseFloat(targetMinutes.replace(",", "."));
    await putJson("/api/pipeline/pacing-pass-settings", {
      work: workApplied,
      target_minutes: Number.isFinite(tm) && tm > 0 ? tm : null,
      trim_to_duration: trimToDuration,
      user_directives: userDirectives,
    });
  };

  const saveDirectivePreset = async () => {
    const text = userDirectives.trim();
    if (!text) throw new Error("Escribe la directriz antes de guardarla como preset.");
    await savePacingDirectivePreset(text);
    setDirectivePresetsRefresh(String(Date.now()));
  };

  const runPacingPass = async () => {
    await savePacingSettings();
    await postJson("/api/pipeline/step/rerun", {
      work: workApplied,
      step_id: "narrative_pacing_pass",
    });
    await onAfterRun?.();
    await loadScript();
    await loadPacingSettings();
    setManualEditMode(false);
    setLintRefreshToken(String(Date.now()));
  };

  const saveGuionDraft = async () => {
    const text = scriptText.trim();
    if (!text) throw new Error("Escribe o pega el guion antes de guardar.");
    setSavingScript(true);
    try {
      await putJson("/api/script", { work: workApplied, text, only_disk: true });
      setScriptDirty(false);
    } finally {
      setSavingScript(false);
    }
  };

  const applyManualGuionAndLock = async () => {
    const text = scriptText.trim();
    if (!text) throw new Error("Escribe o pega el guion antes de aplicar.");
    await postJson("/api/pipeline/pacing-pass/apply-manual", {
      work: workApplied,
      text,
    });
    await onAfterRun?.();
    await loadScript();
    await loadPacingSettings();
    setManualEditMode(false);
    setLintRefreshToken(String(Date.now()));
  };

  const done = stepState === "done";
  const scriptIoLocked = stepState === "running";
  const pacingLocked = done && !manualEditMode;
  const canEditScript = !scriptIoLocked && (!done || manualEditMode);
  const overTarget =
    estMinutes != null &&
    targetMinutes.trim() !== "" &&
    Number.isFinite(parseFloat(targetMinutes)) &&
    estMinutes > parseFloat(targetMinutes) * 1.08;

  return (
    <div className="space-y-4">
      <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">Narrative Pacing Pass</h3>
          <p className="mt-1 text-[12px] text-slate-600">
            Segunda pasada del guion: ritmo, recorte a la duración objetivo y tus notas; o pega tu versión
            corregida a mano y bloquea el paso sin LLM. Sustituye{" "}
            <code className="rounded bg-slate-100 px-1">guion.txt</code>.
          </p>
        </div>
        {scriptIoLocked ? (
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-[12px] text-amber-900">
            <span className="font-semibold">Generando.</span> El LLM está reescribiendo el guion; espera a que
            termine.
          </div>
        ) : null}
        {done && !manualEditMode ? (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-[12px] text-emerald-900">
            Paso en <em>done</em>. Para pegar otra versión del guion, pulsa{" "}
            <strong>Editar guion</strong> y luego «Aplicar y bloquear».
          </div>
        ) : null}
        {done && manualEditMode ? (
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-[12px] text-amber-900">
            Modo edición: cambia el texto abajo y aplica para guardar y mantener el paso en <em>done</em>.
          </div>
        ) : null}
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block text-[12px] text-slate-700">
            Duración objetivo (min)
            <Input
              type="number"
              min={5}
              max={60}
              step={0.5}
              className="mt-1 w-full"
              value={targetMinutes}
              onChange={(e) => setTargetMinutes(e.target.value)}
              disabled={locked || stepState === "running"}
            />
          </label>
          <label className="flex items-end gap-2 text-[12px] text-slate-700 pb-2">
            <input
              type="checkbox"
              checked={trimToDuration}
              onChange={(e) => setTrimToDuration(e.target.checked)}
              disabled={locked || stepState === "running"}
              className="rounded border-slate-300"
            />
            Recortar si el guion supera la duración
          </label>
        </div>
        {overTarget && (
          <p className="text-[11px] text-amber-800 bg-amber-50 border border-amber-100 rounded-lg px-2 py-1.5">
            El borrador actual (~{estMinutes?.toFixed(1)} min narrables) supera el objetivo (
            {targetMinutes} min). Con «Recortar» activo, la pasada acortará antes de pulir ritmo.
          </p>
        )}
        <label className="block text-[12px] text-slate-700">
          Tus directrices (opcional)
          <textarea
            className="mt-1 w-full min-h-[88px] rounded-xl border border-slate-200 bg-white px-3 py-2 text-[12px] text-slate-800"
            placeholder="Ej.: Acorta el Pilar 2 a la mitad. Refuerza el gancho. Elimina la repetición sobre Zillow."
            value={userDirectives}
            onChange={(e) => setUserDirectives(e.target.value)}
            disabled={locked || stepState === "running"}
          />
        </label>
        <PacingDirectivePresetsBar
          disabled={locked || stepState === "running"}
          refreshToken={directivePresetsRefresh}
          run={run}
          onApply={(text) => setUserDirectives(text)}
        />
        {lastResult && (
          <p className="text-[11px] text-slate-600 font-mono">
            Última pasada: {lastResult.words_before} → {lastResult.words_after} palabras (
            ~{lastResult.minutes_before_est} → ~{lastResult.minutes_after_est} min)
          </p>
        )}
        <PipelineStepConfirmBar
          stepId="narrative_pacing_pass"
          stepLabel="Narrative Pacing Pass"
          workApplied={workApplied}
          stepState={stepState}
          run={run}
          onAfterRun={onAfterRun}
        />
        <div className="flex flex-wrap gap-2">
          {done && !manualEditMode ? (
            <Btn
              type="button"
              className="border border-slate-200 bg-white text-slate-900 hover:bg-slate-50"
              disabled={scriptIoLocked}
              onClick={() => setManualEditMode(true)}
            >
              Editar guion
            </Btn>
          ) : null}
          {canEditScript ? (
            <>
              <Btn
                type="button"
                className="border border-slate-200 bg-slate-50"
                disabled={locked || scriptIoLocked || savingScript || !scriptText.trim()}
                onClick={() => run("Guardar borrador de guion", saveGuionDraft)}
              >
                {savingScript ? "Guardando…" : "Guardar borrador"}
              </Btn>
              <Btn
                type="button"
                className="bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-40"
                disabled={locked || scriptIoLocked || !scriptText.trim()}
                onClick={() => run("Aplicar guion manual y bloquear", applyManualGuionAndLock)}
              >
                Aplicar guion y bloquear (sin LLM)
              </Btn>
            </>
          ) : null}
          <Btn
            type="button"
            className="border border-violet-200 bg-violet-50 text-violet-900 hover:bg-violet-100"
            disabled={locked || scriptIoLocked || !userDirectives.trim()}
            onClick={() => run("Guardar directriz", saveDirectivePreset)}
          >
            Guardar directriz
          </Btn>
          <Btn
            type="button"
            className="border border-slate-200 bg-slate-50"
            disabled={locked || scriptIoLocked}
            onClick={() => run("Guardar ajustes de sesión", savePacingSettings)}
          >
            Guardar ajustes
          </Btn>
          <Btn
            type="button"
            className="bg-violet-600 text-white hover:bg-violet-500"
            disabled={locked || scriptIoLocked}
            onClick={() => run("Start Narrative Pacing Pass", runPacingPass)}
          >
            {stepState === "running" ? "Ejecutando…" : "Start step (LLM)"}
          </Btn>
          <Btn
            type="button"
            className="border border-slate-200 bg-slate-50"
            onClick={() => {
              void loadScript();
              void loadPacingSettings();
            }}
          >
            Recargar
          </Btn>
          {manualEditMode ? (
            <Btn
              type="button"
              className="border border-slate-200 bg-slate-50 text-slate-600"
              onClick={() => {
                setManualEditMode(false);
                void loadScript();
              }}
            >
              Cancelar edición
            </Btn>
          ) : null}
        </div>
        {scriptDirty && canEditScript ? (
          <p className="text-[11px] text-amber-800">Hay cambios sin guardar en el editor.</p>
        ) : null}
        {!done ? (
          <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-[12px] text-slate-600">
            Pega tu guion corregido abajo y usa <strong>Aplicar guion y bloquear</strong>, o ejecuta{" "}
            <strong>Start step (LLM)</strong> con las directrices de arriba.
          </div>
        ) : null}
        <label className="block text-[12px] font-medium text-slate-700">
          Guion {pacingLocked ? "(solo lectura)" : "(editable)"}
          <textarea
            className="mt-1 w-full min-h-[280px] max-h-[480px] rounded-xl border border-slate-200 bg-white px-3 py-2 font-mono text-[11px] text-slate-800 leading-relaxed disabled:bg-slate-50"
            placeholder={
              loadingScript
                ? "Cargando guion…"
                : "Pega aquí el guion completo (OUTLINE + GUIÓN + KEYWORDS)…"
            }
            value={scriptText}
            disabled={!canEditScript || loadingScript}
            onChange={(e) => {
              setScriptText(e.target.value);
              setScriptDirty(true);
            }}
          />
        </label>
        {done && narrableWords != null && estMinutes != null ? (
          <p className="text-[11px] text-slate-600">
            En disco: ~{estMinutes.toFixed(1)} min narrables ({narrableWords.toLocaleString()} palabras sin
            outline/B-roll).
          </p>
        ) : null}
      </div>
      {done ? (
        <EditorialHeuristicLint
          workApplied={workApplied}
          sessionMinutes={sessionMinutes}
          refreshToken={lintRefreshToken}
          subtitle="Tras el Pacing Pass el guion en disco cambió: este bloque se recalcula sobre el texto reescrito. Algunas alertas (muletillas, reversiones) pueden seguir si el modelo no las eliminó."
        />
      ) : null}
    </div>
  );
}
