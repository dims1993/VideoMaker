export type SceneVisualSettings = {
  base_style_en: string;
  protagonist_en: string;
  protagonist_wardrobe_en: string;
  protagonist_action_rules_en: string;
  protagonist_expressions_en: string;
  avoid_en: string;
  planner_extra_rules_en: string;
  gemini_continuity_prefix_en: string;
  auto_avoid_supplement_en: string;
  aspect_ratio: string;
  output_spec: string;
  target_generator?: string;
};

/** Borrador «Nuevo estilo»: todos los campos de texto vacíos. */
export const EMPTY_SCENE_VISUAL_SETTINGS: SceneVisualSettings = {
  base_style_en: "",
  protagonist_en: "",
  protagonist_wardrobe_en: "",
  protagonist_action_rules_en: "",
  protagonist_expressions_en: "",
  avoid_en: "",
  planner_extra_rules_en: "",
  gemini_continuity_prefix_en: "",
  auto_avoid_supplement_en: "",
  aspect_ratio: "16:9",
  output_spec: "2K output",
};

export type VisualEffectiveRulesPreview = {
  fallback_used_when_empty: Record<string, string>;
  effective_avoid_en: string;
  planner_extra_rules_en: string;
  planner_extra_rules_is_custom: boolean;
  gemini_continuity_prefix_en: string;
  gemini_continuity_prefix_is_custom: boolean;
  auto_avoid_supplement_en: string;
  auto_avoid_supplement_is_custom: boolean;
  expression_catalog_count: number;
  scene_validation_rules_es: string[];
  builtin_defaults: Record<string, string>;
};

export type VisualPlannerConfig = {
  target_generator: string;
  has_style_settings: boolean;
  has_protagonist: boolean;
  has_action_pose_rules: boolean;
  has_expression_catalog?: boolean;
  planner_injects: string[];
};

/** Cómo el planner elige expresión por bloque — referencia en UI. */
export const VISUAL_EXPRESSION_PLANNER_ES = [
  "El LLM lee el tono emocional de la narración y elige una clave (concerned, shocked, skeptical…).",
  "Si falla, el backend infiere la expresión por palabras clave del voiceover.",
  "Se inyecta en el prompt como «Protagonist facial expression: …».",
  "Cada bloque guarda protagonist_expression_key visible en la tarjeta del bloque.",
  "El planner ve expresiones recientes y pide otra si la emoción del guion cambió.",
];

export const DEFAULT_PROTAGONIST_EXPRESSIONS =
  "neutral: calm circular eyes, relaxed mouth line, attentive but composed\n" +
  "concerned: slightly furrowed cartoon brows, worried circular eyes, tight small mouth\n" +
  "shocked: circular eyes widened, small round open mouth, raised brows in surprise\n" +
  "skeptical: one raised brow, flat unimpressed mouth, sideways doubtful glance\n" +
  "frustrated: brows angled down, pressed lips, tense jaw in simple cartoon lines\n" +
  "hopeful: soft slight smile, bright circular eyes, lifted cheeks with blush\n" +
  "realization: eyes widened with insight, small o-shaped mouth, brows raised in discovery\n" +
  "determined: focused straight-on gaze, firm set mouth, forward-leaning energy\n" +
  "dismissive: half-lidded circular eyes, flat mouth, unimpressed look\n" +
  "curious: head slightly tilted, one brow raised, interested open circular eyes\n" +
  "relieved: soft exhale smile, relaxed brows, eased shoulders\n" +
  "overwhelmed: wide stressed eyes, wavy mouth line, subtle sweat drop in cartoon style";

/** Validaciones automáticas del Visual Planner (backend) — referencia en UI. */
export const VISUAL_PLANNER_VALIDATIONS_ES = [
  "Postura activa: verbo físico (-ing), manos en primer plano, o POV/over-shoulder.",
  "Prohibido sin acción: mano en barbilla, observador pasivo en el centro, sentado contemplativo.",
  "No repetir la misma acción, pose o verbo principal que el bloque inmediatamente anterior.",
  "Pantallas, pizarras y papeles están permitidos si la narración los pide — solo no repetir el gesto.",
  "Montajes: props de la narración; el protagonista debe actuar distinto en cada bloque.",
];

export const DEFAULT_PROTAGONIST_ACTION_RULES =
  "POSE & ACTION (every block):\n" +
  "- Give the protagonist a SPECIFIC physical action from the narration " +
  "(flipping a document page, marking a form, scrolling a phone, walking, handing papers, " +
  "comparing printouts, pointing at a prop when narration requires it).\n" +
  "- NEVER repeat the same action or pose as the PREVIOUS block — vary gesture even if narration is similar.\n" +
  "- Vary body pose and camera every block: full-body side view, over-shoulder, hands close-up, " +
  "walking mid-step, reaching.\n" +
  "- BANNED without narration support: hand on chin, Rodin thinker, arms crossed staring, idle center observer.\n" +
  "- Montage blocks: protagonist ACTS on props; screens/whiteboards/papers are all OK when narration names them.\n" +
  "- Prefer concrete verbs over mood words: avoid thoughtful, contemplative, gazing reflectively, pensive.";

export const DEFAULT_SCENE_VISUAL_SETTINGS: SceneVisualSettings = {
  base_style_en:
    "Cinematic documentary still, editorial photography, muted warm palette, natural motivated lighting, shallow depth of field, subtle 35mm film grain",
  protagonist_en:
    "A person in their early 30s — the viewer's stand-in — shown in medium shot, over-the-shoulder, or close-up on hands when the scene focuses on objects (phone, calculator, app).",
  protagonist_wardrobe_en:
    "messy dark brown hair, warm light-tan skin, black long-sleeve shirt, bare head with no hat cap hood or beanie",
  protagonist_action_rules_en: DEFAULT_PROTAGONIST_ACTION_RULES,
  protagonist_expressions_en: DEFAULT_PROTAGONIST_EXPRESSIONS,
  avoid_en:
    "stock photo feel, generic office, cartoon, watermark, extra fingers, blurry, oversaturated colors",
  planner_extra_rules_en: "",
  gemini_continuity_prefix_en: "",
  auto_avoid_supplement_en: "",
  aspect_ratio: "16:9",
  output_spec: "2K output",
};
