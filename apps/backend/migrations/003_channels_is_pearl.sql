-- Mark channels explicitly saved as "pearls" (curated list)
alter table channels
  add column if not exists is_pearl boolean not null default false;

create index if not exists channels_is_pearl_idx on channels(is_pearl);

