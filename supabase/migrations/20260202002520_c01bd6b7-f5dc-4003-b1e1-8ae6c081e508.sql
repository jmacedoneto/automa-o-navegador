-- Criar enum para tipos de agendamento
CREATE TYPE public.schedule_type AS ENUM ('once', 'daily', 'weekly', 'monthly', 'interval');

-- Criar enum para status de execução
CREATE TYPE public.execution_status AS ENUM ('pending', 'running', 'success', 'failed', 'cancelled');

-- Criar enum para tipos de mídia
CREATE TYPE public.media_type AS ENUM ('image', 'audio', 'video');

-- Alterar tabela automations para adicionar novos campos
ALTER TABLE public.automations
ADD COLUMN IF NOT EXISTS webhook_url TEXT,
ADD COLUMN IF NOT EXISTS webhook_secret TEXT,
ADD COLUMN IF NOT EXISTS credentials JSONB DEFAULT '{}'::jsonb,
ADD COLUMN IF NOT EXISTS last_execution_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS last_execution_status public.execution_status;

-- Criar tabela schedules para agendamentos
CREATE TABLE public.schedules (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  automation_id UUID NOT NULL REFERENCES public.automations(id) ON DELETE CASCADE,
  schedule_type public.schedule_type NOT NULL DEFAULT 'once',
  cron_expression TEXT,
  interval_minutes INTEGER,
  days_of_week INTEGER[],
  time_of_day TIME,
  timezone TEXT DEFAULT 'America/Sao_Paulo',
  is_active BOOLEAN DEFAULT true,
  next_run_at TIMESTAMP WITH TIME ZONE,
  last_run_at TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Criar tabela execution_logs para histórico de execuções
CREATE TABLE public.execution_logs (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  automation_id UUID NOT NULL REFERENCES public.automations(id) ON DELETE CASCADE,
  schedule_id UUID REFERENCES public.schedules(id) ON DELETE SET NULL,
  started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  finished_at TIMESTAMP WITH TIME ZONE,
  status public.execution_status NOT NULL DEFAULT 'pending',
  error_message TEXT,
  steps_completed INTEGER DEFAULT 0,
  total_steps INTEGER DEFAULT 0,
  screenshots JSONB DEFAULT '[]'::jsonb,
  extracted_data JSONB DEFAULT '{}'::jsonb,
  webhook_response JSONB,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Criar tabela media_uploads para arquivos de mídia
CREATE TABLE public.media_uploads (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  automation_id UUID REFERENCES public.automations(id) ON DELETE CASCADE,
  file_type public.media_type NOT NULL,
  file_url TEXT NOT NULL,
  file_name TEXT,
  file_size INTEGER,
  transcription TEXT,
  analysis JSONB,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Habilitar RLS nas novas tabelas
ALTER TABLE public.schedules ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.execution_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.media_uploads ENABLE ROW LEVEL SECURITY;

-- Políticas RLS para schedules
CREATE POLICY "Anyone can view schedules" ON public.schedules FOR SELECT USING (true);
CREATE POLICY "Anyone can create schedules" ON public.schedules FOR INSERT WITH CHECK (true);
CREATE POLICY "Anyone can update schedules" ON public.schedules FOR UPDATE USING (true);
CREATE POLICY "Anyone can delete schedules" ON public.schedules FOR DELETE USING (true);

-- Políticas RLS para execution_logs
CREATE POLICY "Anyone can view execution_logs" ON public.execution_logs FOR SELECT USING (true);
CREATE POLICY "Anyone can create execution_logs" ON public.execution_logs FOR INSERT WITH CHECK (true);
CREATE POLICY "Anyone can update execution_logs" ON public.execution_logs FOR UPDATE USING (true);
CREATE POLICY "Anyone can delete execution_logs" ON public.execution_logs FOR DELETE USING (true);

-- Políticas RLS para media_uploads
CREATE POLICY "Anyone can view media_uploads" ON public.media_uploads FOR SELECT USING (true);
CREATE POLICY "Anyone can create media_uploads" ON public.media_uploads FOR INSERT WITH CHECK (true);
CREATE POLICY "Anyone can update media_uploads" ON public.media_uploads FOR UPDATE USING (true);
CREATE POLICY "Anyone can delete media_uploads" ON public.media_uploads FOR DELETE USING (true);

-- Triggers para updated_at
CREATE TRIGGER update_schedules_updated_at
BEFORE UPDATE ON public.schedules
FOR EACH ROW
EXECUTE FUNCTION public.update_updated_at_column();

-- Índices para performance
CREATE INDEX idx_schedules_automation_id ON public.schedules(automation_id);
CREATE INDEX idx_schedules_next_run_at ON public.schedules(next_run_at) WHERE is_active = true;
CREATE INDEX idx_execution_logs_automation_id ON public.execution_logs(automation_id);
CREATE INDEX idx_execution_logs_status ON public.execution_logs(status);
CREATE INDEX idx_execution_logs_started_at ON public.execution_logs(started_at DESC);
CREATE INDEX idx_media_uploads_automation_id ON public.media_uploads(automation_id);