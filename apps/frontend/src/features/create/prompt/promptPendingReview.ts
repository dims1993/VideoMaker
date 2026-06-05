/** Claves de campos que pueden marcarse tras un análisis de transcripciones. */
export type PromptFieldKey =
  | "name"
  | "system_instructions"
  | "user_instructions_narrative"
  | "user_output_structure"
  | "target_audience"
  | "language_code"
  | "target_duration_minutes"
  | "hook_type"
  | "narrative_tone"
  | "cta_type";

/** Campos que el análisis de transcripts rellena; el usuario revisa y ajusta. */
export const INFERRED_FROM_TRANSCRIPTS_KEYS: PromptFieldKey[] = [
  "system_instructions",
  "user_instructions_narrative",
  "target_audience",
  "hook_type",
  "narrative_tone",
  "cta_type",
];

export function isPendingReview(
  pending: ReadonlySet<PromptFieldKey>,
  key: PromptFieldKey,
): boolean {
  return pending.has(key);
}
