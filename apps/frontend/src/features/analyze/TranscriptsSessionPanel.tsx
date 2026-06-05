import { useCallback, useEffect, useRef, useState } from "react";
import { Btn } from "../../components/ui";
import { postJson } from "../../services/api";
import type { RunFn } from "../../types/run";
import {
  fetchTranscriptsProviderConfig,
  fetchTranscriptsSession,
  sessionLoadLabel,
  normalizeAnalyzeOutputLang,
  sessionReadyHint,
  sessionReadyLabel,
  type AnalyzeOutputLanguage,
  type TranscriptsProviderConfig,
  type TranscriptsSessionView,
} from "./transcriptsSession";

type TranscriptsSessionPanelProps = {
  workApplied: string;
  channelId: string;
  videoIds: string[];
  lang: string;
  run: RunFn;
  onSessionChange?: (view: TranscriptsSessionView) => void;
};

export function TranscriptsSessionPanel({
  workApplied,
  channelId,
  videoIds,
  lang,
  run,
  onSessionChange,
}: TranscriptsSessionPanelProps) {
  const [view, setView] = useState<TranscriptsSessionView | null>(null);
  const [providerCfg, setProviderCfg] =
    useState<TranscriptsProviderConfig | null>(null);
  const [loadError, setLoadError] = useState("");
  const [loading, setLoading] = useState(false);
  const [analyzeOutputLang, setAnalyzeOutputLang] =
    useState<AnalyzeOutputLanguage>(() => normalizeAnalyzeOutputLang(lang));
  const [debugProvider, setDebugProvider] = useState(false);
  const importRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setAnalyzeOutputLang(normalizeAnalyzeOutputLang(lang));
  }, [lang, channelId]);

  const refresh = useCallback(async () => {
    const v = await fetchTranscriptsSession(workApplied);
    setView(v);
    if (v.analyze_output_language) {
      setAnalyzeOutputLang(
        normalizeAnalyzeOutputLang(v.analyze_output_language),
      );
    }
    onSessionChange?.(v);
    return v;
  }, [workApplied, onSessionChange]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    void fetchTranscriptsProviderConfig().then(setProviderCfg);
  }, []);

  const handleLoadSession = () =>
    run("Cargar transcripts en sesión", async () => {
      setLoadError("");
      setLoading(true);
      try {
        const res = await postJson<TranscriptsSessionView>(
          `/api/channels/${encodeURIComponent(channelId)}/transcripts/session`,
          {
            work: workApplied,
            video_ids: videoIds,
            limit: 50,
            lang: lang || "es",
          },
        );
        setView(res);
        onSessionChange?.(res);
      } catch (e) {
        setLoadError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    });

  const handleAnalyze = () =>
    run("Analizar transcripts", async () => {
      setLoadError("");
      setView((prev) =>
        prev
          ? { ...prev, analyze_status: "analyzing" }
          : {
              stored: true,
              valid_count: 0,
              combined_chars: 0,
              ready_to_analyze: false,
              analyze_status: "analyzing",
            },
      );
      try {
        const res = await postJson<TranscriptsSessionView>(
          "/api/session/transcripts/analyze",
          {
            work: workApplied,
            topic_count: 8,
            output_language: analyzeOutputLang,
            provider: debugProvider ? "mock" : "anthropic",
            model: "",
          },
        );
        setView(res);
        onSessionChange?.(res);
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        setLoadError(msg);
        await refresh();
      }
    });

  const handleImportJson = (file: File) =>
    run("Importar transcripts JSON", async () => {
      setLoadError("");
      setLoading(true);
      try {
        const raw = await file.text();
        let parsed: unknown;
        try {
          parsed = JSON.parse(raw);
        } catch {
          throw new Error("El archivo no es JSON válido.");
        }
        const payload =
          parsed && typeof parsed === "object" && !Array.isArray(parsed)
            ? (parsed as Record<string, unknown>)
            : { videos: parsed };
        const res = await postJson<TranscriptsSessionView>(
          "/api/session/transcripts/import",
          {
            work: workApplied,
            payload,
            source_channel_id: channelId,
          },
        );
        setView(res);
        onSessionChange?.(res);
      } catch (e) {
        setLoadError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    });

  const handleDownloadJson = () =>
    run("Descargar transcripts JSON", async () => {
      const r = await fetch(
        `/api/channels/${encodeURIComponent(channelId)}/transcripts.json`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            work: workApplied,
            video_ids: videoIds,
            limit: 50,
            lang: lang || "es",
          }),
        },
      );
      if (!r.ok) return;
      const text = await r.text();
      const blob = new Blob([text], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `transcripts_${channelId}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    });

  const v = view;
  const validCount = v?.valid_count ?? 0;
  const combinedChars = v?.combined_chars ?? 0;
  const stored = !!v?.stored;
  const analyzeStatus = v?.analyze_status ?? "pending";
  const canAnalyze =
    stored &&
    validCount >= 1 &&
    (v?.ready_to_analyze ||
      analyzeStatus === "error" ||
      analyzeStatus === "completed");

  return (
    <div className="space-y-6">
      {/* Step 1: Load Transcripts */}
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-slate-800">
              1. Cargar Transcripts en Sesión
            </h3>
            <p className="mt-1 max-w-xl text-sm text-slate-500">
              Carga las transcripciones de los vídeos para analizarlas. Puedes
              cargarlas desde el canal o importar un archivo JSON previamente
              descargado.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Btn
              className="bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
              disabled={loading}
              onClick={() => void handleLoadSession()}
            >
              {loading ? "Cargando…" : "Cargar desde Canal"}
            </Btn>
            <Btn
              className="bg-white text-slate-800 ring-1 ring-slate-200 hover:bg-slate-50"
              onClick={() => void handleDownloadJson()}
            >
              Descargar JSON
            </Btn>
            <Btn
              className="bg-white text-slate-800 ring-1 ring-emerald-200 hover:bg-emerald-50"
              disabled={loading}
              onClick={() => importRef.current?.click()}
            >
              Importar JSON
            </Btn>
            <input
              ref={importRef}
              type="file"
              accept=".json,application/json"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (importRef.current) importRef.current.value = "";
                if (f) void handleImportJson(f);
              }}
            />
          </div>
        </div>

        {providerCfg &&
        !providerCfg.data_api_oauth_ready &&
        providerCfg.provider === "data_api" ? (
          <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
            {providerCfg.setup_hint ??
              "Configura OAuth en .env (YOUTUBE_OAUTH_*) y ejecuta: python youtube_oauth_setup.py"}
          </div>
        ) : null}

        <div className="mt-3 grid gap-2 sm:grid-cols-3">
          <div className="rounded-xl border border-slate-100 bg-slate-50/80 px-3 py-2">
            <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
              Transcripts válidos
            </div>
            <div className="mt-0.5 text-sm font-semibold text-slate-900">
              {validCount}
            </div>
            <div className="text-[10px] text-slate-500">
              status ok y texto no vacío
            </div>
          </div>
          <div className="rounded-xl border border-slate-100 bg-slate-50/80 px-3 py-2">
            <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
              Caracteres combinados
            </div>
            <div className="mt-0.5 text-sm font-semibold text-slate-900">
              {combinedChars.toLocaleString()}
            </div>
          </div>
          <div className="rounded-xl border border-slate-100 bg-slate-50/80 px-3 py-2">
            <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
              Estado sesión
            </div>
            <div className="mt-0.5 text-sm font-semibold text-slate-900">
              {v ? sessionReadyLabel(v) : "Pendiente"}
            </div>
            {(v?.has_file ?? stored) ? (
              <div className="text-[10px] text-slate-500">
                JSON en sesión · {v?.video_count ?? 0} vídeo(s)
                {validCount > 0 ? ` · ${validCount} válido(s)` : null}
              </div>
            ) : (
              <div className="text-[10px] text-slate-500">
                Sin carga en sesión
              </div>
            )}
          </div>
        </div>

        {v && sessionReadyHint(v, providerCfg) ? (
          <div
            className={[
              "mt-2 rounded-lg border px-3 py-2 text-xs",
              providerCfg?.data_api_oauth_ready &&
              (v.session_needs_reload || v.youtube_ip_blocked)
                ? "border-sky-200 bg-sky-50 text-sky-900"
                : v.youtube_ip_blocked || (v.blocked_count ?? 0) > 0
                  ? "border-rose-200 bg-rose-50 text-rose-900"
                  : validCount < 1
                    ? "border-amber-200 bg-amber-50 text-amber-900"
                    : "border-indigo-100 bg-white/80 text-slate-600",
            ].join(" ")}
          >
            {sessionReadyHint(v, providerCfg)}
          </div>
        ) : null}

        {loadError ? (
          <div className="mt-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
            {loadError}
          </div>
        ) : null}
      </div>

      {/* Step 2: Analyze */}
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-slate-800">
              2. Analizar Contenido
            </h3>
            <p className="mt-1 max-w-xl text-sm text-slate-500">
              Genera ideas de temas y una plantilla de prompt basada en el
              contenido de las transcripciones.
            </p>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-end gap-4 border-t border-slate-100 pt-4">
          <label className="flex flex-col gap-1">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Idioma de salida (temas + Prompt)
            </span>
            <select
              className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm text-slate-800"
              value={analyzeOutputLang}
              onChange={(e) =>
                setAnalyzeOutputLang(normalizeAnalyzeOutputLang(e.target.value))
              }
              disabled={analyzeStatus === "analyzing"}
            >
              <option value="en">English</option>
              <option value="es">Español</option>
            </select>
          </label>
          <label className="flex cursor-pointer items-center gap-2 rounded-lg p-2 hover:bg-slate-50">
            <input
              type="checkbox"
              className="size-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
              checked={debugProvider}
              onChange={(e) => setDebugProvider(e.target.checked)}
              disabled={analyzeStatus === "analyzing"}
            />
            <span className="text-sm text-slate-600">Usar mock (sin API)</span>
          </label>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-4">
          <div className="text-sm text-slate-600">
            Análisis LLM:{" "}
            <span
              className={
                analyzeStatus === "analyzing"
                  ? "font-semibold text-violet-600"
                  : analyzeStatus === "completed"
                    ? "font-semibold text-emerald-700"
                    : analyzeStatus === "error"
                      ? "font-semibold text-rose-600"
                      : "font-semibold text-amber-700"
              }
            >
              {sessionLoadLabel(analyzeStatus)}
            </span>
            {analyzeStatus === "pending" && validCount >= 1 ? (
              <span className="ml-1 text-slate-500">(aún no analizado)</span>
            ) : null}
            {analyzeStatus === "completed" && v?.topics_count != null ? (
              <span className="ml-2 text-slate-500">
                · {v.topics_count} temas · plantilla inferida
                {v.analyze_output_language
                  ? ` · ${v.analyze_output_language === "en" ? "EN" : "ES"}`
                  : null}
              </span>
            ) : null}
          </div>
          <Btn
            className="bg-violet-600 text-white hover:bg-violet-500 disabled:bg-slate-300 disabled:text-slate-500"
            disabled={!canAnalyze || analyzeStatus === "analyzing"}
            onClick={() => void handleAnalyze()}
          >
            {analyzeStatus === "analyzing" ? "Analizando…" : "Analizar"}
          </Btn>
        </div>

        {v?.analyze_error ? (
          <div className="mt-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
            {v.analyze_error}
          </div>
        ) : null}
      </div>
    </div>
  );
}
