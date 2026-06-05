export type ChunkStatus = "idle" | "generating" | "done" | "error";
export type VisualStatus = "idle" | "planning" | "done" | "error";

export type VisualShot = {
  id: string;
  order: number;
  shot_type?: string | null;
  director_note?: string | null;
  narration_excerpt?: string | null;
  situation_es?: string | null;
  scene_prompt_en?: string | null;
  protagonist_expression_key?: string | null;
  protagonist_expression_en?: string | null;
  ai_prompt?: string | null;
  negative_prompt?: string | null;
};

export type Chunk = {
  id: string;
  narration_text: string;
  section?: string | null;
  director_note: string | null;
  audio_url: string | null;
  duration_ms: number | null;
  status: ChunkStatus;
  visual_status?: VisualStatus;
  situation_es?: string | null;
  scene_prompt_en?: string | null;
  protagonist_expression_key?: string | null;
  protagonist_expression_en?: string | null;
  ai_prompt?: string | null;
  negative_prompt?: string | null;
  visual_shots?: VisualShot[];
  visual_rhythm_ok?: boolean | null;
  visual_rhythm_warning?: string | null;
};

export type ParseScriptResponse = {
  chunks: Chunk[];
};

export type GenerateChunkResponse = {
  chunk: Chunk;
};

export type TtsConfig = {
  provider: "elevenlabs" | "mock";
  elevenlabs_configured: boolean;
  voice_id: string | null;
  model_id: string | null;
};

export type ElevenLabsVoice = {
  voice_id: string;
  name: string;
  category: string;
};

export type GenerateAllChunksResponse = {
  chunks: Chunk[];
  generated: number;
  skipped: number;
  failed: number;
  errors: { chunk_id: string; detail: string }[];
};

export type PlanAllVisualResponse = {
  chunks: Chunk[];
  planned: number;
  skipped: number;
  failed: number;
  errors: { chunk_id: string; detail: string }[];
};

export type VisualPlannerConfig = {
  target_generator: string;
  has_style_settings?: boolean;
  has_protagonist?: boolean;
};

export type ExportNarrationResponse = {
  ok?: boolean;
  path?: string;
  duration_s?: number;
  chunks_used?: number;
  chunks_missing?: string[];
};

export type ExportImagePromptsResponse = {
  path: string;
  prompt_count: number;
};
