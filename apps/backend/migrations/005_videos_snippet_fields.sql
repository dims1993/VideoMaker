alter table videos
  add column if not exists description text,
  add column if not exists tags_json jsonb,
  add column if not exists category_id text,
  add column if not exists default_language text,
  add column if not exists default_audio_language text;

create index if not exists videos_category_idx on videos(category_id);

