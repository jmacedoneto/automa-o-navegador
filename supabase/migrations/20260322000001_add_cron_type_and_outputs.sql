-- Add 'cron' to the schedule_type enum
ALTER TYPE public.schedule_type ADD VALUE IF NOT EXISTS 'cron';

-- Ensure automations table has the outputs column (idempotent)
ALTER TABLE public.automations
  ADD COLUMN IF NOT EXISTS outputs JSONB DEFAULT '[]'::jsonb;

-- Ensure google_service_account setting exists
INSERT INTO public.settings (key, value, description)
VALUES ('google_service_account', '', 'JSON da Service Account do Google (para Google Sheets)')
ON CONFLICT (key) DO NOTHING;
