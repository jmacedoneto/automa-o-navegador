import { useState, useEffect, useCallback } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import {
  Video,
  Square,
  Loader2,
  ExternalLink,
  Circle,
  AlertTriangle,
  Sparkles,
  Globe,
} from "lucide-react";
import { toast } from "sonner";
import { AutomationStep } from "@/types/automation";
import {
  startRecordingSession,
  stopRecordingSession,
  CapturedAction,
  RecordingSession,
} from "@/services/recordingService";

type RecordingState = 'idle' | 'starting' | 'recording' | 'processing' | 'complete' | 'error';

interface RecordingModalProps {
  isOpen: boolean;
  onClose: () => void;
  onStepsGenerated: (steps: AutomationStep[], erpUrl: string, notes?: string) => void;
}

export function RecordingModal({ isOpen, onClose, onStepsGenerated }: RecordingModalProps) {
  const [state, setState] = useState<RecordingState>('idle');
  const [erpUrl, setErpUrl] = useState("");
  const [session, setSession] = useState<RecordingSession | null>(null);
  const [capturedActions, setCapturedActions] = useState<CapturedAction[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [recordingDuration, setRecordingDuration] = useState(0);

  // Timer for recording duration
  useEffect(() => {
    let interval: number | null = null;
    
    if (state === 'recording') {
      interval = window.setInterval(() => {
        setRecordingDuration(prev => prev + 1);
      }, 1000);
    } else {
      setRecordingDuration(0);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [state]);

  // Reset state when modal closes
  useEffect(() => {
    if (!isOpen) {
      setState('idle');
      setErpUrl("");
      setSession(null);
      setCapturedActions([]);
      setError(null);
      setRecordingDuration(0);
    }
  }, [isOpen]);

  const handleStartRecording = async () => {
    if (!erpUrl.trim()) {
      toast.error("Por favor, insira a URL do ERP");
      return;
    }

    // Validate URL
    try {
      new URL(erpUrl);
    } catch {
      toast.error("URL inválida. Inclua http:// ou https://");
      return;
    }

    setState('starting');
    setError(null);

    try {
      const recordingSession = await startRecordingSession(erpUrl);
      setSession(recordingSession);
      setState('recording');
      toast.success("Gravação iniciada! Interaja com o browser na nova janela.");
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Erro ao iniciar gravação';
      setError(message);
      setState('error');
      toast.error(message);
    }
  };

  const handleAddAction = useCallback((action: CapturedAction) => {
    setCapturedActions(prev => [...prev, action]);
  }, []);

  const handleStopRecording = async () => {
    if (!session) return;

    setState('processing');

    try {
      const result = await stopRecordingSession(
        session.sessionId,
        session.erpUrl,
        capturedActions
      );

      if (result.success && result.steps.length > 0) {
        setState('complete');
        toast.success(`${result.steps.length} passos gerados com sucesso!`);
        
        // Delay to show success state, then pass steps to parent
        setTimeout(() => {
          onStepsGenerated(result.steps, session.erpUrl, result.notes);
          onClose();
        }, 1000);
      } else {
        throw new Error(result.error || 'Nenhum passo gerado');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Erro ao processar gravação';
      setError(message);
      setState('error');
      toast.error(message);
    }
  };

  const handleOpenLiveView = () => {
    if (session?.liveUrl) {
      window.open(session.liveUrl, '_blank', 'width=1200,height=800');
    }
  };

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const renderContent = () => {
    switch (state) {
      case 'idle':
        return (
          <div className="space-y-6">
            <div className="text-center py-4">
              <div className="w-16 h-16 mx-auto bg-primary/10 rounded-full flex items-center justify-center mb-4">
                <Video className="h-8 w-8 text-primary" />
              </div>
              <h3 className="text-lg font-medium mb-2">Gravar Nova Automação</h3>
              <p className="text-sm text-muted-foreground">
                Abra o navegador remoto, faça as ações manualmente, e a IA vai aprender automaticamente.
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="erp-url">URL do ERP</Label>
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Globe className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="erp-url"
                    placeholder="https://seu-erp.com.br"
                    value={erpUrl}
                    onChange={(e) => setErpUrl(e.target.value)}
                    className="pl-10"
                  />
                </div>
              </div>
              <p className="text-xs text-muted-foreground">
                Insira a URL inicial do sistema que deseja automatizar
              </p>
            </div>

            <Button 
              onClick={handleStartRecording} 
              className="w-full gap-2"
              disabled={!erpUrl.trim()}
            >
              <Video className="h-4 w-4" />
              Iniciar Gravação
            </Button>
          </div>
        );

      case 'starting':
        return (
          <div className="py-12 text-center space-y-4">
            <Loader2 className="h-12 w-12 animate-spin mx-auto text-primary" />
            <div>
              <h3 className="text-lg font-medium">Iniciando sessão...</h3>
              <p className="text-sm text-muted-foreground">
                Conectando ao navegador remoto
              </p>
            </div>
          </div>
        );

      case 'recording':
        return (
          <div className="space-y-6">
            {/* Recording indicator */}
            <div className="flex items-center justify-between p-4 bg-destructive/10 border border-destructive/20 rounded-lg">
              <div className="flex items-center gap-3">
                <Circle className="h-4 w-4 text-destructive fill-destructive animate-pulse" />
                <span className="font-medium text-destructive">Gravando...</span>
              </div>
              <Badge variant="outline" className="font-mono">
                {formatDuration(recordingDuration)}
              </Badge>
            </div>

            {/* Instructions */}
            <div className="bg-muted/50 rounded-lg p-4 space-y-3">
              <h4 className="font-medium">Como gravar:</h4>
              <ol className="text-sm text-muted-foreground space-y-2 list-decimal list-inside">
                <li>Clique no botão abaixo para abrir o Chrome DevTools</li>
                <li>No DevTools, você verá a página do ERP carregada</li>
                <li>Faça as ações que deseja automatizar (cliques, digitação, navegação)</li>
                <li>Quando terminar, volte aqui e clique em "Finalizar"</li>
              </ol>
              <p className="text-xs text-muted-foreground italic">
                Nota: O DevTools abrirá em uma nova janela para permitir interação com o navegador remoto.
              </p>
            </div>

            {/* Open browser button */}
            <Button
              onClick={handleOpenLiveView}
              variant="outline"
              className="w-full gap-2"
            >
              <ExternalLink className="h-4 w-4" />
              Abrir Chrome DevTools
            </Button>

            {/* Actions counter */}
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Ações capturadas:</span>
              <Badge variant="secondary">{capturedActions.length}</Badge>
            </div>

            {/* Manual action buttons */}
            <div className="grid grid-cols-2 gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleAddAction({
                  type: 'click',
                  timestamp: Date.now(),
                  description: 'Clique manual registrado',
                })}
              >
                + Registrar Clique
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleAddAction({
                  type: 'navigate',
                  timestamp: Date.now(),
                  description: 'Navegação manual registrada',
                })}
              >
                + Registrar Navegação
              </Button>
            </div>

            {/* Stop button */}
            <Button 
              onClick={handleStopRecording}
              variant="destructive"
              className="w-full gap-2"
            >
              <Square className="h-4 w-4" />
              Finalizar Gravação
            </Button>
          </div>
        );

      case 'processing':
        return (
          <div className="py-12 text-center space-y-6">
            <div className="relative">
              <Loader2 className="h-12 w-12 animate-spin mx-auto text-primary" />
              <Sparkles className="h-5 w-5 absolute top-0 right-1/3 text-accent animate-pulse" />
            </div>
            <div>
              <h3 className="text-lg font-medium">Analisando suas ações...</h3>
              <p className="text-sm text-muted-foreground">
                A IA está gerando os passos de automação
              </p>
            </div>
            <Progress value={66} className="w-full max-w-xs mx-auto" />
          </div>
        );

      case 'complete':
        return (
          <div className="py-12 text-center space-y-4">
            <div className="w-16 h-16 mx-auto bg-success/10 rounded-full flex items-center justify-center">
              <Sparkles className="h-8 w-8 text-success" />
            </div>
            <div>
              <h3 className="text-lg font-medium text-success">Passos gerados!</h3>
              <p className="text-sm text-muted-foreground">
                Redirecionando para o editor...
              </p>
            </div>
          </div>
        );

      case 'error':
        return (
          <div className="py-8 text-center space-y-4">
            <div className="w-16 h-16 mx-auto bg-destructive/10 rounded-full flex items-center justify-center">
              <AlertTriangle className="h-8 w-8 text-destructive" />
            </div>
            <div>
              <h3 className="text-lg font-medium text-destructive">Erro na gravação</h3>
              <p className="text-sm text-muted-foreground">{error}</p>
            </div>
            <Button variant="outline" onClick={() => setState('idle')}>
              Tentar novamente
            </Button>
          </div>
        );
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Video className="h-5 w-5 text-primary" />
            Gravar Automação
          </DialogTitle>
          <DialogDescription>
            {state === 'idle' && "Grave suas ações no navegador e a IA criará os passos automaticamente."}
            {state === 'recording' && "Interaja com o navegador remoto. Suas ações serão analisadas."}
            {state === 'processing' && "Processando a gravação..."}
          </DialogDescription>
        </DialogHeader>

        {renderContent()}
      </DialogContent>
    </Dialog>
  );
}
