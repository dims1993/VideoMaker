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
      className="fixed inset-y-0 left-[280px] right-0 z-[200] flex items-stretch justify-center bg-slate-950/55 p-2 sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="flex h-[min(calc(100vh-1rem),920px)] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
        <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
          <span className="text-sm font-semibold text-slate-900">{title}</span>
          <div className="flex flex-wrap gap-2">
            <Btn
              type="button"
              className="bg-slate-900 text-white hover:bg-slate-800"
              onClick={() => {
                onSave(draft);
                onClose();
              }}
            >
              Guardar
            </Btn>
            <Btn
              type="button"
              className="bg-white text-slate-800 ring-1 ring-slate-200 hover:bg-slate-50"
              onClick={onClose}
            >
              Cerrar sin guardar
            </Btn>
          </div>
        </div>

        <textarea
          ref={taRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          className="min-h-0 flex-1 resize-none border-0 !bg-white px-4 py-3 font-mono text-sm leading-relaxed !text-slate-900 outline-none focus:ring-0"
          spellCheck={false}
        />

        <p className="shrink-0 border-t border-slate-100 px-4 py-2 text-[11px] leading-snug text-slate-500">
          <kbd className="rounded bg-slate-100 px-1 font-mono text-[10px]">Esc</kbd>
          {" "}cierra · {draft.length.toLocaleString()} caracteres
        </p>
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
  disabled = false,
  disabledTitle,
}: {
  label?: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  modalTitle: string;
  variant?: "form" | "output" | "outputLight" | "inferred";
  /** Solo lectura: no abre el editor a pantalla completa. */
  disabled?: boolean;
  /** Tooltip cuando está disabled (si no se pasa, mensaje genérico). */
  disabledTitle?: string;
}) {
  const [modalOpen, setModalOpen] = useState(false);
  const fullText = value.trim();
  const previewLimit =
    variant === "output" || variant === "outputLight" || variant === "inferred" ? 600 : 160;
  const preview = fullText.slice(0, previewLimit);
  const hasMore = fullText.length > previewLimit;

  const baseContainerClass =
    variant === "output"
      ? "group relative min-h-[120px] w-full rounded-xl border border-slate-600 bg-slate-800 px-3 py-2 text-left shadow-inner outline-none transition"
      : variant === "outputLight"
        ? "group relative min-h-[120px] w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-left shadow-inner outline-none transition"
        : variant === "inferred"
          ? "group relative min-h-[120px] w-full rounded-xl border border-violet-200/90 bg-white px-3 py-2 text-left shadow-sm outline-none transition"
          : "group relative w-full rounded-lg border border-slate-600 bg-slate-700 px-3 py-2 transition-all";

  const interactiveClass = disabled
    ? " cursor-not-allowed opacity-50"
    : variant === "output"
      ? " cursor-pointer hover:border-slate-500"
      : variant === "outputLight"
        ? " cursor-pointer hover:border-slate-300"
        : variant === "inferred"
          ? " cursor-pointer hover:border-violet-300 hover:shadow-sm"
          : " cursor-pointer hover:border-slate-400 hover:shadow-sm";

  const containerClass = `${baseContainerClass}${interactiveClass}`;

  const textClass =
    variant === "output"
      ? `block max-h-[280px] overflow-y-auto whitespace-pre-wrap break-words pr-10 font-mono text-xs leading-relaxed ${preview ? "text-slate-200" : "text-slate-500"}`
      : variant === "outputLight" || variant === "inferred"
        ? `block max-h-[280px] overflow-y-auto whitespace-pre-wrap break-words pr-10 font-mono text-xs leading-relaxed ${preview ? "text-slate-900" : "text-slate-500"}`
      : `block max-h-[5.5rem] overflow-hidden whitespace-pre-wrap break-words pr-10 font-mono text-xs leading-snug ${
          preview ? "text-slate-300" : "text-slate-500"
        }`;

  return (
    <>
      {label && <Label>{label}</Label>}
      <div
        role={disabled ? undefined : "button"}
        tabIndex={disabled ? undefined : 0}
        aria-disabled={disabled || undefined}
        aria-label={disabled ? undefined : `Abrir ${modalTitle} a pantalla completa`}
        className={containerClass}
        onClick={() => { if (!disabled) setModalOpen(true); }}
        onKeyDown={(e) => { if (!disabled && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); setModalOpen(true); } }}
        title={
          disabled
            ? (disabledTitle ?? "No disponible")
            : "Clic para editar a pantalla completa"
        }
      >
        <span className={textClass}>
          {preview
            ? `${preview}${hasMore ? "…" : ""}`
            : placeholder || "Vacío — clic para editar"}
        </span>
        {!disabled && (
        <span className="absolute right-2 top-2 rounded bg-slate-600 px-1.5 py-0.5 text-[10px] text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity">
          ✎ editar
        </span>
        )}
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
