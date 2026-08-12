-- Update the stored OpenAI model default for existing installations
UPDATE public.settings
SET value = 'gpt-5.4-mini',
    description = 'Modelo OpenAI padrão (gpt-5.4-mini e compatíveis)'
WHERE key = 'openai_model';
