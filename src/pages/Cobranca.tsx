import { useEffect, useMemo, useState } from "react";
import { Header } from "@/components/layout/Header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Loader2, AlertTriangle, Phone } from "lucide-react";
import { toast } from "sonner";
import {
  fetchCobrancaLeads,
  fetchCobrancaMetrics,
  CobrancaLead,
  CobrancaMetrics,
} from "@/services/cobrancaService";

const currencyFormatter = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});

function formatCurrency(value: number | null | undefined) {
  return currencyFormatter.format(value ?? 0);
}

function formatDate(value: string | null | undefined) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleDateString("pt-BR");
}

function formatPercent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

const STATUS_OPTIONS = [
  { value: "todos", label: "Todos" },
  { value: "pendente", label: "Pendente" },
  { value: "discando", label: "Discando" },
  { value: "atendeu", label: "Atendeu" },
  { value: "nao_atendeu", label: "Não atendeu" },
  { value: "invalido", label: "Inválido" },
];

const STATUS_BADGE_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  pendente: "outline",
  discando: "secondary",
  atendeu: "default",
  nao_atendeu: "destructive",
  invalido: "destructive",
};

function statusLabel(status: string | null) {
  const found = STATUS_OPTIONS.find((s) => s.value === status);
  return found ? found.label : status ?? "-";
}

export default function Cobranca() {
  const [leads, setLeads] = useState<CobrancaLead[]>([]);
  const [metrics, setMetrics] = useState<CobrancaMetrics | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("todos");
  const [search, setSearch] = useState("");
  const [transcricaoLead, setTranscricaoLead] = useState<CobrancaLead | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setIsLoading(true);
    try {
      const [leadsData, metricsData] = await Promise.all([
        fetchCobrancaLeads(),
        fetchCobrancaMetrics(),
      ]);
      setLeads(leadsData);
      setMetrics(metricsData);
    } catch (error) {
      console.error("Error loading cobrança data:", error);
      toast.error("Erro ao carregar dados de cobrança");
    } finally {
      setIsLoading(false);
    }
  };

  const encaminharSetorLeads = useMemo(
    () => leads.filter((l) => l.encaminhar_setor === true),
    [leads],
  );

  const filteredLeads = useMemo(() => {
    return leads.filter((lead) => {
      if (statusFilter !== "todos" && lead.status_cobranca !== statusFilter) {
        return false;
      }
      if (search.trim()) {
        const term = search.trim().toLowerCase();
        const matchesNome = lead.nome?.toLowerCase().includes(term);
        const matchesCelular = lead.celular?.toLowerCase().includes(term);
        if (!matchesNome && !matchesCelular) return false;
      }
      return true;
    });
  }, [leads, statusFilter, search]);

  return (
    <div className="min-h-screen bg-background">
      <Header />

      <main className="container py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold">Cobrança</h1>
          <p className="text-muted-foreground mt-1">
            Painel de gestão de cobrança automatizada
          </p>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-24">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
          </div>
        ) : (
          <>
            {/* Métricas */}
            <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 mb-8">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    Total em aberto
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {formatCurrency(metrics?.totalValor)}
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    Total de leads
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{metrics?.total ?? 0}</div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    Taxa de atendimento
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {formatPercent(metrics?.taxaAtendimento ?? 0)}
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    Taxa de acordo
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {formatPercent(metrics?.taxaAcordo ?? 0)}
                  </div>
                </CardContent>
              </Card>

              <Card className="border-orange-500/30 bg-orange-500/5">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    Encaminhado ao setor
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-2">
                    <div className="text-2xl font-bold">
                      {metrics?.encaminharSetor ?? 0}
                    </div>
                    <Badge className="bg-orange-500/15 text-orange-600 border-orange-500/30">
                      Atenção
                    </Badge>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Fila de encaminhamento */}
            {encaminharSetorLeads.length > 0 && (
              <Card className="mb-8 border-orange-500/30 bg-orange-500/5">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <AlertTriangle className="h-5 w-5 text-orange-600" />
                    Encaminhar para o setor
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="max-h-72 overflow-auto space-y-2">
                    {encaminharSetorLeads.map((lead) => (
                      <div
                        key={lead.id}
                        className="flex items-center justify-between gap-4 rounded-md border bg-background px-4 py-3"
                      >
                        <div>
                          <p className="font-medium">{lead.nome}</p>
                          <p className="text-sm text-muted-foreground flex items-center gap-1">
                            <Phone className="h-3 w-3" />
                            {lead.celular}
                          </p>
                        </div>
                        <div className="text-sm text-right text-muted-foreground max-w-[50%]">
                          {lead.objecao || lead.resultado || "Sem motivo informado"}
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Filtros */}
            <div className="flex flex-col sm:flex-row gap-3 mb-4">
              <Input
                placeholder="Buscar por nome ou celular..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="sm:max-w-xs"
              />
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="sm:max-w-[220px]">
                  <SelectValue placeholder="Filtrar por status" />
                </SelectTrigger>
                <SelectContent>
                  {STATUS_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Tabela principal */}
            <Card>
              <CardContent className="p-0">
                <div className="max-h-[600px] overflow-auto">
                  <Table>
                    <TableHeader className="sticky top-0 bg-card z-10">
                      <TableRow>
                        <TableHead>Nome</TableHead>
                        <TableHead>Veículo</TableHead>
                        <TableHead>Valor</TableHead>
                        <TableHead>Dias Atraso</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Resultado</TableHead>
                        <TableHead>Tentativas</TableHead>
                        <TableHead>Data Retorno</TableHead>
                        <TableHead className="text-right">Ações</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredLeads.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={9} className="text-center py-10 text-muted-foreground">
                            Nenhum lead encontrado
                          </TableCell>
                        </TableRow>
                      ) : (
                        filteredLeads.map((lead) => (
                          <TableRow key={lead.id}>
                            <TableCell className="font-medium">{lead.nome}</TableCell>
                            <TableCell>{lead.nm_auto || "-"}</TableCell>
                            <TableCell>{formatCurrency(lead.valor_total)}</TableCell>
                            <TableCell>{lead.qtd_dias_inadimplencia ?? "-"}</TableCell>
                            <TableCell>
                              <Badge variant={STATUS_BADGE_VARIANT[lead.status_cobranca ?? ""] ?? "outline"}>
                                {statusLabel(lead.status_cobranca)}
                              </Badge>
                            </TableCell>
                            <TableCell>{lead.resultado || "-"}</TableCell>
                            <TableCell>{lead.tentativas ?? 0}</TableCell>
                            <TableCell>{formatDate(lead.data_retorno)}</TableCell>
                            <TableCell className="text-right">
                              <Button
                                variant="ghost"
                                size="sm"
                                disabled={!lead.transcricao}
                                onClick={() => setTranscricaoLead(lead)}
                              >
                                Ver transcrição
                              </Button>
                            </TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          </>
        )}
      </main>

      <Dialog open={!!transcricaoLead} onOpenChange={(open) => !open && setTranscricaoLead(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Transcrição da ligação</DialogTitle>
            <DialogDescription>
              {transcricaoLead?.nome} — {transcricaoLead?.celular}
            </DialogDescription>
          </DialogHeader>
          <div className="max-h-[60vh] overflow-auto whitespace-pre-wrap text-sm rounded-md border bg-muted/30 p-4">
            {transcricaoLead?.transcricao || "Sem transcrição disponível."}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
