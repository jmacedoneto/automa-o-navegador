-- Adiciona configurações de IA e integrações na tabela settings

INSERT INTO public.settings (key, value, description) VALUES
  ('openai_api_key',     '', 'Chave da API do OpenAI'),
  ('openai_model',       'gpt-5.4-mini', 'Modelo OpenAI padrão (gpt-5.4-mini e compatíveis)'),
  ('evolution_api_url',  '', 'URL base da Evolution API (WhatsApp)'),
  ('evolution_api_key',  '', 'API Key da Evolution API'),
  ('evolution_instance', '', 'Nome da instância Evolution API'),
  ('google_service_account', '', 'JSON da Service Account do Google (para Google Sheets)')
ON CONFLICT (key) DO NOTHING;

-- Adiciona coluna outputs nas automações para configurar entregas por automação
ALTER TABLE public.automations
  ADD COLUMN IF NOT EXISTS outputs JSONB DEFAULT '[]'::jsonb;
