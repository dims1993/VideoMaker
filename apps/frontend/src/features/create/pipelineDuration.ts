/** Objetivo de duración alineado con `videomaker.pipeline.duration_policy`. */
export const PIPELINE_TARGET_MIN_MINUTES = 10;
export const PIPELINE_TARGET_MAX_MINUTES = 12;
export const PIPELINE_DEFAULT_MINUTES = 10;

export function clampPipelineMinutes(raw: number): number {
  const n = Number(raw);
  if (!Number.isFinite(n) || n <= 0) return PIPELINE_DEFAULT_MINUTES;
  return Math.min(PIPELINE_TARGET_MAX_MINUTES, Math.max(PIPELINE_TARGET_MIN_MINUTES, n));
}

export const PIPELINE_DURATION_HINT =
  `Objetivo de producción: ${PIPELINE_TARGET_MIN_MINUTES}–${PIPELINE_TARGET_MAX_MINUTES} min (primer vídeo completo).`;
