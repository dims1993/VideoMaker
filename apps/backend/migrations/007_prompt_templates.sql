create extension if not exists pgcrypto;

create table if not exists prompt_templates (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  hook_style text not null default '',
  visual_style text not null default '',
  tone text not null default '',
  system_instructions text not null default '',
  user_instructions text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists prompt_templates_name_idx on prompt_templates (name);
