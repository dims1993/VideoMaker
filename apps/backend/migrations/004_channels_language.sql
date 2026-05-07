alter table channels
  add column if not exists language text;

create index if not exists channels_language_idx on channels(language);

