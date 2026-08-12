import { useEffect, useRef, useState, useCallback } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Loader2, Square, Globe, Trash2, Check, X,
  Eye, EyeOff, MousePointer, Navigation, Bot, Mic, MicOff,
  CheckCircle2, XCircle, Play,
} from "lucide-react";
import { AutomationStep } from "@/types/automation";
import { toast } from "sonner";

interface BrowserRecorderProps {
  isOpen: boolean;
  onClose: () => void;
  onStepsReady: (steps: AutomationStep[]) => void;
  initialUrl?: string;
}

type AgentAction = { action: string; description?: string; x?: number; y?: number; url?: string; value?: string; selector?: string };

type ServerMsg =
  | { type: "ready"; viewport: { w: number; h: number } }
  | { type: "screenshot"; data: string }
  | { type: "step_added"; step: AutomationStep }
  | { type: "steps_reset"; steps: AutomationStep[] }
  | { type: "steps"; steps: AutomationStep[] }
  | { type: "live_url"; url: string }
  | { type: "input_focused"; selector: string; is_password: boolean }
  | { type: "select_options"; selector: string; options: { value: string; label: string }[] }
  | { type: "agent_started" }
  | { type: "agent_action"; action: AgentAction }
  | { type: "agent_done"; success: boolean; message: string }
  | { type: "agent_error"; message: string }
  | { type: "error"; message: string };

const ACTION_LABEL: Record<string, string> = {
  navigate:     "Navegar",
  click:        "Clicar",
  type:         "Digitar",
  selectOption: "Selecionar",
  hover:        "Hover",
  wait:         "Aguardar",
  download:     "Download",
  extractTable: "Extrair Tabela",
  extractText:  "Extrair Texto",
};

const ACTION_COLOR: Record<string, string> = {
  navigate:     "bg-blue-500/20 text-blue-400 border-blue-500/30",
  click:        "bg-orange-500/20 text-orange-400 border-orange-500/30",
  type:         "bg-green-500/20 text-green-400 border-green-500/30",
  selectOption: "bg-purple-500/20 text-purple-400 border-purple-500/30",
  hover:        "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
};

export function BrowserRecorder({ isOpen, onClose, onStepsReady, initialUrl = "" }: BrowserRecorderProps) {
  const wsRef = useRef<WebSocket | null>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const popupRef = useRef<Window | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const shouldReconnectRef = useRef(false);

  const [connected, setConnected] = useState(false);
  const [hasScreenshot, setHasScreenshot] = useState(false);
  const [steps, setSteps] = useState<AutomationStep[]>([]);
  const [urlBar, setUrlBar] = useState(initialUrl);
  const [busy, setBusy] = useState(true);
  const [liveUrl, setLiveUrl] = useState("");
  const [popupBlocked, setPopupBlocked] = useState(false);

  // Type dialog (shown when server says an input was clicked)
  const [typeDialog, setTypeDialog] = useState<{ selector: string; is_password: boolean } | null>(null);
  const [typeValue, setTypeValue] = useState("");
  const [showPwd, setShowPwd] = useState(false);

  // Select dialog (shown when server sends select options)
  const [selectDialog, setSelectDialog] = useState<{ selector: string; options: { value: string; label: string }[] } | null>(null);

  // Agent mode
  const [agentMode, setAgentMode] = useState(false);
  const [agentInstruction, setAgentInstruction] = useState("");
  const [agentRunning, setAgentRunning] = useState(false);
  const [agentLog, setAgentLog] = useState<{ ok: boolean; text: string }[]>([]);

  // Agent mic
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  const stepsEndRef = useRef<HTMLDivElement>(null);
  const agentLogEndRef = useRef<HTMLDivElement>(null);

  const send = useCallback((msg: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  const openExternalWindow = useCallback((url: string) => {
    setLiveUrl(url);

    if (popupRef.current && !popupRef.current.closed) {
      popupRef.current.location.href = url;
      popupRef.current.focus();
      setPopupBlocked(false);
      return;
    }

    const win = window.open(url, "autopilot-recorder-live", "popup=yes,width=1440,height=960");
    popupRef.current = win;
    setPopupBlocked(!win);
  }, []);

  // Auto-scroll steps / agent log
  useEffect(() => { stepsEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [steps]);
  useEffect(() => { agentLogEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [agentLog]);

  // Open / close WebSocket when modal opens / closes
  useEffect(() => {
    if (!isOpen) {
      shouldReconnectRef.current = false;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      wsRef.current?.close();
      if (popupRef.current && !popupRef.current.closed) popupRef.current.close();
      return;
    }

    setConnected(false);
    setHasScreenshot(false);
    if (imgRef.current) imgRef.current.src = "";
    setSteps([]);
    setBusy(true);
    setLiveUrl("");
    setPopupBlocked(false);
    setTypeDialog(null);
    setSelectDialog(null);
    setAgentLog([]);
    setAgentRunning(false);
    setUrlBar(initialUrl);

    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${proto}//${window.location.host}/api/recording/ws`;

    const connect = (preserveSteps?: typeof steps) => {
      if (!shouldReconnectRef.current) return;
      setBusy(true);
      setConnected(false);
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      if (preserveSteps?.length) setSteps(preserveSteps);
      setupHandlers(ws, preserveSteps);
    };

    shouldReconnectRef.current = true;

    const setupHandlers = (ws: WebSocket, preserveSteps?: typeof steps) => {
      ws.onmessage = (e) => {
        const msg: ServerMsg = JSON.parse(e.data);
        switch (msg.type) {
          case "ready":
            setConnected(true);
            setBusy(false);
            if (initialUrl) send({ type: "navigate", url: initialUrl });
            break;
          case "screenshot": {
            const fmt = (msg as ServerMsg & { fmt?: string }).fmt === "jpeg" ? "jpeg" : "png";
            if (imgRef.current) {
              imgRef.current.src = `data:image/${fmt};base64,${msg.data}`;
            }
            setHasScreenshot(true);
            setBusy(false);
            break;
          }
          case "live_url": {
            // wss:// e ws:// não abrem no browser — normaliza para https:// / http://
            const httpUrl = msg.url.replace(/^wss:\/\//, "https://").replace(/^ws:\/\//, "http://");
            openExternalWindow(httpUrl);
            break;
          }
          case "step_added":
            setSteps((prev) => [...prev, msg.step]);
            break;
          case "steps_reset":
            setSteps(msg.steps);
            break;
          case "steps":
            shouldReconnectRef.current = false; // deliberate close — no reconnect
            onStepsReady(msg.steps);
            ws.close();
            onClose();
            break;
          case "input_focused":
            setTypeDialog({ selector: msg.selector, is_password: msg.is_password });
            setTypeValue("");
            setShowPwd(false);
            setBusy(false);
            break;
          case "select_options":
            setSelectDialog({ selector: msg.selector, options: msg.options });
            setBusy(false);
            break;
          case "agent_started":
            setAgentLog([{ ok: true, text: "Agente iniciado..." }]);
            break;
          case "agent_action": {
            const a = msg.action;
            const desc = a.description || a.action;
            setAgentLog((prev) => [...prev, { ok: true, text: desc }]);
            break;
          }
          case "agent_done":
            setAgentRunning(false);
            setBusy(false);
            setAgentLog((prev) => [...prev, {
              ok: msg.success,
              text: msg.success ? `✓ ${msg.message || "Tarefa concluída!"}` : `✗ ${msg.message || "Tarefa não concluída"}`,
            }]);
            break;
          case "agent_error":
            setAgentRunning(false);
            setBusy(false);
            toast.error(msg.message);
            break;
          case "error":
            toast.error(msg.message);
            setBusy(false);
            break;
        }
      };

      ws.onerror = () => {
        setBusy(false);
      };

      ws.onclose = () => {
        setConnected(false);
        setBusy(false);
        if (shouldReconnectRef.current) {
          const snap = preserveSteps;
          reconnectTimerRef.current = setTimeout(() => connect(snap), 2500);
        }
      };
    };

    // Initial connection
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    setupHandlers(ws);

    return () => {
      shouldReconnectRef.current = false;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      ws.close();
      if (popupRef.current && !popupRef.current.closed) popupRef.current.close();
    };
  }, [isOpen, initialUrl, onClose, onStepsReady, openExternalWindow, send]);

  // ── Select option submit ─────────────────────────────────────────────────
  const handleSelectOption = (option: { value: string; label: string }) => {
    if (!selectDialog) return;
    setBusy(true);
    send({ type: "select_option", selector: selectDialog.selector, value: option.label, select_by: "label" });
    setSelectDialog(null);
  };

  // ── Agent mic ────────────────────────────────────────────────────────────
  const handleAgentMic = useCallback(async () => {
    if (isRecording) { mediaRecorderRef.current?.stop(); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream, { mimeType: "audio/webm" });
      audioChunksRef.current = [];
      mr.ondataavailable = (e) => { if (e.data.size > 0) audioChunksRef.current.push(e.data); };
      mr.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setIsRecording(false);
        const blob = new Blob(audioChunksRef.current, { type: "audio/webm" });
        setIsTranscribing(true);
        try {
          const fd = new FormData();
          fd.append("audio", blob, "audio.webm");
          const res = await fetch("/api/ai/transcribe", { method: "POST", body: fd });
          if (!res.ok) throw new Error(await res.text());
          const { text } = await res.json();
          if (text) setAgentInstruction((prev) => prev ? prev + " " + text : text);
        } catch { toast.error("Erro ao transcrever áudio"); }
        finally { setIsTranscribing(false); }
      };
      mediaRecorderRef.current = mr;
      mr.start();
      setIsRecording(true);
    } catch { toast.error("Microfone não disponível"); }
  }, [isRecording]);

  // ── Start agent ───────────────────────────────────────────────────────────
  const handleAgentRun = () => {
    if (!agentInstruction.trim() || agentRunning) return;
    setAgentRunning(true);
    setBusy(true);
    setAgentLog([]);
    send({ type: "agent_run", instruction: agentInstruction });
  };

  // ── Click on screenshot ──────────────────────────────────────────────────
  const handleScreenshotClick = useCallback((e: React.MouseEvent<HTMLImageElement>) => {
    if (!connected || busy || agentMode) return;
    const img = e.currentTarget;
    const rect = img.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setBusy(true);
    send({ type: "click", x, y, display_w: rect.width, display_h: rect.height });
  }, [connected, busy, agentMode, send]);

  // ── Navigate ─────────────────────────────────────────────────────────────
  const handleNavigate = () => {
    let url = urlBar.trim();
    if (!url) return;
    if (!url.startsWith("http")) url = "https://" + url;
    setUrlBar(url);
    setBusy(true);
    send({ type: "navigate", url });
  };

  // ── Type dialog submit ───────────────────────────────────────────────────
  const handleTypeSubmit = () => {
    if (!typeDialog) return;
    setBusy(true);
    send({ type: "type", selector: typeDialog.selector, value: typeValue, is_password: typeDialog.is_password });
    setTypeDialog(null);
    setTypeValue("");
  };

  // ── Delete step ───────────────────────────────────────────────────────────
  const handleDeleteStep = (index: number) => {
    send({ type: "delete_step", index });
  };

  // ── Stop recording ────────────────────────────────────────────────────────
  const handleStop = () => {
    shouldReconnectRef.current = false;
    if (steps.length === 0) { onClose(); return; }
    send({ type: "stop" });
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-[95vw] w-[1300px] h-[88vh] flex flex-col p-0 gap-0 overflow-hidden">
        <DialogHeader className="px-4 py-2.5 border-b shrink-0 flex-row items-center justify-between space-y-0">
          <DialogTitle className="flex items-center gap-2 text-sm font-semibold">
            <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse shrink-0" />
            Gravador de Automação
          </DialogTitle>
            <div className="flex items-center gap-2 shrink-0">
            {/* Mode toggle */}
            <div className="flex items-center rounded-md border text-xs overflow-hidden">
              <button
                className={`px-3 py-1 flex items-center gap-1.5 transition-colors ${!agentMode ? "bg-primary text-primary-foreground" : "hover:bg-muted"}`}
                onClick={() => setAgentMode(false)}
              >
                <MousePointer className="h-3 w-3" /> Manual
              </button>
              <button
                className={`px-3 py-1 flex items-center gap-1.5 transition-colors ${agentMode ? "bg-primary text-primary-foreground" : "hover:bg-muted"}`}
                onClick={() => setAgentMode(true)}
              >
                <Bot className="h-3 w-3" /> Agente IA
              </button>
            </div>
            <Badge variant={connected ? "default" : "secondary"} className="text-xs">
              {connected ? "Conectado" : busy ? "Reconectando..." : "Desconectado"}
            </Badge>
          </div>
        </DialogHeader>

        <div className="flex flex-1 overflow-hidden min-h-0">
          {/* ── Left: browser viewport ────────────────────────────────── */}
          <div className="flex flex-col flex-1 min-w-0 border-r overflow-hidden">
            {/* URL bar */}
            <div className="flex items-center gap-2 px-2 py-1.5 border-b bg-muted/20 shrink-0">
              <Globe className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              <Input
                value={urlBar}
                onChange={(e) => setUrlBar(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleNavigate()}
                placeholder="https://..."
                className="h-7 text-xs font-mono border-0 bg-transparent shadow-none focus-visible:ring-0 px-0"
              />
              <Button size="sm" variant="outline" className="h-7 px-3 text-xs shrink-0" onClick={handleNavigate}>
                <Navigation className="h-3 w-3 mr-1" />Ir
              </Button>
            </div>

            {/* Screenshot area */}
            <div className="flex-1 relative bg-zinc-950 flex items-center justify-center overflow-hidden min-h-0">
              {/* Loading overlay */}
              {busy && (
                <div className="absolute inset-0 bg-black/50 flex items-center justify-center z-10 pointer-events-none">
                  <Loader2 className="h-8 w-8 animate-spin text-white/70" />
                </div>
              )}

              {/* Connecting state */}
              {!hasScreenshot && !busy && (
                <div className="flex flex-col items-center gap-3 text-white/40">
                  <MousePointer className="h-10 w-10" />
                  <p className="text-sm">Aguardando conexão com o navegador...</p>
                </div>
              )}

              {/* The live screenshot preview — interaction happens in the external window */}
              <img
                ref={imgRef}
                className={`max-w-full max-h-full object-contain select-none ${
                  hasScreenshot ? "" : "hidden"
                } ${connected && !busy && !agentMode ? "cursor-pointer" : "cursor-default"}`}
                draggable={false}
                alt="browser"
                onClick={handleScreenshotClick}
              />

              {/* Type dialog overlay */}
              {typeDialog && (
                <div className="absolute inset-0 bg-black/65 flex items-center justify-center z-20">
                  <div className="bg-card border rounded-xl p-5 w-80 shadow-2xl space-y-4">
                    <p className="text-sm font-medium">
                      {typeDialog.is_password ? "Digite a senha:" : "O que digitar nesse campo?"}
                    </p>
                    <div className="relative">
                      <Input
                        autoFocus
                        type={typeDialog.is_password && !showPwd ? "password" : "text"}
                        value={typeValue}
                        onChange={(e) => setTypeValue(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && handleTypeSubmit()}
                        placeholder={typeDialog.is_password ? "••••••••" : "Texto..."}
                      />
                      {typeDialog.is_password && (
                        <Button
                          variant="ghost" size="icon"
                          className="absolute right-1 top-1/2 -translate-y-1/2 h-6 w-6"
                          type="button"
                          onClick={() => setShowPwd(!showPwd)}
                        >
                          {showPwd ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
                        </Button>
                      )}
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" className="flex-1 gap-1.5" onClick={handleTypeSubmit}>
                        <Check className="h-3.5 w-3.5" /> Confirmar
                      </Button>
                      <Button size="sm" variant="outline" className="gap-1.5" onClick={() => { setTypeDialog(null); setBusy(false); }}>
                        <X className="h-3.5 w-3.5" /> Cancelar
                      </Button>
                    </div>
                  </div>
                </div>
              )}

              {/* Select option dialog overlay */}
              {selectDialog && (
                <div className="absolute inset-0 bg-black/65 flex items-center justify-center z-20">
                  <div className="bg-card border rounded-xl p-5 w-80 shadow-2xl space-y-3 max-h-[70%] flex flex-col">
                    <p className="text-sm font-medium shrink-0">Selecione uma opção:</p>
                    <div className="overflow-y-auto flex-1 space-y-1">
                      {selectDialog.options.length === 0 ? (
                        <p className="text-xs text-muted-foreground text-center py-4">Nenhuma opção encontrada</p>
                      ) : (
                        selectDialog.options.map((opt) => (
                          <button
                            key={opt.value}
                            className="w-full text-left text-sm px-3 py-2 rounded-md hover:bg-accent hover:text-accent-foreground transition-colors"
                            onClick={() => handleSelectOption(opt)}
                          >
                            {opt.label || opt.value}
                          </button>
                        ))
                      )}
                    </div>
                    <Button size="sm" variant="outline" className="gap-1.5 shrink-0" onClick={() => { setSelectDialog(null); setBusy(false); }}>
                      <X className="h-3.5 w-3.5" /> Cancelar
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* ── Right panel: steps (manual) OR agent (AI) ────────────── */}
          <div className="w-72 flex flex-col shrink-0 min-h-0">

            {agentMode ? (
              /* ── Agente IA panel ──────────────────────────────────── */
              <>
                <div className="px-3 py-2 border-b shrink-0">
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide flex items-center gap-1.5">
                    <Bot className="h-3.5 w-3.5" /> Agente IA
                  </p>
                </div>

                <div className="p-3 border-b shrink-0 space-y-2">
                  <div className="relative">
                    <Textarea
                      placeholder="Ex: Acesse https://site.com, faça login com usuário admin e senha 1234, vá em Relatórios, baixe o Excel de inadimplência."
                      value={agentInstruction}
                      onChange={(e) => setAgentInstruction(e.target.value)}
                      className="text-xs min-h-[90px] pr-9 resize-none"
                      disabled={agentRunning}
                    />
                    <Button
                      type="button" size="icon" variant={isRecording ? "destructive" : "ghost"}
                      className="absolute right-1 top-1 h-7 w-7"
                      onClick={handleAgentMic}
                      disabled={agentRunning || isTranscribing}
                      title={isRecording ? "Parar gravação" : "Gravar por voz"}
                    >
                      {isTranscribing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : isRecording ? <MicOff className="h-3.5 w-3.5" /> : <Mic className="h-3.5 w-3.5" />}
                    </Button>
                  </div>
                  {isRecording && (
                    <p className="text-[10px] text-red-400 flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" /> Gravando...
                    </p>
                  )}
                  <Button
                    size="sm" className="w-full gap-1.5"
                    onClick={handleAgentRun}
                    disabled={!agentInstruction.trim() || agentRunning || !connected}
                  >
                    {agentRunning
                      ? <><Loader2 className="h-3.5 w-3.5 animate-spin" />Executando...</>
                      : <><Play className="h-3.5 w-3.5" />Executar Agente</>}
                  </Button>
                </div>

                <ScrollArea className="flex-1 min-h-0">
                  <div className="p-2 space-y-1">
                    {agentLog.length === 0 ? (
                      <div className="py-8 text-center text-xs text-muted-foreground space-y-2">
                        <Bot className="h-6 w-6 mx-auto opacity-30" />
                        <p>Descreva a tarefa e clique<br />em Executar Agente</p>
                      </div>
                    ) : (
                      agentLog.map((entry, i) => (
                        <div key={i} className="flex items-start gap-1.5 text-xs py-1">
                          {entry.ok
                            ? <CheckCircle2 className="h-3.5 w-3.5 text-green-400 shrink-0 mt-0.5" />
                            : <XCircle className="h-3.5 w-3.5 text-red-400 shrink-0 mt-0.5" />}
                          <span className="text-muted-foreground leading-tight">{entry.text}</span>
                        </div>
                      ))
                    )}
                    <div ref={agentLogEndRef} />
                  </div>
                </ScrollArea>

                <div className="p-3 border-t shrink-0 space-y-2">
                  <p className="text-[10px] text-muted-foreground text-center">
                    {steps.length > 0 ? `${steps.length} passos gravados` : "O agente grava os passos automaticamente"}
                  </p>
                  <Button className="w-full gap-2" variant={steps.length > 0 ? "destructive" : "outline"} onClick={handleStop}>
                    <Square className="h-3.5 w-3.5" />
                    {steps.length > 0 ? `Salvar ${steps.length} passos` : "Fechar"}
                  </Button>
                </div>
              </>
            ) : (
              /* ── Manual recording panel ───────────────────────────── */
              <>
                <div className="px-3 py-2 border-b shrink-0">
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                    Passos gravados ({steps.length})
                  </p>
                </div>

                <ScrollArea className="flex-1 min-h-0">
                <div className="p-2 space-y-1">
                  <div className="rounded-md border bg-muted/30 px-2.5 py-2 text-[11px] text-muted-foreground">
                    Clique na tela à esquerda para interagir com o navegador remoto.
                  </div>
                  {steps.length === 0 ? (
                    <div className="py-10 text-center text-xs text-muted-foreground space-y-2">
                      <MousePointer className="h-6 w-6 mx-auto opacity-30" />
                        <p>Interaja na janela externa<br />para gravar ações</p>
                    </div>
                  ) : (
                      steps.map((step, i) => (
                        <div key={i} className="flex items-start gap-1.5 rounded-md border px-2 py-1.5 text-xs group hover:bg-muted/30 transition-colors">
                          <span className="text-muted-foreground font-mono w-4 shrink-0 pt-0.5 text-[10px]">{i + 1}</span>
                          <div className="flex-1 min-w-0 space-y-0.5">
                            <span className={`inline-block px-1.5 py-0.5 rounded border text-[10px] font-semibold ${ACTION_COLOR[step.action] ?? "bg-muted text-muted-foreground border-border"}`}>
                              {ACTION_LABEL[step.action] ?? step.action}
                            </span>
                            <p className="text-muted-foreground font-mono truncate text-[10px] leading-tight">
                              {step.value || step.selector || "—"}
                            </p>
                          </div>
                          <Button
                            variant="ghost" size="icon"
                            className="h-5 w-5 shrink-0 opacity-0 group-hover:opacity-100 text-destructive hover:text-destructive hover:bg-destructive/10 transition-opacity"
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

                <div className="p-3 border-t shrink-0 space-y-2">
                  <p className="text-[10px] text-muted-foreground text-center">
                    Quando terminar, clique em Salvar
                  </p>
                  <Button className="w-full gap-2" variant={steps.length > 0 ? "destructive" : "outline"} onClick={handleStop}>
                    <Square className="h-3.5 w-3.5" />
                    {steps.length > 0 ? `Salvar ${steps.length} passos` : "Fechar"}
                  </Button>
                </div>
              </>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
