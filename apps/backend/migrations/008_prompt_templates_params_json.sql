alter table prompt_templates
  add column if not exists params_json jsonb not null default '{}'::jsonb;

