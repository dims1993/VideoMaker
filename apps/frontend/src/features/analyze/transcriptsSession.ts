export type TranscriptsAnalyzeStatus =
  | "pending"
  | "analyzing"
  | "completed"
  | "error";

export type TranscriptsSessionView = {
  stored: boolean;
  /** JSON guardado en disco (aunque aún no haya transcripts válidos). */
  has_file?: boolean;
  valid_count: number;
  missing_count?: number;
  blocked_count?: number;
  forbidden_count?: number;
  transcript_provider?: string | null;
  session_needs_reload?: boolean;
  youtube_ip_blocked?: boolean;
  youtube_ip_blocked_hint?: string;
  combined_chars: number;
  ready_to_analyze: boolean;
  analyze_status: TranscriptsAnalyzeStatus;
  analyze_error?: string | null;
  source_channel_id?: string;
  video_count?: number;
  stored_at?: string | null;
  analyze_completed_at?: string | null;
  has_prompt_analysis?: boolean;
  prompt_analysis?: Record<string, unknown> | null;
  topics_count?: number;
  /** Último idioma elegido al pulsar Analizar (en | es). */
  analyze_output_language?: string | null;
};

export type AnalyzeOutputLanguage = "en" | "es";

export function normalizeAnalyzeOutputLang(raw: string | null | undefined): AnalyzeOutputLanguage {
  return raw === "en" ? "en" : "es";
}

export function sessionLoadLabel(status: TranscriptsAnalyzeStatus): string {
  if (status === "analyzing") return "Analizando…";
  if (status === "completed") return "Completado";
  if (status === "error") return "Error";
  return "Pendiente";
}

export function sessionReadyLabel(view: TranscriptsSessionView): string {
  const hasFile = view.has_file ?? view.stored;
  if (!hasFile && (view.video_count ?? 0) < 1) return "Pendiente";
  if ((view.valid_count ?? 0) < 1) return "Sin transcripts válidos";
  if (view.analyze_status === "completed") return "Completado";
  return "Listo para analizar";
}

export function sessionReadyHint(
  view: TranscriptsSessionView,
  providerCfg?: TranscriptsProviderConfig | null,
): string | null {
  const hasFile = view.has_file ?? view.stored;
  const videos = view.video_count ?? 0;
  const valid = view.valid_count ?? 0;
  const missing = view.missing_count ?? Math.max(0, videos - valid);
  const oauthReady = providerCfg?.data_api_oauth_ready ?? false;

  if (!hasFile && videos < 1) {
    return "Pulsa «Transcripts JSON → sesión» para descargar y guardar transcripciones.";
  }

  if (
    oauthReady &&
    (view.session_needs_reload ||
      (valid < 1 &&
        (view.youtube_ip_blocked ||
          (view.blocked_count ?? 0) > 0 ||
          (view.forbidden_count ?? 0) > 0)))
  ) {
    return (
      "OAuth ya está configurado. La sesión en disco es de un intento anterior " +
      "(scrape / IP bloqueada / solo data_api). Pulsa otra vez «Transcripts JSON → sesión» " +
      "(modo auto: Data API y fallback scrape en canales ajenos)."
    );
  }

  if (view.youtube_ip_blocked) {
    if (providerCfg?.worker_url_set) {
      return (
        view.youtube_ip_blocked_hint ??
        "Scrape directo bloqueado; el Worker CF debería usarse en auto. Reintenta «Transcripts JSON → sesión»."
      );
    }
    return (
      view.youtube_ip_blocked_hint ??
      "IP bloqueada en scrape. Despliega el Worker (workers/youtube-transcript-proxy) y " +
        "YOUTUBE_TRANSCRIPT_WORKER_URL en .env, o importa JSON."
    );
  }

  if ((view.forbidden_count ?? 0) > 0 && valid < 1) {
    const mode = providerCfg?.provider ?? "auto";
    if (mode === "data_api") {
      return (
        `${view.forbidden_count} vídeo(s) con 403: Data API solo descarga subtítulos de vídeos propios. ` +
        "Usa auto + YOUTUBE_TRANSCRIPT_WORKER_URL (Cloudflare) y vuelve a «Transcripts JSON → sesión»."
      );
    }
    return (
      `${view.forbidden_count} vídeo(s) sin subtítulo (403 en Data API y scrape sin texto). ` +
      "Prueba más vídeos, proxy si hay IpBlocked, o importa JSON."
    );
  }

  if (valid < 1 && videos > 0) {
    return `${videos} vídeo(s) en JSON, ${missing} sin subtítulo real (sin texto). Prueba más vídeos, sube «Máx. vídeos» o idioma ES/EN en clasificación.`;
  }
  if (view.analyze_status === "pending" && valid >= 1) {
    return "Transcripts guardados. Pulsa «Analizar» para generar temas y plantilla Prompt.";
  }
  return null;
}

export type TranscriptsProviderConfig = {
  provider: string;
  provider_label: string;
  data_api_oauth_ready: boolean;
  worker_url_set?: boolean;
  youtube_api_key_set: boolean;
  setup_hint?: string | null;
};

export async function fetchTranscriptsProviderConfig(): Promise<TranscriptsProviderConfig> {
  const r = await fetch("/api/youtube/transcripts/config");
  if (!r.ok) {
    return {
      provider: "auto",
      provider_label: "auto: Data API → scrape",
      data_api_oauth_ready: false,
      worker_url_set: false,
      youtube_api_key_set: false,
    };
  }
  return (await r.json()) as TranscriptsProviderConfig;
}

export async function fetchTranscriptsSession(
  work: string,
): Promise<TranscriptsSessionView> {
  const r = await fetch(
    `/api/session/transcripts?work=${encodeURIComponent(work)}`,
  );
  if (!r.ok) {
    return {
      stored: false,
      valid_count: 0,
      combined_chars: 0,
      ready_to_analyze: false,
      analyze_status: "pending",
    };
  }
  return (await r.json()) as TranscriptsSessionView;
}
