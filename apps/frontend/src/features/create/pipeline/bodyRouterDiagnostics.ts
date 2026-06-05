export type SectionDensityPlanSummary = {
  hook_pool_min?: number;
  body_pool_min?: number;
  total_narration_min?: number;
  hook_target_images?: number;
  body_target_images?: number;
  total_target_images?: number;
  hook_target_hold_s?: number;
  body_target_hold_s?: number;
  body_max_hold_s?: number;
  audio_source?: string;
  notes?: string;
};

export type BodyRouterDiagnostics = {
  macro_beat_count?: number;
  track_summary?: { avatar?: number; insert?: number; other?: number };
  macro_beats_source?: string;
  split_max_hold_count?: number;
  fragment_beats?: { index?: number; track?: string; preview?: string }[];
  duplicate_pairs?: {
    a?: number;
    b?: number;
    shared_words?: number;
    preview_a?: string;
    preview_b?: string;
  }[];
  density?: {
    body_audio_pool_s?: number;
    body_audio_pool_min?: number;
    hook_target_images?: number;
    body_target_images?: number;
    total_target_images?: number;
    hook_target_hold_s?: number;
    body_target_hold_s?: number;
    body_max_hold_s?: number;
    audio_source?: string;
    target_beat_count?: number;
    actual_beat_count?: number;
    beats_deficit?: number;
    avg_sec_per_beat_if_equal?: number | null;
    plan_notes?: string;
  };
  composition_desk_bias?: boolean;
  warnings?: string[];
  ok?: boolean;
};

export async function fetchBodyRouterDiagnostics(
  workApplied: string,
): Promise<{
  exists: boolean;
  diagnostics: BodyRouterDiagnostics;
  artifact_density_target?: Record<string, unknown>;
  visual_density_plan?: SectionDensityPlanSummary;
}> {
  const r = await fetch(
    `/api/pipeline/body-router-diagnostics?work=${encodeURIComponent(workApplied)}`,
  );
  if (!r.ok) {
    throw new Error(`Diagnóstico Body Router: ${r.status}`);
  }
  return r.json() as Promise<{
    exists: boolean;
    diagnostics: BodyRouterDiagnostics;
    artifact_density_target?: Record<string, unknown>;
    visual_density_plan?: SectionDensityPlanSummary;
  }>;
}
