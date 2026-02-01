-- Tabela para armazenar as configurações de automação
CREATE TABLE public.automations (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  erp_url TEXT NOT NULL,
  browserless_url TEXT NOT NULL,
  sheets_url TEXT NOT NULL,
  instructions TEXT NOT NULL,
  steps JSONB DEFAULT '[]'::jsonb,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Habilitar RLS
ALTER TABLE public.automations ENABLE ROW LEVEL SECURITY;

-- Políticas públicas (para MVP sem autenticação)
CREATE POLICY "Anyone can view automations" 
ON public.automations 
FOR SELECT 
USING (true);

CREATE POLICY "Anyone can create automations" 
ON public.automations 
FOR INSERT 
WITH CHECK (true);

CREATE POLICY "Anyone can update automations" 
ON public.automations 
FOR UPDATE 
USING (true);

CREATE POLICY "Anyone can delete automations" 
ON public.automations 
FOR DELETE 
USING (true);

-- Trigger para atualizar updated_at
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = public;

CREATE TRIGGER update_automations_updated_at
BEFORE UPDATE ON public.automations
FOR EACH ROW
EXECUTE FUNCTION public.update_updated_at_column();