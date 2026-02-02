-- Tabela de configurações globais
CREATE TABLE public.settings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key TEXT UNIQUE NOT NULL,
  value TEXT,
  description TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Enable RLS
ALTER TABLE public.settings ENABLE ROW LEVEL SECURITY;

-- RLS Policies (sistema interno, acesso aberto)
CREATE POLICY "Anyone can view settings" ON public.settings FOR SELECT USING (true);
CREATE POLICY "Anyone can create settings" ON public.settings FOR INSERT WITH CHECK (true);
CREATE POLICY "Anyone can update settings" ON public.settings FOR UPDATE USING (true);
CREATE POLICY "Anyone can delete settings" ON public.settings FOR DELETE USING (true);

-- Valores padrão
INSERT INTO public.settings (key, value, description) VALUES
  ('browserless_url', '', 'URL da instância Browserless'),
  ('browserless_token', '', 'Token de autenticação do Browserless');

-- Trigger para updated_at
CREATE TRIGGER update_settings_updated_at
  BEFORE UPDATE ON public.settings
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();