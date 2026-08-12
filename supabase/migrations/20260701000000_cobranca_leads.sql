create table if not exists cobranca_leads (
  id uuid primary key default gen_random_uuid(),
  nome text not null,
  cpf_cnpj text,
  placa text,
  chassi text,
  vencimento_parcela date,
  valor_total numeric not null,
  celular text not null,
  celular_8 text,
  fone text,
  boleto text,
  link text,
  qtd_dias_inadimplencia int,
  nm_auto text,
  status_cobranca text default 'pendente',
  fase_cobranca text,
  objecao text,
  tentativas int default 0,
  ultima_tentativa timestamptz,
  data_retorno date,
  valor_acordado numeric,
  resultado text,
  transcricao text,
  encaminhar_setor boolean default false,
  call_id text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create index if not exists idx_cobranca_leads_status on cobranca_leads(status_cobranca);
create index if not exists idx_cobranca_leads_encaminhar on cobranca_leads(encaminhar_setor) where encaminhar_setor = true;
