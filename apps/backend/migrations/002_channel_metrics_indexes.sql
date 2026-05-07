-- Indexes to speed opportunity metrics aggregation

-- Last-N videos per channel (already have channel+published desc, keep as-is)
-- Additional sort/filter helpers:
create index if not exists videos_channel_views_idx on videos(channel_id, views desc);
create index if not exists videos_channel_duration_idx on videos(channel_id, duration_s desc);
create index if not exists videos_channel_published_idx on videos(channel_id, published_at desc);

-- Snapshots lookups for velocity windows (already have channel+fetched desc, keep as-is)
create index if not exists channel_snapshots_channel_fetched_idx on channel_snapshots(channel_id, fetched_at desc);

