import { useEffect, useRef, useState } from "react";
import { Btn } from "./Btn";
import { Label } from "./Form";

// ── Fullscreen text editor modal ──────────────────────────────────────────
function FullscreenEditor({
  title,
  value,
  onSave,
  onClose,
}: {
  title: string;
  value: string;
  onSave: (v: string) => void;
  onClose: () => void;
}) {
  const [draft, setDraft] = useState(value);
  const taRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    taRef.current?.focus();
  }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col bg-black/50 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="flex flex-1 flex-col bg-white shadow-2xl m-4 rounded-2xl overflow-hidden">
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
          <span className="text-sm font-semibold text-slate-800">{title}</span>
          <div className="flex items-center gap-1.5 text-[10px] text-slate-400">
            <kbd className="rounded bg-slate-100 px-1.5 py-0.5 font-mono">Esc</kbd>
            <span>cerrar sin guardar</span>
          </div>
        </div>

        <textarea
          ref={taRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          className="flex-1 resize-none px-4 py-3 font-mono text-sm text-slate-800 focus:outline-none"
          spellCheck={false}
        />

        <div className="flex items-center justify-between border-t border-slate-200 px-4 py-3 bg-slate-50">
          <span className="text-[11px] text-slate-400">
            {draft.length.toLocaleString()} caracteres
          </span>
          <div className="flex gap-2">
            <Btn
              type="button"
              className="bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"
              onClick={onClose}
            >
              Cancelar
            </Btn>
            <Btn
              type="button"
              className="bg-slate-900 text-white hover:bg-slate-800"
              onClick={() => { onSave(draft); onClose(); }}
            >
              Guardar
            </Btn>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Expandable textarea ───────────────────────────────────────────────────
/**
 * variant "form"   → bg-slate-700 rounded-lg  (estilo campo de formulario, usado en Prompt)
 * variant "output" → bg-slate-800 rounded-xl shadow-inner (estilo cuadro de salida, usado en Script Writer)
 */
export function ExpandableTextArea({
  label,
  value,
  onChange,
  placeholder,
  modalTitle,
  variant = "form",
}: {
  label?: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  modalTitle: string;
  variant?: "form" | "output";
}) {
  const [modalOpen, setModalOpen] = useState(false);
  const preview = value.trim().slice(0, 160);

  const containerClass =
    variant === "output"
      ? "group relative w-full cursor-pointer rounded-xl border border-slate-600 bg-slate-800 px-3 py-2 text-left shadow-inner outline-none transition hover:border-slate-500"
      : "group relative cursor-pointer rounded-lg border border-slate-600 bg-slate-700 px-3 py-2 hover:border-slate-400 hover:shadow-sm transition-all";

  return (
    <>
      {label && <Label>{label}</Label>}
      <div
        role="button"
        tabIndex={0}
        aria-label={`Abrir ${modalTitle} a pantalla completa`}
        className={containerClass}
        onClick={() => setModalOpen(true)}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setModalOpen(true); } }}
        title="Clic para editar a pantalla completa"
      >
        {preview ? (
          <pre className="whitespace-pre-wrap font-mono text-xs text-slate-300 leading-snug line-clamp-4">
            {preview}{value.trim().length > 160 ? "…" : ""}
          </pre>
        ) : (
          <span className="text-xs text-slate-500 italic">{placeholder ?? "Vacío — clic para editar"}</span>
        )}
        <span className="absolute right-2 top-2 rounded bg-slate-600 px-1.5 py-0.5 text-[10px] text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity">
          ✎ editar
        </span>
      </div>

      {modalOpen && (
        <FullscreenEditor
          title={modalTitle}
          value={value}
          onSave={onChange}
          onClose={() => setModalOpen(false)}
        />
      )}
    </>
  );
}
