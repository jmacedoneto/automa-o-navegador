import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Header } from "@/components/layout/Header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { supabase } from "@/integrations/supabase/client";
import { toast } from "sonner";
import { 
  ArrowLeft, 
  CheckCircle, 
  XCircle, 
  Clock, 
  Play, 
  Image as ImageIcon,
  FileText,
  AlertTriangle,
  Loader2,
  RefreshCw,
  ExternalLink
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { ptBR } from "date-fns/locale";

interface ExecutionLog {
  id: string;
  automation_id: string;
  status: 'pending' | 'running' | 'success' | 'failed' | 'cancelled';
  started_at: string;
  finished_at: string | null;
  steps_completed: number | null;
  total_steps: number | null;
  error_message: string | null;
  screenshots: string[] | null;
  extracted_data: Record<string, unknown> | null;
  webhook_response: { status?: number; ok?: boolean } | null;
  automation?: {
    name: string;
  };
}

export default function ExecutionLogs() {
  const navigate = useNavigate();
  const [logs, setLogs] = useState<ExecutionLog[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedLog, setSelectedLog] = useState<ExecutionLog | null>(null);

  useEffect(() => {
    loadLogs();
  }, []);

  const loadLogs = async () => {
    setIsLoading(true);
    try {
      const { data, error } = await supabase
        .from('execution_logs')
        .select(`
          *,
          automation:automations(name)
        `)
        .order('created_at', { ascending: false })
        .limit(50);

      if (error) {
        console.error('Error loading logs:', error);
        toast.error('Erro ao carregar logs');
        return;
      }

      // Transform the data to handle the nested automation object
      const transformedLogs = (data || []).map(log => ({
        ...log,
        automation: log.automation ? { name: (log.automation as any).name } : undefined,
        screenshots: Array.isArray(log.screenshots) ? log.screenshots as string[] : null,
        extracted_data: log.extracted_data as Record<string, unknown> | null,
        webhook_response: log.webhook_response as { status?: number; ok?: boolean } | null,
      }));

      setLogs(transformedLogs);
    } catch (error) {
      console.error('Error loading logs:', error);
      toast.error('Erro ao carregar logs');
    } finally {
      setIsLoading(false);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success':
        return <CheckCircle className="h-4 w-4 text-success" />;
      case 'failed':
        return <XCircle className="h-4 w-4 text-destructive" />;
      case 'running':
        return <Play className="h-4 w-4 text-info animate-pulse" />;
      case 'pending':
        return <Clock className="h-4 w-4 text-warning" />;
      default:
        return <AlertTriangle className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const getStatusBadge = (status: string) => {
    const variants: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
      success: "default",
      failed: "destructive",
      running: "secondary",
      pending: "outline",
      cancelled: "outline"
    };
    
    const labels: Record<string, string> = {
      success: "Sucesso",
      failed: "Falhou",
      running: "Executando",
      pending: "Pendente",
      cancelled: "Cancelado"
    };

    return (
      <Badge variant={variants[status] || "outline"}>
        {labels[status] || status}
      </Badge>
    );
  };

  return (
    <div className="min-h-screen bg-background">
      <Header />

      {/* Sub-header */}
      <div className="border-b bg-card/50">
        <div className="container py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="icon" onClick={() => navigate('/')}>
                <ArrowLeft className="h-5 w-5" />
              </Button>
              <div>
                <h1 className="text-xl font-bold">Histórico de Execuções</h1>
                <p className="text-sm text-muted-foreground">
                  Visualize logs e resultados das automações
                </p>
              </div>
            </div>
            <Button 
              variant="outline" 
              size="sm" 
              onClick={loadLogs}
              disabled={isLoading}
              className="gap-2"
            >
              <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
              Atualizar
            </Button>
          </div>
        </div>
      </div>

      {/* Main content */}
      <main className="container py-6">
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
          </div>
        ) : logs.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <FileText className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium">Nenhuma execução encontrada</h3>
              <p className="text-sm text-muted-foreground">
                Execute uma automação para ver os logs aqui
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-4">
            {logs.map((log) => (
              <Card key={log.id} className="hover:shadow-md transition-shadow">
                <CardContent className="p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3">
                      {getStatusIcon(log.status)}
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">
                            {log.automation?.name || 'Automação desconhecida'}
                          </span>
                          {getStatusBadge(log.status)}
                        </div>
                        <p className="text-sm text-muted-foreground">
                          {formatDistanceToNow(new Date(log.started_at), { 
                            addSuffix: true, 
                            locale: ptBR 
                          })}
                          {log.total_steps && (
                            <> · {log.steps_completed || 0} de {log.total_steps} passos</>
                          )}
                        </p>
                        {log.error_message && (
                          <p className="text-sm text-destructive line-clamp-2">
                            {log.error_message}
                          </p>
                        )}
                      </div>
                    </div>
                    
                    <Dialog>
                      <DialogTrigger asChild>
                        <Button 
                          variant="outline" 
                          size="sm"
                          onClick={() => setSelectedLog(log)}
                        >
                          <ExternalLink className="h-4 w-4 mr-1" />
                          Detalhes
                        </Button>
                      </DialogTrigger>
                      <DialogContent className="max-w-4xl max-h-[90vh]">
                        <DialogHeader>
                          <DialogTitle className="flex items-center gap-2">
                            {getStatusIcon(log.status)}
                            <span>{log.automation?.name || 'Execução'}</span>
                            {getStatusBadge(log.status)}
                          </DialogTitle>
                        </DialogHeader>
                        
                        <Tabs defaultValue="info" className="mt-4">
                          <TabsList>
                            <TabsTrigger value="info">Informações</TabsTrigger>
                            <TabsTrigger value="errors">
                              Erros
                              {log.error_message && (
                                <Badge variant="destructive" className="ml-1 h-5 w-5 p-0 flex items-center justify-center">
                                  !
                                </Badge>
                              )}
                            </TabsTrigger>
                            <TabsTrigger value="screenshots">
                              Screenshots
                              {log.screenshots && log.screenshots.length > 0 && (
                                <Badge variant="secondary" className="ml-1">
                                  {log.screenshots.length}
                                </Badge>
                              )}
                            </TabsTrigger>
                            <TabsTrigger value="data">
                              Dados Extraídos
                            </TabsTrigger>
                          </TabsList>

                          <TabsContent value="info" className="space-y-4 mt-4">
                            <div className="grid grid-cols-2 gap-4">
                              <div>
                                <p className="text-sm text-muted-foreground">ID da Execução</p>
                                <p className="font-mono text-sm">{log.id}</p>
                              </div>
                              <div>
                                <p className="text-sm text-muted-foreground">Status</p>
                                <p>{getStatusBadge(log.status)}</p>
                              </div>
                              <div>
                                <p className="text-sm text-muted-foreground">Início</p>
                                <p className="text-sm">
                                  {new Date(log.started_at).toLocaleString('pt-BR')}
                                </p>
                              </div>
                              <div>
                                <p className="text-sm text-muted-foreground">Fim</p>
                                <p className="text-sm">
                                  {log.finished_at 
                                    ? new Date(log.finished_at).toLocaleString('pt-BR')
                                    : '-'
                                  }
                                </p>
                              </div>
                              <div>
                                <p className="text-sm text-muted-foreground">Passos</p>
                                <p className="text-sm">
                                  {log.steps_completed || 0} / {log.total_steps || 0}
                                </p>
                              </div>
                              <div>
                                <p className="text-sm text-muted-foreground">Webhook</p>
                                <p className="text-sm">
                                  {log.webhook_response 
                                    ? (log.webhook_response.ok ? '✅ Enviado' : `❌ Erro ${log.webhook_response.status}`)
                                    : 'Não configurado'
                                  }
                                </p>
                              </div>
                            </div>
                          </TabsContent>

                          <TabsContent value="errors" className="mt-4">
                            {log.error_message ? (
                              <ScrollArea className="h-[300px]">
                                <Card className="border-destructive/50 bg-destructive/5">
                                  <CardContent className="p-4">
                                    <pre className="whitespace-pre-wrap text-sm text-destructive font-mono">
                                      {log.error_message}
                                    </pre>
                                  </CardContent>
                                </Card>
                              </ScrollArea>
                            ) : (
                              <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                                <CheckCircle className="h-8 w-8 mb-2 text-success" />
                                <p>Nenhum erro registrado</p>
                              </div>
                            )}
                          </TabsContent>

                          <TabsContent value="screenshots" className="mt-4">
                            {log.screenshots && log.screenshots.length > 0 ? (
                              <ScrollArea className="h-[400px]">
                                <div className="grid grid-cols-2 gap-4">
                                  {log.screenshots.map((screenshot, index) => (
                                    <div key={index} className="relative group">
                                      <img
                                        src={`data:image/png;base64,${screenshot}`}
                                        alt={`Screenshot ${index + 1}`}
                                        className="rounded-lg border shadow-sm w-full"
                                      />
                                      <div className="absolute bottom-2 left-2 bg-background/80 rounded px-2 py-1 text-xs">
                                        Passo {index + 1}
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              </ScrollArea>
                            ) : (
                              <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                                <ImageIcon className="h-8 w-8 mb-2" />
                                <p>Nenhum screenshot capturado</p>
                              </div>
                            )}
                          </TabsContent>

                          <TabsContent value="data" className="mt-4">
                            {log.extracted_data && Object.keys(log.extracted_data).length > 0 ? (
                              <ScrollArea className="h-[300px]">
                                <pre className="bg-muted p-4 rounded-lg text-sm font-mono overflow-auto">
                                  {JSON.stringify(log.extracted_data, null, 2)}
                                </pre>
                              </ScrollArea>
                            ) : (
                              <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                                <FileText className="h-8 w-8 mb-2" />
                                <p>Nenhum dado extraído</p>
                              </div>
                            )}
                          </TabsContent>
                        </Tabs>
                      </DialogContent>
                    </Dialog>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
