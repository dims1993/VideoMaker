import { useCallback, useEffect, useRef, useState } from "react";
import type { RunFn } from "../types";
import {
  deletePacingDirectivePreset,
  fetchPacingDirectivePresets,
  renamePacingDirectivePreset,
  type PacingDirectivePreset,
} from "./pacingPassDirectivePresets";

export function PacingDirectivePresetsBar({
  disabled,
  onApply,
  refreshToken = "",
  run,
}: {
  disabled?: boolean;
  onApply: (text: string) => void;
  /** Incrementar tras guardar una directriz nueva. */
  refreshToken?: string;
  run?: RunFn;
}) {
  const [presets, setPresets] = useState<PacingDirectivePreset[]>([]);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const renameInputRef = useRef<HTMLInputElement>(null);
  const clickTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async () => {
    try {
      setPresets(await fetchPacingDirectivePresets());
    } catch {
      setPresets([]);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load, refreshToken]);

  useEffect(() => {
    if (renamingId && renameInputRef.current) {
      renameInputRef.current.focus();
      renameInputRef.current.select();
    }
  }, [renamingId]);

  const commitRename = async (id: string) => {
    const name = renameValue.trim();
    setRenamingId(null);
    if (!name) return;
    const task = async () => {
      await renamePacingDirectivePreset(id, name);
      await load();
    };
    if (run) await run("Renombrar directriz", task);
    else await task();
  };

  if (presets.length === 0 && !renamingId) {
    return (
      <p className="text-[11px] text-slate-500">
        Sin directrices guardadas. Usa <strong>Guardar directriz</strong> para crear una burbuja reutilizable
        (p. ej. directriz01).
      </p>
    );
  }

  return (
    <div className="flex flex-wrap gap-2 pt-1">
      {presets.map((p) =>
        renamingId === p.id ? (
          <input
            key={p.id}
            ref={renameInputRef}
            type="text"
            className="rounded-full border border-violet-300 bg-white px-3 py-1 text-[11px] text-slate-800 shadow-sm outline-none ring-2 ring-violet-100"
            value={renameValue}
            maxLength={48}
            onChange={(e) => setRenameValue(e.target.value)}
            onBlur={() => void commitRename(p.id)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                void commitRename(p.id);
              }
              if (e.key === "Escape") {
                setRenamingId(null);
              }
            }}
          />
        ) : (
          <span key={p.id} className="group relative inline-flex max-w-full">
            <button
              type="button"
              disabled={disabled}
              title={`Cargar «${p.name}» en el cuadro de texto. Doble clic para renombrar.`}
              className="inline-flex max-w-[220px] items-center gap-1 rounded-full border border-violet-200 bg-violet-50 px-3 py-1 text-[11px] font-medium text-violet-900 shadow-sm transition hover:border-violet-300 hover:bg-violet-100 disabled:opacity-40"
              onClick={() => {
                if (disabled) return;
                if (clickTimerRef.current) clearTimeout(clickTimerRef.current);
                clickTimerRef.current = setTimeout(() => {
                  clickTimerRef.current = null;
                  onApply(p.text);
                }, 220);
              }}
              onDoubleClick={(e) => {
                e.preventDefault();
                if (disabled) return;
                if (clickTimerRef.current) {
                  clearTimeout(clickTimerRef.current);
                  clickTimerRef.current = null;
                }
                setRenamingId(p.id);
                setRenameValue(p.name);
              }}
            >
              <span className="truncate">{p.name}</span>
            </button>
            {!disabled ? (
              <button
                type="button"
                aria-label={`Eliminar ${p.name}`}
                className="absolute -right-1 -top-1 hidden h-4 w-4 items-center justify-center rounded-full bg-slate-600 text-[10px] leading-none text-white group-hover:flex"
                onClick={(e) => {
                  e.stopPropagation();
                  if (!confirm(`¿Eliminar la directriz «${p.name}»?`)) return;
                  const task = async () => {
                    await deletePacingDirectivePreset(p.id);
                    await load();
                  };
                  if (run) void run("Eliminar directriz", task);
                  else void task();
                }}
              >
                ×
              </button>
            ) : null}
          </span>
        ),
      )}
    </div>
  );
}
