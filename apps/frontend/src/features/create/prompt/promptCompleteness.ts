import { hasOutputStructureHeader } from "./promptInstructions";
import type { PromptLibraryStore } from "./usePromptLibrary";

const MIN_MANUAL_NARRATIVE_CHARS = 40;

/** Modelo base slim (placeholders de sesión) o plantilla legacy con cabecera ## Estructura… */
function isOutputStructureAcceptable(out: string): boolean {
  const t = out.trim();
  if (!t) return false;
  if (t.includes("{{LANGUAGE_CODE}}")) return true;
  if (hasOutputStructureHeader(t)) return true;
  return t.length >= 60;
}

function isUserNarrativeAcceptable(narr: string): boolean {
  return narr.trim().length >= MIN_MANUAL_NARRATIVE_CHARS;
}

export type PromptSectionId =
  | "catalog"
  | "transcripts"
  | "params"
  | "system"
  | "user"
  | "topic";

export type PromptMissingField = {
  id: string;
  sectionId: PromptSectionId;
  sectionTitle: string;
  label: string;
  /** id del PipelineSection a abrir */
  sectionDomId: string;
};

export type PromptValidationResult = {
  missing: PromptMissingField[];
  warnings: PromptMissingField[];
};

export function validatePromptStep(lib: PromptLibraryStore): PromptValidationResult {
  const missing: PromptMissingField[] = [];
  const warnings: PromptMissingField[] = [];

  const addMissing = (
    id: string,
    sectionId: PromptSectionId,
    sectionTitle: string,
    sectionDomId: string,
    label: string,
  ) => {
    missing.push({ id, sectionId, sectionTitle, sectionDomId, label });
  };

  const addWarning = (
    id: string,
    sectionId: PromptSectionId,
    sectionTitle: string,
    sectionDomId: string,
    label: string,
  ) => {
    warnings.push({ id, sectionId, sectionTitle, sectionDomId, label });
  };

  if (!lib.promptName.trim()) {
    addMissing("name", "catalog", "Catálogo", "prompt-catalog", "Nombre del template");
  }

  if (!lib.promptTargetAudience.trim()) {
    addMissing(
      "target_audience",
      "params",
      "PARÁMETROS EXTRA",
      "parametros-extra",
      "Target audience (analiza transcripts o complétalo)",
    );
  }
  if (!lib.promptSystem.trim()) {
    addMissing(
      "system_instructions",
      "system",
      "SYSTEM INSTRUCTIONS",
      "system-instructions",
      "Estilo del canal (analiza transcripts o escribe manualmente)",
    );
  }

  const outOk = isOutputStructureAcceptable(lib.promptOutputStructure);
  const narrOk = isUserNarrativeAcceptable(lib.promptUserNarrative);

  if (!outOk && !narrOk) {
    addMissing(
      "user_narrative",
      "user",
      "USER INSTRUCTIONS",
      "user-instructions",
      "Modelo base o instrucciones narrativas (rellena al menos uno)",
    );
  } else if (!narrOk && outOk) {
    addWarning(
      "user_narrative",
      "user",
      "USER INSTRUCTIONS",
      "user-instructions",
      "Instrucciones narrativas (opcional si el modelo base ya basta)",
    );
  }

  const hasInferredParams =
    lib.promptHookType.trim() ||
    lib.promptNarrTone.trim() ||
    lib.promptCtaType.trim();
  if (!hasInferredParams) {
    addWarning(
      "inferred_params",
      "params",
      "PARÁMETROS EXTRA",
      "parametros-extra",
      "Tono / apertura / cierre (psicología — analiza transcripts)",
    );
  }

  return { missing, warnings };
}

export function isFieldHighlighted(
  highlight: PromptValidationResult | null | undefined,
  fieldId: string,
): "missing" | "warning" | null {
  if (!highlight) return null;
  if (highlight.missing.some((m) => m.id === fieldId)) return "missing";
  if (highlight.warnings.some((w) => w.id === fieldId)) return "warning";
  return null;
}

export function isSectionIncomplete(
  highlight: PromptValidationResult | null | undefined,
  sectionDomId: string,
): "missing" | "warning" | null {
  if (!highlight) return null;
  if (highlight.missing.some((m) => m.sectionDomId === sectionDomId)) return "missing";
  if (highlight.warnings.some((w) => w.sectionDomId === sectionDomId)) return "warning";
  return null;
}

export function sectionIdsToOpen(result: PromptValidationResult): string[] {
  const ids = new Set<string>();
  for (const m of [...result.missing, ...result.warnings]) {
    ids.add(m.sectionDomId);
  }
  return [...ids];
}
