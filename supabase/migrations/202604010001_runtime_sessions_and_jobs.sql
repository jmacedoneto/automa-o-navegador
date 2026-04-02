create table if not exists recording_sessions (
  id uuid primary key default gen_random_uuid(),
  automation_id uuid null references automations(id) on delete set null,
  status text not null default 'pending',
  runtime_id text null,
  started_at timestamptz null,
  finished_at timestamptz null,
  created_at timestamptz not null default now()
);

create table if not exists execution_jobs (
  id uuid primary key default gen_random_uuid(),
  automation_id uuid not null references automations(id) on delete cascade,
  trigger_type text not null,
  mode text not null,
  payload jsonb not null default '{}'::jsonb,
  status text not null default 'queued',
  created_at timestamptz not null default now()
);
