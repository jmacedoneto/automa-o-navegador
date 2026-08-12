import { useEffect, useRef, useState, useCallback } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Square, MousePointer, Navigation, Trash2, Chrome, CheckCircle2, Download } from "lucide-react";
import { AutomationStep } from "@/types/automation";
import { toast } from "sonner";

interface ExtensionRecorderProps {
  isOpen: boolean;
  onClose: () => void;
  onStepsReady: (steps: AutomationStep[]) => void;
  initialUrl?: string;
}

const ACTION_LABEL: Record<string, string> = {
  navigate: "Navegar", click: "Clicar", type: "Digitar",
  selectOption: "Selecionar", hover: "Hover", wait: "Aguardar",
  download: "Download", extractTable: "Extrair Tabela", extractText: "Extrair Texto",
};
const ACTION_COLOR: Record<string, string> = {
  navigate: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  click: "bg-orange-500/20 text-orange-400 border-orange-500/30",
  type: "bg-green-500/20 text-green-400 border-green-500/30",
  selectOption: "bg-purple-500/20 text-purple-400 border-purple-500/30",
};

const API_BASE = `${window.location.origin}/api`;
const EXT_DOWNLOAD_URL = `${window.location.origin}/chrome-extension-v2.zip`;

export function ExtensionRecorder({ isOpen, onClose, onStepsReady, initialUrl = "" }: ExtensionRecorderProps) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [steps, setSteps] = useState<AutomationStep[]>([]);
  const [recording, setRecording] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const stepsEndRef = useRef<HTMLDivElement>(null);
  const sessionIdRef = useRef<string | null>(null);

  // Auto-scroll
  useEffect(() => { stepsEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [steps]);

  // Cleanup on close
  useEffect(() => {
    if (!isOpen) {
      stopPolling();
      if (sessionId) {
        fetch(`${API_BASE}/automations/ext-session/${sessionId}`, { method: "DELETE" }).catch(() => {});
      }
      setSessionId(null);
      sessionIdRef.current = null;
      setSteps([]);
      setRecording(false);
    }
  }, [isOpen]);

  // Cleanup on unmount — stops the polling loop and deletes the backend
  // session regardless of `isOpen` state. Without this, leaving the
  // Record tab via tab-switch unmounts the component while polling is
  // still active and leaks a backend session.
  useEffect(() => {
    return () => {
      stopPolling();
      // Capture sessionId via ref to avoid stale closure.
      if (sessionIdRef.current) {
        fetch(`${API_BASE}/automations/ext-session/${sessionIdRef.current}`, { method: "DELETE" }).catch(() => {});
      }
    };
  }, []);

  const stopPolling = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  };

  const startPolling = useCallback((sid: string) => {
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/automations/ext-session/${sid}/steps`);
        if (!res.ok) return;
        const data = await res.json();
        setSteps(data.steps || []);
      } catch (_) {}
    }, 800);
  }, []);

  const handleStart = async () => {
    // Cria sessão no backend
    const res = await fetch(`${API_BASE}/automations/ext-session/create`, { method: "POST" });
    const { session_id } = await res.json();
    setSessionId(session_id);
    sessionIdRef.current = session_id;
    setSteps([]);
    setRecording(true);
    startPolling(session_id);

    // Abre nova aba com parâmetros — a extensão detecta e inicia gravação automaticamente
    const redirectUrl = initialUrl || "";
    const launchUrl = `${window.location.origin}?__autopilot_session=${session_id}&__autopilot_api=${encodeURIComponent(API_BASE)}${redirectUrl ? `&__autopilot_redirect=${encodeURIComponent(redirectUrl)}` : ""}`;
    window.open(launchUrl, "_blank");

    toast.success("Nova aba aberta! A extensão vai iniciar a gravação automaticamente.", { duration: 5000 });
  };

  const handleFinish = () => {
    stopPolling();
    if (steps.length === 0) { onClose(); return; }

    const normalized: AutomationStep[] = steps.map((s: any, i: number) => ({
      order: i + 1,
      action: s.action || "click",
      selector: s.selector || "",
      value: s.value || s.url || "",
      description: s.description || "",
      waitTime: s.waitTime || 500,
    }));
    onStepsReady(normalized);
    onClose();
  };

  const handleDeleteStep = async (index: number) => {
    if (!sessionId) return;
    const newSteps = steps.filter((_, i) => i !== index);
    setSteps(newSteps);
    // Atualiza no backend
    try {
      await fetch(`${API_BASE}/automations/ext-session/${sessionId}/steps`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newSteps),
      });
    } catch (_) {}
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-lg w-full flex flex-col gap-0 p-0 overflow-hidden">
        <DialogHeader className="px-4 py-3 border-b flex-row items-center justify-between space-y-0">
          <DialogTitle className="flex items-center gap-2 text-sm font-semibold">
            <span className={`w-2 h-2 rounded-full ${recording ? "bg-red-500 animate-pulse" : "bg-muted-foreground"}`} />
            Gravador de Automação
          </DialogTitle>
          <Badge variant={recording ? "default" : "secondary"} className="text-xs">
            {recording ? `Gravando — ${steps.length} passos` : "Aguardando"}
          </Badge>
        </DialogHeader>

        <div className="flex flex-col flex-1 p-4 gap-4">
          {!recording ? (
            /* ── Tela inicial ── */
            <div className="space-y-4">
              <div className="rounded-lg border bg-muted/30 p-4 space-y-2 text-sm">
                <p className="font-medium flex items-center gap-2">
                  <Chrome className="h-4 w-4" /> Como funciona
                </p>
                <ol className="list-decimal list-inside space-y-1 text-muted-foreground text-[13px]">
                  <li>Instale a extensão AutoPilot no Chrome</li>
                  <li>Clique em <strong>Iniciar Gravação</strong> abaixo</li>
                  <li>Navegue normalmente no Chrome — cada ação é gravada aqui</li>
                  <li>Quando terminar, clique em <strong>Finalizar</strong></li>
                </ol>
              </div>

              <div className="flex gap-2">
                <Button variant="outline" size="sm" className="gap-1.5" asChild>
                  <a href={EXT_DOWNLOAD_URL} download>
                    <Download className="h-3.5 w-3.5" /> Baixar Extensão
                  </a>
                </Button>
                <Button className="flex-1 gap-1.5" onClick={handleStart}>
                  <MousePointer className="h-3.5 w-3.5" /> Iniciar Gravação
                </Button>
              </div>
            </div>
          ) : (
            /* ── Gravando ── */
            <div className="flex flex-col gap-3 flex-1 min-h-0">
              <div className="rounded-md border bg-muted/20 px-3 py-2 text-[12px] text-muted-foreground space-y-1">
                <p>Navegue no Chrome com a extensão ativa. Os passos aparecem abaixo em tempo real.</p>
                {sessionId && (
                  <p className="font-mono text-[11px]">ID da sessão: <span className="text-foreground">{sessionId.slice(0, 16)}…</span></p>
                )}
              </div>

              <ScrollArea className="flex-1 min-h-[200px] max-h-[300px] border rounded-md">
                <div className="p-2 space-y-1">
                  {steps.length === 0 ? (
                    <div className="py-10 text-center text-xs text-muted-foreground space-y-2">
                      <MousePointer className="h-6 w-6 mx-auto opacity-30" />
                      <p>Nenhum passo ainda.<br />Ative a extensão e navegue no Chrome.</p>
                    </div>
                  ) : (
                    steps.map((step: any, i) => (
                      <div key={i} className="flex items-start gap-1.5 rounded-md border px-2 py-1.5 text-xs group hover:bg-muted/30">
                        <span className="text-muted-foreground font-mono w-4 shrink-0 pt-0.5 text-[10px]">{i + 1}</span>
                        <div className="flex-1 min-w-0 space-y-0.5">
                          <span className={`inline-block px-1.5 py-0.5 rounded border text-[10px] font-semibold ${ACTION_COLOR[step.action] ?? "bg-muted text-muted-foreground border-border"}`}>
                            {ACTION_LABEL[step.action] ?? step.action}
                          </span>
                          <p className="text-muted-foreground font-mono truncate text-[10px] leading-tight">
                            {step.value || step.url || step.selector || "—"}
                          </p>
                        </div>
                        <Button
                          variant="ghost" size="icon"
                          className="h-5 w-5 shrink-0 opacity-0 group-hover:opacity-100 text-destructive hover:text-destructive hover:bg-destructive/10"
                          onClick={() => handleDeleteStep(i)}
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </div>
                    ))
                  )}
                  <div ref={stepsEndRef} />
                </div>
              </ScrollArea>

              <Button
                className="w-full gap-2"
                variant={steps.length > 0 ? "default" : "outline"}
                onClick={handleFinish}
              >
                {steps.length > 0
                  ? <><CheckCircle2 className="h-3.5 w-3.5" />Finalizar e Salvar {steps.length} passos</>
                  : <><Square className="h-3.5 w-3.5" />Cancelar</>}
              </Button>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
