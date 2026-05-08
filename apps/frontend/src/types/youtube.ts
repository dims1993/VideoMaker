export type ChannelSearchItem = {
  channel_id: string;
  title: string;
  handle?: string;
  avatar_url?: string | null;
  subscribers?: number;
  total_views?: number;
  video_count?: number;
  description?: string;
};

export type SavedChannelItem = {
  channel_id: string;
  handle?: string | null;
  title?: string;
  avatar_url?: string | null;
  description?: string | null;
  internal_category?: string | null;
  is_pearl?: boolean | null;
  language?: string | null;
  subscribers?: number | null;
  total_views?: number | null;
  video_count?: number | null;
  updated_at?: string | null;
  last_synced_at?: string | null;

  // Derived opportunity metrics (computed in backend)
  opportunity_score?: number | null;
  subs_delta_30d?: number | null;
  views_delta_30d?: number | null;
  views_per_sub?: number | null;
  median_views?: number | null;
  hit_rate?: number | null;
  uploads_per_month_90d?: number | null;
  days_since_last_upload?: number | null;
  median_duration_min?: number | null;
  pct_over_8min?: number | null;
  pct_over_10min?: number | null;
  likes_per_1k_views?: number | null;
  comments_per_1k_views?: number | null;
};

export type ChannelVideoItem = {
  video_id: string;
  title: string;
  thumbnail_url?: string | null;
  description?: string | null;
  tags_json?: unknown;
  category_id?: string | null;
  default_language?: string | null;
  default_audio_language?: string | null;
  published_at?: string | null;
  duration_s?: number | null;
  views?: number | null;
  likes?: number | null;
  comments?: number | null;
  views_per_day?: number | null;
  vph?: number | null;
  engagement?: number | null;
  like_rate?: number | null;
  comment_rate?: number | null;
  engagement_per_sub?: number | null;
};

