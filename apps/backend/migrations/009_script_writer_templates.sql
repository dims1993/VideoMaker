create extension if not exists pgcrypto;

create table if not exists script_writer_templates (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  system_instructions text not null default '',
  user_instructions text not null default '',
  params_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists script_writer_templates_name_idx on script_writer_templates (name);
