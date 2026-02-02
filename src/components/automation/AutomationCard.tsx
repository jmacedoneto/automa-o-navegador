import { Automation } from "@/types/automation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { 
  Play, 
  Pause, 
  Settings, 
  Trash2, 
  Clock, 
  CheckCircle2, 
  XCircle, 
  AlertCircle,
  ExternalLink
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { ptBR } from "date-fns/locale";

interface AutomationCardProps {
  automation: Automation;
  onEdit: (id: string) => void;
  onDelete: (id: string) => void;
  onToggleStatus: (id: string, isActive: boolean) => void;
  onExecute: (id: string) => void;
}

function getStatusIcon(status?: string) {
  switch (status) {
    case 'success':
      return <CheckCircle2 className="h-4 w-4 text-primary" />;
    case 'failed':
      return <XCircle className="h-4 w-4 text-destructive" />;
    case 'running':
      return <Clock className="h-4 w-4 text-accent-foreground animate-pulse" />;
    default:
      return <AlertCircle className="h-4 w-4 text-muted-foreground" />;
  }
}

function getStatusLabel(status?: string) {
  switch (status) {
    case 'success':
      return 'Sucesso';
    case 'failed':
      return 'Falhou';
    case 'running':
      return 'Executando';
    case 'pending':
      return 'Pendente';
    default:
      return 'Nunca executado';
  }
}

export function AutomationCard({ 
  automation, 
  onEdit, 
  onDelete, 
  onToggleStatus, 
  onExecute 
}: AutomationCardProps) {
  return (
    <Card className={`transition-all ${!automation.is_active ? 'opacity-60' : ''}`}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0">
            <CardTitle className="text-lg truncate">{automation.name}</CardTitle>
            {automation.description && (
              <CardDescription className="mt-1 truncate">
                {automation.description}
              </CardDescription>
            )}
          </div>
          <Switch
            checked={automation.is_active ?? true}
            onCheckedChange={(checked) => onToggleStatus(automation.id, checked)}
          />
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Status e última execução */}
        <div className="flex items-center gap-2 text-sm">
          {getStatusIcon(automation.last_execution_status)}
          <span className="text-muted-foreground">
            {getStatusLabel(automation.last_execution_status)}
          </span>
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
          <Badge variant="outline" className="text-xs">
            {automation.steps?.length || 0} passos
          </Badge>
          {automation.erp_url && (
            <Badge variant="secondary" className="text-xs">
              <ExternalLink className="h-3 w-3 mr-1" />
              ERP
            </Badge>
          )}
          {automation.webhook_url && (
            <Badge variant="secondary" className="text-xs">
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
          >
            <Play className="h-4 w-4 mr-1" />
            Executar
          </Button>
          <Button 
            size="sm" 
            variant="outline"
            onClick={() => onEdit(automation.id)}
          >
            <Settings className="h-4 w-4 mr-1" />
            Editar
          </Button>
          <Button 
            size="sm" 
            variant="ghost"
            className="text-destructive hover:text-destructive hover:bg-destructive/10"
            onClick={() => onDelete(automation.id)}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
