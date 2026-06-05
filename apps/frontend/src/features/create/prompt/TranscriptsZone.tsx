import { useEffect, useRef, useState } from "react";
import { Btn } from "../../../components/ui";
import {
  extractTranscriptFile,
  TRANSCRIPT_ACCEPT_ATTR,
  TRANSCRIPT_FILE_EXTENSIONS,
} from "./transcriptFileParse";

export type TranscriptAnalyzeStatus =
  | "idle"
  | "ready"
  | "analyzing"
  | "completed";

export type LoadedTranscriptFile = {
  id: string;
  name: string;
  chars: number;
};

type TranscriptsZoneProps = {
  disabled?: boolean;
  onAnalysisComplete: (data: Record<string, unknown>) => void;
  /** Texto combinado actual (p. ej. Topic Generator sin analizar aún). */
  onCombinedTextChange?: (text: string) => void;
  /** Oculta el botón de analizar (solo carga de archivos). */
  analyzeMode?: boolean;
};

function combineDocuments(docs: { name: string; text: string }[]): string {
  return docs
    .map((d) => {
      const body = d.text.trim();
      return body ? `--- ${d.name} ---\n${body}` : "";
    })
    .filter(Boolean)
    .join("\n\n");
}

const STATUS_LABEL: Record<TranscriptAnalyzeStatus, string> = {
  idle: "Sin archivos cargados",
  ready: "Pendiente — listo para analizar",
  analyzing: "Analizando…",
  completed: "Completado — revisa los campos antes de guardar",
};

export function TranscriptsZone({
  disabled,
  onAnalysisComplete,
  onCombinedTextChange,
  analyzeMode = true,
}: TranscriptsZoneProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [documents, setDocuments] = useState<
    { id: string; name: string; text: string }[]
  >([]);
  const [fileList, setFileList] = useState<LoadedTranscriptFile[]>([]);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [analyzeStatus, setAnalyzeStatus] =
    useState<TranscriptAnalyzeStatus>("idle");
  const [error, setError] = useState("");

  const combinedText = combineDocuments(documents);
  const fileCount = fileList.length;

  useEffect(() => {
    onCombinedTextChange?.(combinedText);
  }, [combinedText, onCombinedTextChange]);

  const handleLoadFiles = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const picked = Array.from(e.target.files ?? []);
    if (fileRef.current) fileRef.current.value = "";
    if (!picked.length) return;
    setError("");
    setLoadingFiles(true);
    try {
      const newDocs: { id: string; name: string; text: string }[] = [];
      const newMeta: LoadedTranscriptFile[] = [];
      for (const file of picked) {
        const { name, text } = await extractTranscriptFile(file);
        const trimmed = text.trim();
        if (!trimmed) {
          throw new Error(`${name}: no se extrajo texto`);
        }
        const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
        newDocs.push({ id, name, text: trimmed });
        newMeta.push({ id, name, chars: trimmed.length });
      }
      setDocuments((prev) => [...prev, ...newDocs]);
      setFileList((prev) => [...prev, ...newMeta]);
      setAnalyzeStatus("ready");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error desconocido");
    } finally {
      setLoadingFiles(false);
    }
  };

  const removeFile = (id: string) => {
    setDocuments((prev) => prev.filter((d) => d.id !== id));
    setFileList((prev) => {
      const next = prev.filter((f) => f.id !== id);
      if (next.length === 0) {
        setAnalyzeStatus("idle");
      } else if (analyzeStatus === "completed") {
        setAnalyzeStatus("ready");
      }
      return next;
    });
  };

  const clearAll = () => {
    setDocuments([]);
    setFileList([]);
    setAnalyzeStatus("idle");
    setError("");
  };

  const handleAnalyze = async () => {
    if (!combinedText.trim()) return;
    setError("");
    setAnalyzeStatus("analyzing");
    try {
      const res = await fetch(
        "/api/prompt-templates/generate-from-transcript",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ transcript_text: combinedText }),
        },
      );
      if (!res.ok) {
        const j = (await res.json().catch(() => ({}))) as { detail?: string };
        throw new Error(j.detail ?? `Error ${res.status}`);
      }
      const data = (await res.json()) as Record<string, unknown>;
      onAnalysisComplete(data);
      setAnalyzeStatus("completed");
    } catch (err) {
      setAnalyzeStatus(fileCount > 0 ? "ready" : "idle");
      setError(err instanceof Error ? err.message : "Error desconocido");
    }
  };

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm shadow-slate-200/50">
      <div className="border-b border-slate-200 bg-slate-50 px-4 py-3.5 sm:px-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <span
                className="h-2 w-2 rounded-full bg-violet-500"
                aria-hidden
              />
              <h3 className="text-[15px] font-semibold tracking-tight text-slate-900">
                ZONA DE TRANSCRIPTS
              </h3>
            </div>
            <p className="mt-1 max-w-xl text-[12px] leading-relaxed text-slate-500">
              Sube varios archivos, revisa la lista y luego analiza.
            </p>
          </div>
          <span className="shrink-0 rounded-lg border border-violet-200 bg-violet-50 px-2 py-0.5 text-[10px] font-medium text-violet-700">
            Claude Sonnet
          </span>
        </div>
      </div>
      <div className="space-y-3 p-4 sm:p-5">
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            disabled={disabled || loadingFiles}
            onClick={() => fileRef.current?.click()}
            className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm transition-colors hover:bg-slate-50 disabled:opacity-50"
          >
            {loadingFiles
              ? "Leyendo archivos…"
              : "Cargar transcripts del canal"}
          </button>
          <input
            ref={fileRef}
            type="file"
            accept={TRANSCRIPT_ACCEPT_ATTR}
            multiple
            className="hidden"
            disabled={disabled || loadingFiles}
            onChange={handleLoadFiles}
          />
          {fileCount > 0 ? (
            <button
              type="button"
              disabled={disabled || loadingFiles}
              onClick={clearAll}
              className="text-xs text-slate-500 hover:text-slate-800"
            >
              Vaciar lista
            </button>
          ) : null}
          <span className="text-xs text-slate-400">
            {TRANSCRIPT_FILE_EXTENSIONS.join(", ")} · múltiples archivos
          </span>
        </div>

        {fileCount > 0 ? (
          <ul className="max-h-32 overflow-y-auto rounded-xl border border-slate-200 bg-slate-50 divide-y divide-slate-200">
            {fileList.map((f) => (
              <li
                key={f.id}
                className="flex items-center justify-between gap-2 px-3 py-1.5 text-xs"
              >
                <span className="truncate text-slate-700" title={f.name}>
                  {f.name}
                  <span className="ml-2 text-slate-400">
                    {f.chars.toLocaleString()} chars
                  </span>
                </span>
                <button
                  type="button"
                  disabled={disabled || analyzeStatus === "analyzing"}
                  onClick={() => removeFile(f.id)}
                  className="shrink-0 text-slate-400 hover:text-slate-700"
                  aria-label={`Quitar ${f.name}`}
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        ) : null}

        {combinedText ? (
          <p className="text-[11px] text-slate-500">
            Texto combinado: {combinedText.length.toLocaleString()} caracteres
          </p>
        ) : null}

        {analyzeMode ? (
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-3">
            <div className="flex items-center gap-2 text-xs">
              <span className="text-slate-500">Estado:</span>
              <span
                className={
                  analyzeStatus === "analyzing"
                    ? "text-violet-600 animate-pulse"
                    : analyzeStatus === "completed"
                      ? "text-emerald-600"
                      : analyzeStatus === "ready"
                        ? "text-amber-600"
                        : "text-slate-400"
                }
              >
                {STATUS_LABEL[analyzeStatus]}
              </span>
            </div>
            <Btn
              type="button"
              className="bg-violet-600 text-white hover:bg-violet-500 disabled:opacity-50"
              disabled={
                disabled ||
                loadingFiles ||
                analyzeStatus === "analyzing" ||
                !combinedText.trim()
              }
              onClick={handleAnalyze}
            >
              {analyzeStatus === "analyzing"
                ? "Analizando…"
                : "Analizar y rellenar campos"}
            </Btn>
          </div>
        ) : null}

        {error ? (
          <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
            {error}
          </div>
        ) : null}

        <p className="text-[10px] text-slate-400">
          Requiere{" "}
          <code className="rounded bg-slate-100 px-1 text-slate-600">
            ANTHROPIC_API_KEY
          </code>{" "}
          en .env. Los campos rellenados quedarán marcados como inferidos hasta
          que los revises o guardes el template.
        </p>
      </div>
    </div>
  );
}
