import { Automation } from "@/types/automation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { 
  Play, 
  Settings, 
  Trash2, 
  Clock, 
  CheckCircle2, 
  XCircle, 
  AlertCircle,
  ExternalLink,
  Zap
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { ptBR } from "date-fns/locale";
import { cn } from "@/lib/utils";

interface AutomationCardProps {
  automation: Automation;
  onEdit: (id: string) => void;
  onDelete: (id: string) => void;
  onToggleStatus: (id: string, isActive: boolean) => void;
  onExecute: (id: string) => void;
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

export function AutomationCard({ 
  automation, 
  onEdit, 
  onDelete, 
  onToggleStatus, 
  onExecute 
}: AutomationCardProps) {
  const statusConfig = getStatusConfig(automation.last_execution_status);
  const StatusIcon = statusConfig.icon;

  return (
    <Card 
      className={cn(
        "group relative overflow-hidden transition-all duration-300 hover:shadow-lg border-l-4",
        statusConfig.borderColor,
        !automation.is_active && "opacity-60"
      )}
    >
      {/* Decorative gradient */}
      <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-accent/5 opacity-0 transition-opacity group-hover:opacity-100" />
      
      <CardHeader className="relative pb-3">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <CardTitle className="text-lg truncate flex items-center gap-2">
              <Zap className="h-4 w-4 text-primary flex-shrink-0" />
              {automation.name}
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
        {/* Status e última execução */}
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

        {/* URLs e info */}
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

        {/* Ações */}
        <div className="flex items-center gap-2 pt-2">
          <Button 
            size="sm" 
            onClick={() => onExecute(automation.id)}
            disabled={!automation.is_active}
            className="gap-1.5 bg-primary hover:bg-primary/90"
          >
            <Play className="h-4 w-4" />
            Executar
          </Button>
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
