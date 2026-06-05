import { useState } from "react";
import {
  formatProductionResetMessage,
  runProductionReset,
  type ProductionResetScope,
} from "./productionReset";

export function ProductionResetButton({
  workApplied,
  scope,
  label,
  className = "",
  disabled = false,
  onDone,
}: {
  workApplied: string;
  scope: ProductionResetScope;
  label: string;
  className?: string;
  disabled?: boolean;
  onDone?: (message: string) => void | Promise<void>;
}) {
  const [busy, setBusy] = useState(false);

  return (
    <button
      type="button"
      disabled={disabled || busy}
      className={
        className ||
        "rounded-lg border border-rose-400/60 bg-rose-950/30 px-2.5 py-1.5 text-[11px] font-medium text-rose-200 hover:bg-rose-950/50 disabled:cursor-not-allowed disabled:opacity-40"
      }
      onClick={async () => {
        setBusy(true);
        try {
          const res = await runProductionReset(workApplied, scope);
          if (!res) return;
          await onDone?.(formatProductionResetMessage(res));
        } catch (e) {
          await onDone?.(e instanceof Error ? e.message : "Error al reiniciar");
        } finally {
          setBusy(false);
        }
      }}
    >
      {busy ? "Reiniciando…" : label}
    </button>
  );
}
