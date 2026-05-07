-- Channels directory + analytics tables

create table if not exists channels (
  channel_id text primary key,
  handle text,
  title text not null default '',
  avatar_url text,
  internal_category text,
  notes text,
  rpm_estimate numeric,
  monetization_estimate numeric,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  last_synced_at timestamptz
);

create index if not exists channels_handle_idx on channels(handle);
create index if not exists channels_title_idx on channels(title);
create index if not exists channels_category_idx on channels(internal_category);

create table if not exists channel_snapshots (
  id bigserial primary key,
  channel_id text not null references channels(channel_id) on delete cascade,
  fetched_at timestamptz not null default now(),
  subscribers bigint,
  total_views bigint,
  video_count int
);
create index if not exists channel_snapshots_channel_fetched_idx on channel_snapshots(channel_id, fetched_at desc);

create table if not exists videos (
  video_id text primary key,
  channel_id text not null references channels(channel_id) on delete cascade,
  title text not null default '',
  thumbnail_url text,
  published_at timestamptz,
  duration_s int,
  views bigint,
  likes bigint,
  comments bigint
);
create index if not exists videos_channel_published_idx on videos(channel_id, published_at desc);

create table if not exists video_insights (
  id bigserial primary key,
  video_id text not null references videos(video_id) on delete cascade,
  fetched_at timestamptz not null default now(),
  hook text,
  outline_json jsonb,
  broll_themes_json jsonb,
  cta text,
  keywords_json jsonb
);
create index if not exists video_insights_video_fetched_idx on video_insights(video_id, fetched_at desc);

create table if not exists assets (
  id bigserial primary key,
  channel_id text not null references channels(channel_id) on delete cascade,
  kind text not null,
  path_or_url text not null,
  created_at timestamptz not null default now()
);
create index if not exists assets_channel_kind_idx on assets(channel_id, kind, created_at desc);

