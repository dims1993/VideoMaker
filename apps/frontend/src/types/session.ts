export type EnvInfo = {
  VIDEOMAKER_LLM_PROVIDER?: string;
  OPENAI_BASE_URL?: string;
  OPENAI_MODEL?: string;
  OLLAMA_BASE_URL?: string;
  OLLAMA_MODEL?: string;
  OPENAI_API_KEY?: boolean;
};

export type TranscriptsSessionSummary = {
  stored: boolean;
  valid_count: number;
  combined_chars: number;
  ready_to_analyze: boolean;
  analyze_status: string;
  analyze_error?: string | null;
  has_prompt_analysis?: boolean;
};

export type Session = {
  work: string;
  work_dir: string;
  transcripts_session?: TranscriptsSessionSummary;
  voice_presets: string[];
  has_script: boolean;
  has_narration: boolean;
  has_clone_reference: boolean;
  pipeline_images_count?: number;
  draft_exists: boolean;
  draft_path: string;
  env: EnvInfo;
  status: { state: string; step: string; detail: string };
  log_tail: string;
  voice_previews: { name: string; url: string }[];
  tts_reference?: { mode: string; preview_filename: string | null };
  narration_versions?: { name: string; url: string; active: boolean }[];
  active_narration?: string | null;
  urls: { narration: string; clone_reference: string; draft?: string };
};

export type TaskStatus = { id: string; state: string; result?: unknown; error?: string };

