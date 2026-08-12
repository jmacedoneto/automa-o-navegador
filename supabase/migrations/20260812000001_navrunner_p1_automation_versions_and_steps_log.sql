-- Migration: NavRunner P1a — automation_versions + automation_steps_log

create table if not exists public.automation_versions (
    id uuid primary key default gen_random_uuid(),
    automation_id uuid not null,
    version int not null,
    steps jsonb not null,
    inputs_schema text,
    created_at timestamptz not null default now(),
    created_by text,
    unique (automation_id, version)
);

create index if not exists idx_automation_versions_automation_id
    on public.automation_versions (automation_id, version desc);

create table if not exists public.automation_steps_log (
    id uuid primary key default gen_random_uuid(),
    run_id uuid not null,
    step_id text not null,
    attempt int not null default 1,
    status text not null check (status in ('ok', 'failed', 'skipped')),
    started_at timestamptz,
    finished_at timestamptz,
    error text,
    bindings jsonb default '{}'::jsonb,
    screenshot_keys jsonb default '[]'::jsonb,
    screenshot_urls jsonb default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_automation_steps_log_run_id
    on public.automation_steps_log (run_id, started_at);

create index if not exists idx_automation_steps_log_status
    on public.automation_steps_log (status);

alter table public.automation_versions enable row level security;
alter table public.automation_steps_log enable row level security;

drop policy if exists "read_all_versions" on public.automation_versions;
create policy "read_all_versions" on public.automation_versions
    for select using (true);

drop policy if exists "insert_all_versions" on public.automation_versions;
create policy "insert_all_versions" on public.automation_versions
    for insert with check (true);

drop policy if exists "read_all_steps" on public.automation_steps_log;
create policy "read_all_steps" on public.automation_steps_log
    for select using (true);

drop policy if exists "insert_all_steps" on public.automation_steps_log;
create policy "insert_all_steps" on public.automation_steps_log
    for insert with check (true);

drop policy if exists "update_all_steps" on public.automation_steps_log;
create policy "update_all_steps" on public.automation_steps_log
    for update using (true);
