create table if not exists execution_runs (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null references execution_jobs(id) on delete cascade,
  status text not null default 'queued',
  steps_completed integer not null default 0,
  total_steps integer not null default 0,
  fallback_attempts integer not null default 0,
  screenshots jsonb not null default '[]'::jsonb,
  extracted_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists output_deliveries (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references execution_runs(id) on delete cascade,
  destination text not null,
  status text not null default 'pending',
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
