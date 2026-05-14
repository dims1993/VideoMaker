/**
 * Interruptor estilo iOS: track con padding, knob que recorre el hueco sin solapar bordes.
 */
export function IosSwitch({
  checked,
  onChange,
  disabled,
  "aria-label": ariaLabel,
  id,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  disabled?: boolean;
  "aria-label": string;
  id?: string;
}) {
  return (
    <button
      id={id}
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      disabled={disabled}
      onClick={() => !disabled && onChange(!checked)}
      className={[
        "relative box-border flex h-8 w-14 shrink-0 cursor-pointer items-center overflow-hidden rounded-full p-[3px]",
        "ring-1 ring-inset ring-black/20 transition-[background-color,opacity,filter] duration-200 ease-out",
        "focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/90 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900",
        checked ? "bg-emerald-500 shadow-[inset_0_1px_0_rgba(255,255,255,0.35)]" : "bg-slate-600 shadow-[inset_0_2px_4px_rgba(0,0,0,0.22)]",
        disabled ? "cursor-not-allowed opacity-45" : "enabled:active:brightness-95",
      ].join(" ")}
    >
      <span
        aria-hidden
        className={[
          "h-[26px] w-[26px] shrink-0 rounded-full border border-slate-200/90 bg-white shadow-md",
          "transition-transform duration-200 ease-[cubic-bezier(0.25,0.85,0.3,1.08)] will-change-transform",
          checked ? "translate-x-6" : "translate-x-0",
        ].join(" ")}
      />
    </button>
  );
}
