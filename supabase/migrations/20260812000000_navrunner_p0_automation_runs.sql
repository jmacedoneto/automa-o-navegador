-- Migration: NavRunner — automation_runs audit table (P0 minimal)
-- P1 will add automation_versions + automation_steps_log.

create table if not exists public.automation_runs (
    id uuid primary key default gen_random_uuid(),
    automation_name text not null,
    status text not null check (status in ('pending','running','success','failed','partial')),
    started_at timestamptz not null default now(),
    finished_at timestamptz,
    error_message text,
    bindings jsonb default '{}'::jsonb,
    trace_id text,
    created_at timestamptz not null default now()
);

create index if not exists idx_automation_runs_started_at
    on public.automation_runs (started_at desc);

create index if not exists idx_automation_runs_status
    on public.automation_runs (status);

alter table public.automation_runs enable row level security;

drop policy if exists "read_all_runs" on public.automation_runs;
create policy "read_all_runs" on public.automation_runs
    for select using (true);

drop policy if exists "insert_all_runs" on public.automation_runs;
create policy "insert_all_runs" on public.automation_runs
    for insert with check (true);

drop policy if exists "update_all_runs" on public.automation_runs;
create policy "update_all_runs" on public.automation_runs
    for update using (true);
