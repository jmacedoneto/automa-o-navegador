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

alter table public.recording_sessions enable row level security;
alter table public.execution_jobs enable row level security;

create policy "Anyone can view recording_sessions"
on public.recording_sessions for select using (true);

create policy "Anyone can create recording_sessions"
on public.recording_sessions for insert with check (true);

create policy "Anyone can update recording_sessions"
on public.recording_sessions for update using (true);

create policy "Anyone can delete recording_sessions"
on public.recording_sessions for delete using (true);

create policy "Anyone can view execution_jobs"
on public.execution_jobs for select using (true);

create policy "Anyone can create execution_jobs"
on public.execution_jobs for insert with check (true);

create policy "Anyone can update execution_jobs"
on public.execution_jobs for update using (true);

create policy "Anyone can delete execution_jobs"
on public.execution_jobs for delete using (true);
