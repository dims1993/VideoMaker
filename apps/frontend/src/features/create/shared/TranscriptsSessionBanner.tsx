import { useEffect, useState } from "react";
import {
  fetchTranscriptsSession,
  sessionLoadLabel,
  type TranscriptsSessionView,
} from "../../analyze/transcriptsSession";

export function TranscriptsSessionBanner({
  workApplied,
}: {
  workApplied: string;
}) {
  const [view, setView] = useState<TranscriptsSessionView | null>(null);

  // ✅ Restaurar sesión guardada automáticamente
  useEffect(() => {
    fetch(`/api/session/transcripts?work=output/ui_session`)
      .then((r) => r.json())
      .then((data) => {
        if (data.stored) {
          // la sesión ya existe en disco, el banner la mostrará automáticamente
          setView(data);
        }
      })
      .catch(() => {});
  }, []);

  // ✅ Refrescar usando workApplied actual
  useEffect(() => {
    let cancelled = false;

    void fetchTranscriptsSession(workApplied).then((v) => {
      if (!cancelled) {
        setView(v);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [workApplied]);

  if (!view?.stored) {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
        No hay <strong>transcripts_session</strong> en esta carpeta de trabajo.
        Cárgalos desde Analyse → canal favorito → «Transcripts JSON → sesión» y
        pulsa Analizar.
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-violet-200 bg-violet-50 px-3 py-2 text-xs text-violet-900">
      <strong>transcripts_session</strong> activa: {view.valid_count} transcript
      {view.valid_count === 1 ? "" : "s"} válido
      {view.valid_count === 1 ? "" : "s"} ·{" "}
      {view.combined_chars.toLocaleString()} caracteres · análisis:{" "}
      {sessionLoadLabel(view.analyze_status)}
      {view.analyze_status === "completed"
        ? " — no se reenvía el texto completo; usa los resultados guardados."
        : view.ready_to_analyze
          ? " — completa el análisis en Analyse antes de generar de nuevo."
          : ""}
    </div>
  );
}
