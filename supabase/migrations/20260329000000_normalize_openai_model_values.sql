-- Normalize stored OpenAI model values for existing installations
UPDATE public.settings
SET value = regexp_replace(replace(value, 'gpt-5_4', 'gpt-5.4'), '-[0-9]{4}-[0-9]{2}-[0-9]{2}$', '')
WHERE key = 'openai_model';
