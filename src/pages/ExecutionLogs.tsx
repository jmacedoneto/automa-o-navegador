import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Header } from "@/components/layout/Header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { fetchExecutionLogs, cancelExecution } from "@/services/automationService";
import { fetchAutomations } from "@/services/automationService";
import { ExecutionLog, Automation } from "@/types/automation";
import { toast } from "sonner";
import {
  ArrowLeft, CheckCircle, XCircle, Clock, Play,
  Image as ImageIcon, FileText, AlertTriangle,
  Loader2, RefreshCw, ExternalLink, Square, Timer, Zap,
} from "lucide-react";
import { formatDistanceToNow, format, differenceInSeconds } from "date-fns";
import { ptBR } from "date-fns/locale";

export default function ExecutionLogs() {
  const navigate = useNavigate();
  const [logs, setLogs] = useState<ExecutionLog[]>([]);
  const [automationMap, setAutomationMap] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [cancellingId, setCancellingId] = useState<string | null>(null);

  const loadLogs = useCallback(async (silent = false) => {
    if (!silent) setIsLoading(true);
    try {
      const [data, automations] = await Promise.all([
        fetchExecutionLogs(undefined, 50),
        fetchAutomations(),
      ]);
      setLogs(data);
      setAutomationMap(
        Object.fromEntries((automations as Automation[]).map((a) => [a.id, a.name]))
      );
    } catch {
      if (!silent) toast.error("Erro ao carregar logs");
    } finally {
      if (!silent) setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadLogs();
    const interval = setInterval(() => {
      setLogs((prev) => {
        const hasRunning = prev.some(l => l.status === "running" || l.status === "pending");
        if (hasRunning) loadLogs(true);
        return prev;
      });
    }, 3000);
    return () => clearInterval(interval);
  }, [loadLogs]);

  const handleCancel = async (logId: string) => {
    setCancellingId(logId);
    try {
      await cancelExecution(logId);
      toast.success("Execução cancelada");
      loadLogs();
    } catch {
      toast.error("Erro ao cancelar execução");
    } finally {
      setCancellingId(null);
    }
  };

  const getDuration = (log: ExecutionLog): string => {
    const start = new Date(log.started_at);
    const end = log.finished_at ? new Date(log.finished_at) : new Date();
    const secs = differenceInSeconds(end, start);
    if (secs < 60) return `${secs}s`;
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m}m ${s}s`;
  };

  const statusIcon = (s: string) => {
    if (s === "success")  return <CheckCircle className="h-4 w-4 text-green-500" />;
    if (s === "failed")   return <XCircle className="h-4 w-4 text-destructive" />;
    if (s === "running")  return <Play className="h-4 w-4 text-blue-400 animate-pulse" />;
    if (s === "pending")  return <Clock className="h-4 w-4 text-yellow-400" />;
    if (s === "cancelled") return <Square className="h-4 w-4 text-muted-foreground" />;
    return <AlertTriangle className="h-4 w-4 text-muted-foreground" />;
  };

  const statusBadge = (s: string) => {
    const v: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
      success: "default", failed: "destructive", running: "secondary",
      pending: "outline", cancelled: "outline",
    };
    const l: Record<string, string> = {
      success: "Sucesso", failed: "Falhou", running: "Executando",
      pending: "Pendente", cancelled: "Cancelado",
    };
    return <Badge variant={v[s] || "outline"}>{l[s] || s}</Badge>;
  };

  return (
    <div className="min-h-screen bg-background">
      <Header />

      <div className="border-b bg-card/50">
        <div className="container py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="icon" onClick={() => navigate("/")}>
              <ArrowLeft className="h-5 w-5" />
            </Button>
            <div>
              <h1 className="text-xl font-bold">Histórico de Execuções</h1>
              <p className="text-sm text-muted-foreground">
                {logs.length > 0 ? `${logs.length} registros` : "Visualize logs e resultados das automações"}
              </p>
            </div>
          </div>
          <Button variant="outline" size="sm" onClick={() => loadLogs()} disabled={isLoading} className="gap-2">
            <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
            Atualizar
          </Button>
        </div>
      </div>

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
              <p className="text-sm text-muted-foreground">Execute uma automação para ver os logs aqui</p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-2">
            {logs.map((log) => {
              const automationName = automationMap[log.automation_id] || log.automation_id;
              const duration = getDuration(log);
              const startedFmt = format(new Date(log.started_at), "dd/MM/yyyy HH:mm:ss", { locale: ptBR });

              return (
                <Card key={log.id} className="hover:shadow-md transition-shadow">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between gap-4">
                      {/* Left: icon + info */}
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="flex-shrink-0">{statusIcon(log.status)}</div>
                        <div className="min-w-0">
                          {/* Automation name + status */}
                          <div className="flex items-center gap-2 flex-wrap">
                            <Zap className="h-3.5 w-3.5 text-primary flex-shrink-0" />
                            <span className="font-semibold text-sm truncate">{automationName}</span>
                            {statusBadge(log.status)}
                          </div>
                          {/* Date + steps + duration */}
                          <div className="flex items-center gap-3 mt-0.5 text-xs text-muted-foreground flex-wrap">
                            <span>{startedFmt}</span>
                            <span>·</span>
                            <span>{formatDistanceToNow(new Date(log.started_at), { addSuffix: true, locale: ptBR })}</span>
                            {log.total_steps > 0 && (
                              <>
                                <span>·</span>
                                <span>{log.steps_completed}/{log.total_steps} passos</span>
                              </>
                            )}
                            <span>·</span>
                            <span className="flex items-center gap-1">
                              <Timer className="h-3 w-3" />{duration}
                            </span>
                          </div>
                          {/* Error message */}
                          {log.error_message && (
                            <p className="text-xs text-destructive mt-1 line-clamp-1">{log.error_message}</p>
                          )}
                        </div>
                      </div>

                      {/* Right: action buttons */}
                      <div className="flex gap-2 flex-shrink-0">
                        {(log.status === "running" || log.status === "pending") && (
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => handleCancel(log.id)}
                            disabled={cancellingId === log.id}
                          >
                            {cancellingId === log.id
                              ? <Loader2 className="h-4 w-4 animate-spin" />
                              : <><Square className="h-3 w-3 mr-1" />Parar</>
                            }
                          </Button>
                        )}
                        <Dialog>
                          <DialogTrigger asChild>
                            <Button variant="outline" size="sm">
                              <ExternalLink className="h-4 w-4 mr-1" />Detalhes
                            </Button>
                          </DialogTrigger>
                          <DialogContent className="max-w-4xl max-h-[90vh]">
                            <DialogHeader>
                              <DialogTitle className="flex items-center gap-2">
                                {statusIcon(log.status)}
                                <span className="truncate">{automationName}</span>
                                {statusBadge(log.status)}
                              </DialogTitle>
                            </DialogHeader>

                            <Tabs defaultValue="info" className="mt-4">
                              <TabsList>
                                <TabsTrigger value="info">Informações</TabsTrigger>
                                <TabsTrigger value="errors">Erros</TabsTrigger>
                                <TabsTrigger value="screenshots">
                                  Screenshots
                                  {log.screenshots?.length > 0 && (
                                    <Badge variant="secondary" className="ml-1">{log.screenshots.length}</Badge>
                                  )}
                                </TabsTrigger>
                                <TabsTrigger value="data">Dados Extraídos</TabsTrigger>
                              </TabsList>

                              <TabsContent value="info" className="space-y-4 mt-4">
                                <div className="grid grid-cols-2 gap-4 text-sm">
                                  <div><p className="text-muted-foreground text-xs mb-1">Automação</p><p className="font-semibold">{automationName}</p></div>
                                  <div><p className="text-muted-foreground text-xs mb-1">Status</p>{statusBadge(log.status)}</div>
                                  <div><p className="text-muted-foreground text-xs mb-1">Início</p><p>{startedFmt}</p></div>
                                  <div>
                                    <p className="text-muted-foreground text-xs mb-1">Término</p>
                                    <p>{log.finished_at ? format(new Date(log.finished_at), "dd/MM/yyyy HH:mm:ss", { locale: ptBR }) : "—"}</p>
                                  </div>
                                  <div><p className="text-muted-foreground text-xs mb-1">Duração</p><p>{duration}</p></div>
                                  <div><p className="text-muted-foreground text-xs mb-1">Passos</p><p>{log.steps_completed}/{log.total_steps}</p></div>
                                  <div className="col-span-2"><p className="text-muted-foreground text-xs mb-1">ID do Log</p><p className="font-mono text-xs">{log.id}</p></div>
                                </div>
                              </TabsContent>

                              <TabsContent value="errors" className="mt-4">
                                {log.error_message ? (
                                  <ScrollArea className="h-[300px]">
                                    <Card className="border-destructive/50 bg-destructive/5">
                                      <CardContent className="p-4">
                                        <pre className="whitespace-pre-wrap text-sm text-destructive font-mono">{log.error_message}</pre>
                                      </CardContent>
                                    </Card>
                                  </ScrollArea>
                                ) : (
                                  <div className="flex flex-col items-center py-8 text-muted-foreground">
                                    <CheckCircle className="h-8 w-8 mb-2 text-green-500" />
                                    <p>Nenhum erro registrado</p>
                                  </div>
                                )}
                              </TabsContent>

                              <TabsContent value="screenshots" className="mt-4">
                                {log.screenshots?.length > 0 ? (
                                  <ScrollArea className="h-[400px]">
                                    <div className="grid grid-cols-2 gap-4">
                                      {log.screenshots.map((s, i) => (
                                        <div key={i} className="relative">
                                          <img src={`data:image/jpeg;base64,${s}`} alt={`Screenshot ${i + 1}`} className="rounded-lg border w-full" />
                                          <div className="absolute bottom-2 left-2 bg-background/80 rounded px-2 py-1 text-xs">Passo {i + 1}</div>
                                        </div>
                                      ))}
                                    </div>
                                  </ScrollArea>
                                ) : (
                                  <div className="flex flex-col items-center py-8 text-muted-foreground">
                                    <ImageIcon className="h-8 w-8 mb-2" /><p>Nenhum screenshot capturado</p>
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
                                  <div className="flex flex-col items-center py-8 text-muted-foreground">
                                    <FileText className="h-8 w-8 mb-2" /><p>Nenhum dado extraído</p>
                                  </div>
                                )}
                              </TabsContent>
                            </Tabs>
                          </DialogContent>
                        </Dialog>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
