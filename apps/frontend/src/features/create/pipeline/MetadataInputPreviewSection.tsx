import { useCallback, useEffect, useState } from "react";
import { Btn } from "../../../components/ui";
import { readApiError } from "../../../services/api";

export type MetadataInputPreview = {
  ready: boolean;
  missing?: string[];
  lang: {
    effective: string;
    label: string;
    session_raw?: string | null;
    topic_generator?: string | null;
  };
  topic: {
    selected_index?: number | null;
    title?: string | null;
    angle?: string | null;
    from_topic_generator?: boolean;
    title_policy: string;
  };
  session: {
    keywords?: string | null;
    context?: string | null;
    minutes?: number | null;
  };
  settings: {
    target_platform: string;
    target_keywords_effective?: string | null;
    target_keywords_source?: string | null;
    system_prompt_custom?: boolean;
  };
  script: {
    source: string;
    exists: boolean;
    total_chars: number;
    chars_sent_to_llm: number;
    truncated: boolean;
    max_chars: number;
  };
  prompts: {
    system: string;
    user: string;
    user_length: number;
  };
  checks?: Array<{ level: string; id: string; message: string }>;
  llm?: {
    provider: string;
    model?: string | null;
    api?: string;
    session_provider_ignored?: boolean;
  };
};

export function MetadataInputPreviewSection({
  workApplied,
  lang,
  kw,
  ctx,
  minutes,
  provider,
  model,
  targetPlatform,
  refreshKey = 0,
  onReadyChange,
}: {
  workApplied: string;
  lang: string;
  kw: string;
  ctx: string;
  minutes: number;
  provider: string;
  model: string;
  targetPlatform: string;
  refreshKey?: number;
  onReadyChange?: (ready: boolean) => void;
}) {
  const [preview, setPreview] = useState<MetadataInputPreview | null>(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [showPrompts, setShowPrompts] = useState(false);

  const loadPreview = useCallback(async () => {
    setLoading(true);
    try {
      const q = new URLSearchParams({
        work: workApplied,
        lang,
        keywords: kw,
        context: ctx,
        minutes: String(minutes),
        provider,
        model,
      });
      const r = await fetch(`/api/pipeline/metadata-input-preview?${q}`);
      if (!r.ok) throw new Error((await readApiError(r)) || r.statusText);
      const data = (await r.json()) as MetadataInputPreview;
      setPreview(data);
      const hasError = (data.checks ?? []).some((c) => c.level === "error");
      onReadyChange?.(data.ready && !hasError);
    } catch (e) {
      console.error("metadata input preview", e);
      setPreview(null);
    } finally {
      setLoading(false);
    }
  }, [workApplied, lang, kw, ctx, minutes, provider, model, refreshKey, onReadyChange]);

  useEffect(() => {
    const t = window.setTimeout(() => void loadPreview(), 300);
    return () => window.clearTimeout(t);
  }, [loadPreview]);

  const seoKeywordsLabel = (preview: MetadataInputPreview) => {
    const src = preview.settings.target_keywords_source ?? "infer_from_script";
    const eff = preview.settings.target_keywords_effective;
    if (src === "manual" && eff) {
      return `Override manual: ${eff}`;
    }
    if (src === "inferred" && eff) {
      return `Referencia anterior en disco (no se envía al LLM): ${eff}`;
    }
    return "Vacías — la IA inferirá tags SEO del guion (platform.tags).";
  };

  const titlePolicyLabel = (policy: string) => {
    if (policy === "canonical_from_topic_generator") {
      return "Título fijado desde Topic Generator (la IA solo hace variantes SEO y el resto de campos).";
    }
    if (policy === "session_keywords_as_title") {
      return "Título tomado de keywords de sesión (sin tema TG seleccionado).";
    }
    return "Sin título canónico — la IA propone el título principal.";
  };

  return (
    <div className="overflow-hidden rounded-xl border border-sky-200 bg-sky-50/40 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-sky-100 px-4 py-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-800">
            Entrada a Metadata (preview)
          </h3>
          <p className="text-[11px] text-slate-600">
            Lo que recibirá la IA al generar — sin llamar al modelo.
          </p>
        </div>
        <Btn
          type="button"
          className="bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"
          onClick={() => void loadPreview()}
          disabled={loading}
        >
          {loading ? "Actualizando…" : "Actualizar"}
        </Btn>
      </div>

      <div className="space-y-3 p-4 text-sm text-slate-800">
        {!preview && !loading ? (
          <p className="text-slate-500">No se pudo cargar el preview.</p>
        ) : null}

        {preview?.checks && preview.checks.length > 0 ? (
          <ul className="space-y-1.5">
            {preview.checks.map((c) => (
              <li
                key={c.id}
                className={[
                  "rounded-lg px-3 py-2 text-xs",
                  c.level === "error"
                    ? "border border-rose-200 bg-rose-50 text-rose-900"
                    : c.level === "warning"
                      ? "border border-amber-200 bg-amber-50 text-amber-900"
                      : c.level === "ok"
                        ? "border border-emerald-200 bg-emerald-50 text-emerald-900"
                        : "border border-slate-200 bg-white text-slate-700",
                ].join(" ")}
              >
                {c.message}
              </li>
            ))}
          </ul>
        ) : null}

        {preview && !preview.ready ? (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
            Falta el guion ({preview.script?.source ?? "guion.txt / pipeline/script.txt"}).
            Ejecuta <strong>Script Writer</strong> antes de generar metadatos.
          </div>
        ) : null}

        {preview?.ready ? (
          <>
            <dl className="grid gap-2 text-xs sm:grid-cols-2">
              <div>
                <dt className="font-semibold text-slate-500">Idioma de salida</dt>
                <dd>
                  {preview.lang.label} ({preview.lang.effective})
                  {preview.lang.session_raw &&
                  preview.lang.session_raw !== preview.lang.effective ? (
                    <span className="text-slate-500">
                      {" "}
                      · sesión raw: {preview.lang.session_raw}
                    </span>
                  ) : null}
                </dd>
              </div>
              <div>
                <dt className="font-semibold text-slate-500">Plataforma</dt>
                <dd>{targetPlatform || preview.settings.target_platform}</dd>
              </div>
              <div className="sm:col-span-2">
                <dt className="font-semibold text-slate-500">LLM (metadata)</dt>
                <dd className="text-[11px] leading-snug text-slate-700">
                  OpenAI API · modelo{" "}
                  <strong>{preview.llm?.model ?? "gpt-4o-mini"}</strong>
                  {preview.llm?.session_provider_ignored
                    ? " (independiente del proveedor de Script Writer)"
                    : null}
                </dd>
              </div>
              <div className="sm:col-span-2">
                <dt className="font-semibold text-slate-500">Keywords SEO (metadata)</dt>
                <dd className="text-[11px] leading-snug text-slate-700">
                  {seoKeywordsLabel(preview)}
                </dd>
              </div>
              <div className="sm:col-span-2">
                <dt className="font-semibold text-slate-500">Título canónico</dt>
                <dd className="font-medium text-slate-900">
                  {preview.topic.title ?? "—"}
                </dd>
                <dd className="mt-0.5 text-[11px] text-slate-600">
                  {titlePolicyLabel(preview.topic.title_policy)}
                </dd>
              </div>
              {preview.topic.angle ? (
                <div className="sm:col-span-2">
                  <dt className="font-semibold text-slate-500">Ángulo</dt>
                  <dd>{preview.topic.angle}</dd>
                </div>
              ) : null}
              <div>
                <dt className="font-semibold text-slate-500">Guion</dt>
                <dd>
                  {preview.script.source} · {preview.script.total_chars.toLocaleString()}{" "}
                  caracteres
                  {preview.script.truncated
                    ? ` (enviados ${preview.script.chars_sent_to_llm.toLocaleString()} / máx. ${preview.script.max_chars.toLocaleString()})`
                    : null}
                </dd>
              </div>
              <div>
                <dt className="font-semibold text-slate-500">Duración sesión</dt>
                <dd>{preview.session.minutes ?? "—"} min</dd>
              </div>
            </dl>

            <button
              type="button"
              className="text-xs font-medium text-sky-700 hover:text-sky-900"
              onClick={() => setExpanded((v) => !v)}
            >
              {expanded ? "Ocultar detalle de sesión" : "Ver detalle de sesión y ajustes"}
            </button>
            {expanded ? (
              <pre className="max-h-40 overflow-auto rounded-lg border border-slate-200 bg-white p-2 font-mono text-[10px] text-slate-700">
                {JSON.stringify(
                  {
                    session: preview.session,
                    settings: preview.settings,
                    topic_index: preview.topic.selected_index,
                  },
                  null,
                  2,
                )}
              </pre>
            ) : null}

            <p className="text-[11px] text-slate-500">
              Instrucciones al modelo: compactas en inglés; el JSON de salida va en{" "}
              <strong>{preview.lang.label}</strong>.
            </p>
            <button
              type="button"
              className="text-xs font-medium text-sky-700 hover:text-sky-900"
              onClick={() => setShowPrompts((v) => !v)}
            >
              {showPrompts ? "Ocultar prompts" : "Ver system + user prompt"}
            </button>
            {showPrompts ? (
              <div className="space-y-2">
                <div>
                  <div className="mb-1 text-[10px] font-semibold uppercase text-slate-500">
                    System
                  </div>
                  <pre className="max-h-48 overflow-auto rounded-lg border border-slate-200 bg-white p-2 font-mono text-[10px] leading-relaxed text-slate-700">
                    {preview.prompts.system}
                  </pre>
                </div>
                <div>
                  <div className="mb-1 text-[10px] font-semibold uppercase text-slate-500">
                    User ({preview.prompts.user_length.toLocaleString()} chars)
                  </div>
                  <pre className="max-h-64 overflow-auto rounded-lg border border-slate-200 bg-white p-2 font-mono text-[10px] leading-relaxed text-slate-700">
                    {preview.prompts.user}
                  </pre>
                </div>
              </div>
            ) : null}
          </>
        ) : null}
      </div>
    </div>
  );
}
