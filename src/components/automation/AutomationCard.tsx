import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Automation, Schedule } from "@/types/automation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Play,
  Settings,
  Trash2,
  Clock,
  CheckCircle2,
  XCircle,
  AlertCircle,
  ExternalLink,
  Zap,
  Monitor,
  ChevronDown,
  ChevronUp,
  Copy,
  History,
  CalendarClock,
} from "lucide-react";
import { formatDistanceToNow, format } from "date-fns";
import { ptBR } from "date-fns/locale";
import { cn } from "@/lib/utils";
import { fetchExecutionLogs } from "@/services/automationService";

interface AutomationCardProps {
  automation: Automation;
  schedules?: Schedule[];
  onEdit: (id: string) => void;
  onDelete: (id: string) => void;
  onClone: (id: string) => void;
  onToggleStatus: (id: string, isActive: boolean) => void;
  onExecute: (id: string, withLivePreview?: boolean) => void;
}

const DAY_NAMES = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'];

function scheduleLabel(s: Schedule): string {
  switch (s.schedule_type) {
    case 'daily':   return `Diário às ${s.time_of_day || ''}`;
    case 'weekly': {
      const days = (s.days_of_week || []).map(d => DAY_NAMES[d]).join(', ');
      return `${days || 'Semanal'} às ${s.time_of_day || ''}`;
    }
    case 'monthly': return `Mensal às ${s.time_of_day || ''}`;
    case 'interval': return `A cada ${s.interval_minutes} min`;
    case 'cron':   return s.cron_expression || 'Cron';
    case 'once':   return s.next_run_at ? `Uma vez: ${new Date(s.next_run_at).toLocaleString('pt-BR')}` : 'Uma vez';
    default: return '';
  }
}

function getStatusConfig(status?: string) {
  switch (status) {
    case 'success':
      return {
        icon: CheckCircle2,
        label: 'Sucesso',
        color: 'text-success',
        bgColor: 'bg-success/10',
        borderColor: 'border-l-success',
      };
    case 'failed':
      return {
        icon: XCircle,
        label: 'Falhou',
        color: 'text-destructive',
        bgColor: 'bg-destructive/10',
        borderColor: 'border-l-destructive',
      };
    case 'running':
      return {
        icon: Clock,
        label: 'Executando',
        color: 'text-warning',
        bgColor: 'bg-warning/10',
        borderColor: 'border-l-warning',
      };
    case 'pending':
      return {
        icon: Clock,
        label: 'Pendente',
        color: 'text-info',
        bgColor: 'bg-info/10',
        borderColor: 'border-l-info',
      };
    default:
      return {
        icon: AlertCircle,
        label: 'Nunca executado',
        color: 'text-muted-foreground',
        bgColor: 'bg-muted',
        borderColor: 'border-l-muted-foreground',
      };
  }
}

function StatusDot({ status }: { status: string }) {
  const colors: Record<string, string> = {
    success: 'bg-green-500',
    failed: 'bg-red-500',
    running: 'bg-yellow-500',
    pending: 'bg-blue-400',
    cancelled: 'bg-gray-400',
  };
  return (
    <span className={cn("inline-block h-2 w-2 rounded-full flex-shrink-0", colors[status] ?? 'bg-gray-300')} />
  );
}

function ExecutionHistory({ automationId }: { automationId: string }) {
  const { data: logs, isLoading } = useQuery({
    queryKey: ['execution_logs', automationId],
    queryFn: () => fetchExecutionLogs(automationId, 8),
    staleTime: 30_000,
  });

  if (isLoading) {
    return <p className="text-xs text-muted-foreground py-2 text-center">Carregando...</p>;
  }

  if (!logs || logs.length === 0) {
    return <p className="text-xs text-muted-foreground py-2 text-center">Nenhuma execução registrada</p>;
  }

  return (
    <div className="space-y-1 pt-1">
      {logs.map((log) => {
        const duration =
          log.finished_at
            ? Math.round((new Date(log.finished_at).getTime() - new Date(log.started_at).getTime()) / 1000)
            : null;

        return (
          <div
            key={log.id}
            className="flex items-center gap-2 rounded-md px-2 py-1.5 text-xs hover:bg-muted/50"
          >
            <StatusDot status={log.status} />
            <span className="text-muted-foreground w-28 flex-shrink-0">
              {format(new Date(log.started_at), "dd/MM/yy HH:mm", { locale: ptBR })}
            </span>
            <span className={cn(
              "flex-1 truncate",
              log.status === 'failed' ? 'text-destructive' : 'text-foreground'
            )}>
              {log.status === 'failed' && log.error_message
                ? log.error_message
                : log.status === 'success'
                  ? `${log.steps_completed ?? 0}/${log.total_steps ?? 0} passos`
                  : log.status === 'cancelled'
                    ? 'Cancelado'
                    : log.status}
            </span>
            {duration !== null && (
              <span className="text-muted-foreground flex-shrink-0">{duration}s</span>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function AutomationCard({
  automation,
  schedules = [],
  onEdit,
  onDelete,
  onClone,
  onToggleStatus,
  onExecute
}: AutomationCardProps) {
  const [showHistory, setShowHistory] = useState(false);
  const statusConfig = getStatusConfig(automation.last_execution_status);
  const StatusIcon = statusConfig.icon;
  const activeSchedules = schedules.filter(s => s.is_active);

  return (
    <Card
      className={cn(
        "group relative overflow-hidden transition-all duration-300 hover:shadow-lg border-l-4",
        statusConfig.borderColor,
        !automation.is_active && "opacity-60"
      )}
    >
      <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-accent/5 opacity-0 transition-opacity group-hover:opacity-100" />

      <CardHeader className="relative pb-3">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <CardTitle className="text-lg truncate flex items-center gap-2">
              <Zap className="h-4 w-4 text-primary flex-shrink-0" />
              {automation.name}
              {automation.last_execution_status && (
                <StatusDot status={automation.last_execution_status} />
              )}
            </CardTitle>
            {automation.description && (
              <CardDescription className="mt-1 truncate">
                {automation.description}
              </CardDescription>
            )}
          </div>
          <Switch
            checked={automation.is_active ?? true}
            onCheckedChange={(checked) => onToggleStatus(automation.id, checked)}
            className="data-[state=checked]:bg-primary"
          />
        </div>
      </CardHeader>
      <CardContent className="relative space-y-4">
        <div className={cn("flex items-center gap-2 rounded-lg px-3 py-2 text-sm", statusConfig.bgColor)}>
          <StatusIcon className={cn("h-4 w-4", statusConfig.color)} />
          <span className={statusConfig.color}>{statusConfig.label}</span>
          {automation.last_execution_at && (
            <span className="text-muted-foreground">
              · {formatDistanceToNow(new Date(automation.last_execution_at), {
                addSuffix: true,
                locale: ptBR
              })}
            </span>
          )}
        </div>

        <div className="flex flex-wrap gap-2">
          <Badge variant="secondary" className="text-xs font-medium">
            {automation.steps?.length || 0} passos
          </Badge>
          {automation.erp_url && (
            <Badge variant="outline" className="text-xs gap-1">
              <ExternalLink className="h-3 w-3" />
              ERP
            </Badge>
          )}
          {automation.webhook_url && (
            <Badge variant="outline" className="text-xs bg-accent/10 border-accent/30 text-accent-foreground">
              Webhook
            </Badge>
          )}
        </div>

        {/* Agendamentos ativos */}
        {activeSchedules.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {activeSchedules.map(s => (
              <span key={s.id} className="inline-flex items-center gap-1 rounded-full bg-primary/10 border border-primary/20 px-2.5 py-0.5 text-xs text-primary font-medium">
                <CalendarClock className="h-3 w-3 flex-shrink-0" />
                {scheduleLabel(s)}
              </span>
            ))}
          </div>
        )}

        {/* Histórico de execuções colapsável */}
        <div className="border-t pt-2">
          <button
            onClick={() => setShowHistory((v) => !v)}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground w-full"
          >
            <History className="h-3.5 w-3.5" />
            Histórico de execuções
            {showHistory ? <ChevronUp className="h-3 w-3 ml-auto" /> : <ChevronDown className="h-3 w-3 ml-auto" />}
          </button>
          {showHistory && <ExecutionHistory automationId={automation.id} />}
        </div>

        <div className="flex items-center gap-2 pt-1">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                size="sm"
                disabled={!automation.is_active}
                className="gap-1.5 bg-primary hover:bg-primary/90"
              >
                <Play className="h-4 w-4" />
                Executar
                <ChevronDown className="h-3 w-3 ml-1" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              <DropdownMenuItem onClick={() => onExecute(automation.id, false)}>
                <Play className="h-4 w-4 mr-2" />
                Executar em Background
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onExecute(automation.id, true)}>
                <Monitor className="h-4 w-4 mr-2" />
                Executar com Live Preview
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <Button
            size="sm"
            variant="outline"
            onClick={() => onEdit(automation.id)}
            className="gap-1.5"
          >
            <Settings className="h-4 w-4" />
            Editar
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => onClone(automation.id)}
            title="Clonar automação"
          >
            <Copy className="h-4 w-4" />
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="text-destructive hover:text-destructive hover:bg-destructive/10 ml-auto"
            onClick={() => onDelete(automation.id)}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
