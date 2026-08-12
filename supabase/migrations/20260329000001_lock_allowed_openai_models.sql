-- Force unsupported OpenAI models back to the allowed default
UPDATE public.settings
SET value = 'gpt-5.4-mini'
WHERE key = 'openai_model'
  AND regexp_replace(replace(value, 'gpt-5_4', 'gpt-5.4'), '-[0-9]{4}-[0-9]{2}-[0-9]{2}$', '') NOT IN ('gpt-5.4-mini', 'gpt-5.4');
