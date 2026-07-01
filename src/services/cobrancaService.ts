import { supabase } from "@/integrations/supabase/client";

// A tabela `cobranca_leads` foi criada diretamente no banco (ver
// supabase/migrations/20260701000000_cobranca_leads.sql) e ainda não faz
// parte do tipo `Database` gerado em `@/integrations/supabase/types`.
// Para evitar erros de tipagem no client tipado (o overload de `.from()`
// só aceita os nomes de tabela conhecidos pelo generic `Database`),
// fazemos um cast `as any` do client antes de `.from(...)` e mantemos
// toda a tipagem forte no restante do arquivo através da interface
// `CobrancaLead` abaixo.

export interface CobrancaLead {
  id: string;
  nome: string;
  cpf_cnpj: string | null;
  placa: string | null;
  chassi: string | null;
  vencimento_parcela: string | null;
  valor_total: number;
  celular: string;
  celular_8: string | null;
  fone: string | null;
  boleto: string | null;
  link: string | null;
  qtd_dias_inadimplencia: number | null;
  nm_auto: string | null;
  status_cobranca: string | null;
  fase_cobranca: string | null;
  objecao: string | null;
  tentativas: number;
  ultima_tentativa: string | null;
  data_retorno: string | null;
  valor_acordado: number | null;
  resultado: string | null;
  transcricao: string | null;
  encaminhar_setor: boolean;
  call_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface CobrancaMetrics {
  total: number;
  totalValor: number;
  discadas: number;
  atendidas: number;
  acordos: number;
  encaminharSetor: number;
  taxaAtendimento: number;
  taxaAcordo: number;
}

export async function fetchCobrancaLeads(): Promise<CobrancaLead[]> {
  const { data, error } = await (supabase as any)
    .from("cobranca_leads")
    .select("*")
    .order("created_at", { ascending: false });

  if (error) throw error;
  return (data ?? []) as CobrancaLead[];
}

export async function fetchCobrancaMetrics(): Promise<CobrancaMetrics> {
  const leads = await fetchCobrancaLeads();

  const total = leads.length;
  const totalValor = leads
    .filter((l) => l.resultado !== "acordo")
    .reduce((sum, l) => sum + (l.valor_total ?? 0), 0);
  const discadas = leads.filter((l) => (l.tentativas ?? 0) > 0).length;
  const atendidas = leads.filter((l) => l.status_cobranca === "atendeu").length;
  const acordos = leads.filter((l) => l.resultado === "acordo").length;
  const encaminharSetor = leads.filter((l) => l.encaminhar_setor === true).length;

  const taxaAtendimento = discadas > 0 ? atendidas / discadas : 0;
  const taxaAcordo = atendidas > 0 ? acordos / atendidas : 0;

  return {
    total,
    totalValor,
    discadas,
    atendidas,
    acordos,
    encaminharSetor,
    taxaAtendimento,
    taxaAcordo,
  };
}
