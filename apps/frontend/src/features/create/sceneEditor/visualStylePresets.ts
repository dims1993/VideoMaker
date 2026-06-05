export const ALEX_PRESET_ID = "alex_v1";

export type VisualStylePresetSummary = {
  id: string;
  name: string;
  bundled: boolean;
  updated_at: string;
};

export type VisualStylePresetFull = VisualStylePresetSummary & {
  base_style_en: string;
  protagonist_en: string;
  protagonist_wardrobe_en: string;
  protagonist_action_rules_en: string;
  protagonist_expressions_en: string;
  avoid_en: string;
  aspect_ratio: string;
  output_spec: string;
};
