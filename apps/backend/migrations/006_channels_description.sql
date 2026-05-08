alter table channels
  add column if not exists description text;

create index if not exists channels_description_idx on channels using gin (to_tsvector('simple', coalesce(description,'')));

