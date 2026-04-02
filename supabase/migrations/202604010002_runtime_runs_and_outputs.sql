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

alter table public.execution_runs enable row level security;
alter table public.output_deliveries enable row level security;

create policy "Anyone can view execution_runs"
on public.execution_runs for select using (true);

create policy "Anyone can create execution_runs"
on public.execution_runs for insert with check (true);

create policy "Anyone can update execution_runs"
on public.execution_runs for update using (true);

create policy "Anyone can delete execution_runs"
on public.execution_runs for delete using (true);

create policy "Anyone can view output_deliveries"
on public.output_deliveries for select using (true);

create policy "Anyone can create output_deliveries"
on public.output_deliveries for insert with check (true);

create policy "Anyone can update output_deliveries"
on public.output_deliveries for update using (true);

create policy "Anyone can delete output_deliveries"
on public.output_deliveries for delete using (true);
