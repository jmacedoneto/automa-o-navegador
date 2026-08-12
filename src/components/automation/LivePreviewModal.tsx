import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import {
  Monitor,
  CheckCircle2,
  XCircle,
  Loader2,
  X,
  History
} from "lucide-react";
import { cn } from "@/lib/utils";
import { ExecutionSession } from "@/types/automation";
import { subscribeToExecution, getExecutionStatus } from "@/services/executionService";
import { Link } from "react-router-dom";

interface LivePreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  liveUrl: string | null;
  automationName: string;
  executionId: string | null;
}

export function LivePreviewModal({
  isOpen,
  onClose,
  liveUrl,
  automationName,
  executionId,
}: LivePreviewModalProps) {
  const [session, setSession] = useState<ExecutionSession>({
    executionId: executionId || '',
    status: 'starting',
    currentStep: 0,
    totalSteps: 0,
    latestScreenshot: undefined,
  });

  useEffect(() => {
    if (!executionId || !isOpen) return;

    // Initial fetch
    getExecutionStatus(executionId).then((status) => {
      if (status) {
        setSession(status);
      }
    });

    // Subscribe to updates
    const unsubscribe = subscribeToExecution(executionId, (updatedSession) => {
      setSession(updatedSession);
    });

    return () => {
      unsubscribe();
    };
  }, [executionId, isOpen]);


  const getStatusConfig = () => {
    switch (session.status) {
      case 'starting':
        return {
          icon: Loader2,
          label: 'Iniciando...',
          color: 'text-info',
          bgColor: 'bg-info/10',
          animate: true,
        };
      case 'running':
        return {
          icon: Monitor,
          label: 'Executando',
          color: 'text-warning',
          bgColor: 'bg-warning/10',
          animate: true,
        };
      case 'completed':
      case 'success':
        return {
          icon: CheckCircle2,
          label: 'Concluído',
          color: 'text-success',
          bgColor: 'bg-success/10',
          animate: false,
        };
      case 'failed':
        return {
          icon: XCircle,
          label: 'Falhou',
          color: 'text-destructive',
          bgColor: 'bg-destructive/10',
          animate: false,
        };
      default:
        return {
          icon: Loader2,
          label: 'Aguardando...',
          color: 'text-muted-foreground',
          bgColor: 'bg-muted',
          animate: true,
        };
    }
  };

  const statusConfig = getStatusConfig();
  const StatusIcon = statusConfig.icon;
  const progressPercent = session.totalSteps > 0 
    ? (session.currentStep / session.totalSteps) * 100 
    : 0;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-5xl h-[85vh] flex flex-col p-0 gap-0">
        <DialogHeader className="px-6 py-4 border-b bg-card">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-primary/10">
                <Monitor className="h-5 w-5 text-primary" />
              </div>
              <div>
                <DialogTitle className="text-lg">Live Preview</DialogTitle>
                <DialogDescription className="text-sm">
                  {automationName}
                </DialogDescription>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Badge 
                variant="secondary" 
                className={cn("gap-1.5", statusConfig.bgColor, statusConfig.color)}
              >
                <StatusIcon className={cn("h-3.5 w-3.5", statusConfig.animate && "animate-spin")} />
                {statusConfig.label}
              </Badge>
              <Button
                variant="ghost"
                size="icon"
                onClick={onClose}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          </div>
          
          {/* Progress bar */}
          <div className="mt-4 space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">
                Progresso: Passo {session.currentStep} de {session.totalSteps}
              </span>
              <span className="font-medium">{Math.round(progressPercent)}%</span>
            </div>
            <Progress value={progressPercent} className="h-2" />
          </div>
        </DialogHeader>

        {/* Live preview area */}
        <div className="flex-1 relative bg-muted/30 overflow-hidden">
          {session.latestScreenshot ? (
            <>
              <img
                src={`data:image/png;base64,${session.latestScreenshot}`}
                alt="Browser screenshot"
                className="w-full h-full object-contain"
              />
              {/* Live indicator */}
              {(session.status === 'running' || session.status === 'starting') && (
                <div className="absolute top-4 left-4 flex items-center gap-2 bg-destructive/90 text-destructive-foreground px-3 py-1.5 rounded-full text-sm font-medium">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-white opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-white"></span>
                  </span>
                  AO VIVO
                </div>
              )}
            </>
          ) : (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center space-y-4 max-w-sm px-4">
                {session.status === 'starting' || session.status === 'queued' ? (
                  <>
                    <Loader2 className="h-10 w-10 animate-spin text-primary mx-auto" />
                    <p className="text-muted-foreground font-medium">Iniciando automação...</p>
                    <p className="text-sm text-muted-foreground">O browser será exibido assim que a primeira página carregar</p>
                  </>
                ) : session.status === 'running' ? (
                  <>
                    <Monitor className="h-10 w-10 text-warning mx-auto" />
                    <p className="text-muted-foreground font-medium">Executando passos...</p>
                    <p className="text-sm text-muted-foreground">
                      {session.currentStep} de {session.totalSteps} passos concluídos
                    </p>
                    <p className="text-xs text-muted-foreground">A captura de tela aparecerá após o primeiro acesso a uma página</p>
                  </>
                ) : session.status === 'success' || session.status === 'completed' ? (
                  <>
                    <CheckCircle2 className="h-10 w-10 text-success mx-auto" />
                    <p className="font-medium text-success">Execução concluída!</p>
                  </>
                ) : session.status === 'failed' ? (
                  <>
                    <XCircle className="h-10 w-10 text-destructive mx-auto" />
                    <p className="font-medium text-destructive">Execução falhou</p>
                  </>
                ) : (
                  <>
                    <Loader2 className="h-10 w-10 animate-spin text-primary mx-auto" />
                    <p className="text-muted-foreground">Aguardando...</p>
                  </>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        {(session.status === 'completed' || session.status === 'success' || session.status === 'failed') && (
          <div className="px-6 py-4 border-t bg-card">
            <div className="flex items-center justify-between">
              <p className={cn("text-sm font-medium", statusConfig.color)}>
                {session.status === 'failed' 
                  ? 'A execução falhou. Verifique os logs para mais detalhes.'
                  : `Execução concluída! ${session.currentStep} passos executados.`
                }
              </p>
              <div className="flex items-center gap-2">
                <Button variant="outline" asChild className="gap-1.5">
                  <Link to="/logs">
                    <History className="h-4 w-4" />
                    Ver Logs
                  </Link>
                </Button>
                <Button onClick={onClose}>
                  Fechar
                </Button>
              </div>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
