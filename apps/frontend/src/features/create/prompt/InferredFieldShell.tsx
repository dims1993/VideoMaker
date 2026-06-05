import type { ReactNode } from "react";
import { INFERRED_SECTION_LABEL, inferredPanelClass } from "./promptFieldStyles";

export function InferredFieldShell({
  children,
  highlightLevel = null,
  showSectionLabel = false,
  className = "",
}: {
  children: ReactNode;
  highlightLevel?: "missing" | "warning" | null;
  showSectionLabel?: boolean;
  className?: string;
}) {
  return (
    <div
      className={[inferredPanelClass(highlightLevel), className].filter(Boolean).join(" ")}
    >
      {showSectionLabel ? (
        <p className={`${INFERRED_SECTION_LABEL} mb-2`}>Inferido de transcripciones</p>
      ) : null}
      {children}
    </div>
  );
}
