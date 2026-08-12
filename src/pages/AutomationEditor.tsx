import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { StepsList } from "@/components/StepsList";
import { AutomationStep, Automation, AutomationOutput, Schedule, ScheduleType } from "@/types/automation";
import {
  fetchAutomationById,
  createAutomation,
  updateAutomation,
  generateSteps,
  parseSeleniumCsv,
  importChromeRecording,
  runAiAgent,
  fetchSchedulesByAutomation,
  createSchedule,
  deleteSchedule,
  toggleSchedule,
} from "@/services/automationService";
import { toast } from "sonner";
import {
  Loader2, Sparkles, Save, Bot, ArrowLeft, Settings,
  Webhook, Globe, Plus, Trash2, Clock, MessageCircle,
  FileSpreadsheet, ChevronDown, ChevronUp, Upload, MonitorPlay,
  Mic, MicOff, Zap,
} from "lucide-react";
import { Header } from "@/components/layout/Header";
import { ExtensionRecorder } from "@/components/automation/ExtensionRecorder";
import { cn } from "@/lib/utils";

interface LocationState {
  prePopulatedSteps?: AutomationStep[];
  prePopulatedErpUrl?: string;
  prePopulatedNotes?: string;
  fromRecording?: boolean;
}

// ── Output editor component ────────────────────────────────────────────────

function OutputEditor({
  output,
  index,
  onChange,
  onRemove,
}: {
  output: AutomationOutput;
  index: number;
  onChange: (o: AutomationOutput) => void;
  onRemove: () => void;
}) {
  const [expanded, setExpanded] = useState(true);

  const icons: Record<string, React.ReactNode> = {
    webhook: <Webhook className="h-4 w-4 text-blue-400" />,
    whatsapp: <MessageCircle className="h-4 w-4 text-green-400" />,
    sheets: <FileSpreadsheet className="h-4 w-4 text-emerald-400" />,
  };

  const labels: Record<string, string> = {
    webhook: "Webhook",
    whatsapp: "WhatsApp",
    sheets: "Google Sheets",
  };

  return (
    <Card className="border border-border">
      <div className="flex items-center justify-between px-4 py-2 cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <div className="flex items-center gap-2">
          {icons[output.type]}
          <span className="text-sm font-medium">{labels[output.type]} #{index + 1}</span>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive" onClick={(e) => { e.stopPropagation(); onRemove(); }}>
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
          {expanded ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
        </div>
      </div>

      {expanded && (
        <CardContent className="pt-0 pb-4 space-y-3">
          {output.type === "webhook" && (
            <>
              <div className="space-y-1">
                <Label className="text-xs">URL do Webhook</Label>
                <Input
                  placeholder="https://n8n.suavps.com/webhook/..."
                  value={output.url}
                  onChange={(e) => onChange({ ...output, url: e.target.value })}
                />
              </div>
              <p className="text-xs text-muted-foreground">
                Envia POST JSON com os dados extraídos. Compatível com n8n, Make, Zapier, etc.
              </p>
            </>
          )}

          {output.type === "whatsapp" && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="text-xs">URL da Evolution API</Label>
                  <Input
                    placeholder="https://evolution.suavps.com"
                    value={output.api_url}
                    onChange={(e) => onChange({ ...output, api_url: e.target.value })}
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">API Key</Label>
                  <Input
                    type="password"
                    placeholder="••••••••"
                    value={output.api_key}
                    onChange={(e) => onChange({ ...output, api_key: e.target.value })}
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Instância</Label>
                  <Input
                    placeholder="minha-instancia"
                    value={output.instance}
                    onChange={(e) => onChange({ ...output, instance: e.target.value })}
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Número (com DDD)</Label>
                  <Input
                    placeholder="5511999999999"
                    value={output.to}
                    onChange={(e) => onChange({ ...output, to: e.target.value })}
                  />
                </div>
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Mensagem (opcional)</Label>
                <Input
                  placeholder="Relatório '{name}' disponível!"
                  value={output.message || ""}
                  onChange={(e) => onChange({ ...output, message: e.target.value })}
                />
                <p className="text-xs text-muted-foreground">Use {"{name}"} para incluir o nome da automação.</p>
              </div>
            </>
          )}

          {output.type === "sheets" && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1 col-span-2">
                  <Label className="text-xs">ID da Planilha</Label>
                  <Input
                    placeholder="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms"
                    value={output.spreadsheet_id}
                    onChange={(e) => onChange({ ...output, spreadsheet_id: e.target.value })}
                  />
                  <p className="text-xs text-muted-foreground">
                    O ID fica na URL: docs.google.com/spreadsheets/d/<strong>ID</strong>/edit
                  </p>
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Aba (Sheet)</Label>
                  <Input
                    placeholder="Sheet1"
                    value={output.sheet || ""}
                    onChange={(e) => onChange({ ...output, sheet: e.target.value })}
                  />
                </div>
              </div>
              <p className="text-xs text-muted-foreground">
                Configure a Service Account do Google em Configurações → Google Service Account.
              </p>
            </>
          )}
        </CardContent>
      )}
    </Card>
  );
}

// ── Schedule editor component ──────────────────────────────────────────────

function ScheduleRow({
  schedule,
  onToggle,
  onDelete,
}: {
  schedule: Schedule;
  onToggle: () => void;
  onDelete: () => void;
}) {
  const typeLabel: Record<string, string> = {
    once: "Uma vez",
    daily: "Diário",
    weekly: "Semanal",
    monthly: "Mensal",
    interval: "Intervalo",
    cron: "Cron",
  };

  const DAY_NAMES = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'];
  const summary = () => {
    if (schedule.schedule_type === "cron") return schedule.cron_expression;
    if (schedule.schedule_type === "interval") return `A cada ${schedule.interval_minutes} min`;
    if (schedule.schedule_type === "once" && schedule.next_run_at)
      return new Date(schedule.next_run_at).toLocaleString("pt-BR");
    if (schedule.schedule_type === "weekly") {
      const days = (schedule.days_of_week || []).map(d => DAY_NAMES[d]).join(', ');
      return `${days || 'Semanal'}${schedule.time_of_day ? ` às ${schedule.time_of_day}` : ''}`;
    }
    if (schedule.time_of_day) return `às ${schedule.time_of_day}`;
    return "";
  };

  return (
    <div className="flex items-center justify-between rounded-lg border px-3 py-2">
      <div className="flex items-center gap-3">
        <Clock className="h-4 w-4 text-muted-foreground" />
        <div>
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">{typeLabel[schedule.schedule_type]}</span>
            <Badge variant={schedule.is_active ? "default" : "outline"} className="text-xs">
              {schedule.is_active ? "Ativo" : "Inativo"}
            </Badge>
          </div>
          {summary() && <p className="text-xs text-muted-foreground">{summary()}</p>}
        </div>
      </div>
      <div className="flex items-center gap-1">
        <Button variant="outline" size="sm" onClick={onToggle}>
          {schedule.is_active ? "Pausar" : "Ativar"}
        </Button>
        <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive" onClick={onDelete}>
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────

export default function AutomationEditor() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const locationState = location.state as LocationState | null;
  const isNew = !id || id === "new";

  const [isLoading, setIsLoading] = useState(!isNew);
  const [isSaving, setIsSaving] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [isChromeImporting, setIsChromeImporting] = useState(false);
  const [chromeJsonText, setChromeJsonText] = useState("");
  const [recorderOpen, setRecorderOpen] = useState(false);
  const [agentModalOpen, setAgentModalOpen] = useState(false);
  const [agentPrompt, setAgentPrompt] = useState("");
  const [isAgentRunning, setIsAgentRunning] = useState(false);

  // Audio recording
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  const handleMicToggle = useCallback(async () => {
    if (isRecording) {
      mediaRecorderRef.current?.stop();
      return;
    }
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
          if (text) setInstructions((prev) => prev ? prev + " " + text : text);
        } catch (err) {
          toast.error("Erro ao transcrever áudio");
        } finally {
          setIsTranscribing(false);
        }
      };
      mediaRecorderRef.current = mr;
      mr.start();
      setIsRecording(true);
    } catch {
      toast.error("Microfone não disponível ou permissão negada");
    }
  }, [isRecording]);

  // Basic fields
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [erpUrl, setErpUrl] = useState("");
  const [instructions, setInstructions] = useState("");
  const [steps, setSteps] = useState<AutomationStep[]>([]);
  const [notes, setNotes] = useState("");

  // Credentials
  const [requiresLogin, setRequiresLogin] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  // Outputs
  const [outputs, setOutputs] = useState<AutomationOutput[]>([]);

  // Schedules (for existing automations)
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [newScheduleType, setNewScheduleType] = useState<ScheduleType>("daily");
  const [newScheduleTime, setNewScheduleTime] = useState("08:00");
  const [newScheduleInterval, setNewScheduleInterval] = useState("60");
  const [newScheduleCron, setNewScheduleCron] = useState("0 8 * * 1-5");
  const [newScheduleDays, setNewScheduleDays] = useState<number[]>([0, 1, 2, 3, 4]); // Mon–Fri
  const [isAddingSchedule, setIsAddingSchedule] = useState(false);

  // Pre-populate from recording
  useEffect(() => {
    if (isNew && locationState?.fromRecording) {
      if (locationState.prePopulatedSteps) setSteps(locationState.prePopulatedSteps);
      if (locationState.prePopulatedErpUrl) setErpUrl(locationState.prePopulatedErpUrl);
      if (locationState.prePopulatedNotes) {
        setNotes(locationState.prePopulatedNotes);
        setInstructions(`Automação gravada: ${locationState.prePopulatedNotes}`);
      }
      window.history.replaceState({}, document.title);
    }
  }, [isNew, locationState]);

  useEffect(() => {
    if (!isNew && id) {
      loadAutomation(id);
      loadSchedules(id);
    }
  }, [id, isNew]);

  const loadAutomation = async (automationId: string) => {
    try {
      const data = await fetchAutomationById(automationId);
      if (!data) { toast.error("Automação não encontrada"); navigate("/"); return; }
      setName(data.name);
      setDescription(data.description || "");
      setErpUrl(data.erp_url || "");
      setInstructions(data.instructions || "");
      setSteps(data.steps || []);
      setOutputs(data.outputs || []);
      if (data.credentials?.username || data.credentials?.password) {
        setRequiresLogin(true);
        setUsername(data.credentials.username || "");
        setPassword(data.credentials.password || "");
      }
    } catch {
      toast.error("Erro ao carregar automação");
      navigate("/");
    } finally {
      setIsLoading(false);
    }
  };

  const loadSchedules = async (automationId: string) => {
    try {
      const data = await fetchSchedulesByAutomation(automationId);
      setSchedules(data);
    } catch {
      // silently fail — schedules are non-critical
    }
  };

  const handleImportSelenium = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsImporting(true);
    try {
      const text = await file.text();
      const result = await parseSeleniumCsv(text);
      if (result.steps.length === 0) {
        toast.error("Nenhum passo encontrado no arquivo. Verifique se é um CSV exportado pelo Selenium IDE.");
        return;
      }
      setSteps(result.steps);
      toast.success(`${result.count} passos importados do Selenium IDE!`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erro ao importar CSV");
    } finally {
      setIsImporting(false);
      e.target.value = "";
    }
  };

  const handleImportChrome = async () => {
    const text = chromeJsonText.trim();
    if (!text) { toast.error("Cole o JSON do Chrome DevTools Recorder"); return; }
    let parsed: object;
    try { parsed = JSON.parse(text); } catch {
      toast.error("JSON inválido. Copie exatamente o conteúdo exportado pelo Chrome."); return;
    }
    setIsChromeImporting(true);
    try {
      const result = await importChromeRecording(parsed);
      setSteps(result.steps);
      setChromeJsonText("");
      toast.success(`${result.count} passos importados do Chrome DevTools Recorder!`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erro ao importar gravação do Chrome");
    } finally {
      setIsChromeImporting(false);
    }
  };

  const handleRunAgent = async () => {
    if (!agentPrompt.trim()) { toast.error("Descreva o que o agente deve fazer"); return; }
    if (isNew) { toast.error("Salve a automação antes de executar"); return; }
    setIsAgentRunning(true);
    try {
      // Salva o prompt em instructions e limpa os steps para que agendamentos também usem o agente
      const creds = requiresLogin && (username || password) ? { username, password } : {};
      await updateAutomation(id!, { name, description, erp_url: erpUrl, instructions: agentPrompt, steps: [], credentials: creds, outputs });
      setInstructions(agentPrompt);
      setSteps([]);
      const result = await runAiAgent(id!, agentPrompt);
      setAgentModalOpen(false);
      toast.success("Agente iniciado! Acompanhe o progresso no histórico.", { duration: 5000 });
      navigate(`/automations/${id}/executions/${result.execution_id}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erro ao iniciar agente");
    } finally {
      setIsAgentRunning(false);
    }
  };

  const handleGenerateSteps = async () => {
    if (!instructions.trim()) {
      toast.error("Descreva o que você quer automatizar");
      return;
    }
    setIsGenerating(true);
    try {
      const result = await generateSteps(instructions, erpUrl);
      setSteps(result.steps);
      if (result.notes) setNotes(result.notes);
      toast.success("Passos gerados com sucesso!");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erro ao gerar passos");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSave = async () => {
    if (!name.trim()) { toast.error("Dê um nome para a automação"); return; }
    if (steps.length === 0 && !instructions.trim()) { toast.error("Adicione ao menos um passo ou escreva uma instrução para o agente"); return; }

    setIsSaving(true);
    try {
      const payload = {
        name,
        description: description || "",
        erp_url: erpUrl,
        instructions,
        steps,
        is_active: true,
        credentials: requiresLogin && (username || password)
          ? { username, password }
          : {},
        outputs,
      };

      if (isNew) {
        await createAutomation(payload as Omit<Automation, "id" | "created_at" | "updated_at">);
        toast.success("Automação criada!");
      } else if (id) {
        await updateAutomation(id, payload);
        toast.success("Automação atualizada!");
      }
      navigate("/");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erro ao salvar");
    } finally {
      setIsSaving(false);
    }
  };

  const addOutput = (type: AutomationOutput["type"]) => {
    const defaults: Record<string, AutomationOutput> = {
      webhook:  { type: "webhook",  url: "" },
      whatsapp: { type: "whatsapp", api_url: "", api_key: "", instance: "", to: "" },
      sheets:   { type: "sheets",   spreadsheet_id: "", sheet: "Sheet1" },
    };
    setOutputs([...outputs, defaults[type]]);
  };

  const updateOutput = (index: number, updated: AutomationOutput) => {
    setOutputs(outputs.map((o, i) => (i === index ? updated : o)));
  };

  const removeOutput = (index: number) => {
    setOutputs(outputs.filter((_, i) => i !== index));
  };

  const handleAddSchedule = async () => {
    if (!id) return;
    setIsAddingSchedule(true);
    try {
      const base = {
        automation_id: id,
        schedule_type: newScheduleType,
        timezone: "America/Sao_Paulo",
        is_active: true,
      };
      let scheduleData: Omit<Schedule, "id" | "created_at"> = base;

      if (newScheduleType === "cron") {
        scheduleData = { ...base, cron_expression: newScheduleCron };
      } else if (newScheduleType === "interval") {
        scheduleData = { ...base, interval_minutes: parseInt(newScheduleInterval) };
      } else if (newScheduleType === "weekly") {
        scheduleData = { ...base, time_of_day: newScheduleTime, days_of_week: newScheduleDays };
      } else {
        scheduleData = { ...base, time_of_day: newScheduleTime };
      }

      const created = await createSchedule(scheduleData);
      setSchedules([...schedules, created]);
      toast.success("Agendamento criado!");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erro ao criar agendamento");
    } finally {
      setIsAddingSchedule(false);
    }
  };

  const handleToggleSchedule = async (scheduleId: string) => {
    try {
      const { is_active } = await toggleSchedule(scheduleId);
      setSchedules(schedules.map((s) => s.id === scheduleId ? { ...s, is_active } : s));
    } catch {
      toast.error("Erro ao alterar agendamento");
    }
  };

  const handleDeleteSchedule = async (scheduleId: string) => {
    try {
      await deleteSchedule(scheduleId);
      setSchedules(schedules.filter((s) => s.id !== scheduleId));
    } catch {
      toast.error("Erro ao remover agendamento");
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background">
        <Header />
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <Header />

      <div className="border-b bg-card/50">
        <div className="container py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="icon" onClick={() => navigate("/")}>
                <ArrowLeft className="h-5 w-5" />
              </Button>
              <div>
                <h1 className="text-xl font-bold">{isNew ? "Nova Automação" : "Editar Automação"}</h1>
                <p className="text-sm text-muted-foreground">Configure os detalhes da automação</p>
              </div>
            </div>
            <div className="flex gap-2">
              {!isNew && (
                <Button variant="outline" onClick={() => { setAgentPrompt(instructions || agentPrompt); setAgentModalOpen(true); }} className="gap-2 border-purple-500 text-purple-400 hover:bg-purple-500/10">
                  <Zap className="h-4 w-4" /> Executar com IA
                </Button>
              )}
              <Button onClick={handleSave} disabled={isSaving || !name.trim()} className="gap-2">
                {isSaving ? <><Loader2 className="h-4 w-4 animate-spin" /> Salvando...</> : <><Save className="h-4 w-4" /> Salvar</>}
              </Button>
            </div>
          </div>
        </div>
      </div>

      <main className="container py-6">
        <Tabs defaultValue="config" className="space-y-6">
          <TabsList className="grid w-full grid-cols-4 max-w-2xl">
            <TabsTrigger value="config" className="gap-1.5"><Settings className="h-4 w-4" /><span className="hidden sm:inline">Config</span></TabsTrigger>
            <TabsTrigger value="steps"  className="gap-1.5"><Bot className="h-4 w-4" /><span className="hidden sm:inline">Passos</span></TabsTrigger>
            <TabsTrigger value="outputs" className="gap-1.5"><Webhook className="h-4 w-4" /><span className="hidden sm:inline">Entregas</span></TabsTrigger>
            <TabsTrigger value="schedule" className="gap-1.5" disabled={isNew}><Clock className="h-4 w-4" /><span className="hidden sm:inline">Agenda</span></TabsTrigger>
          </TabsList>

          {/* ── Config ── */}
          <TabsContent value="config" className="space-y-6">
            <Card className="border-l-4 border-l-primary">
              <CardHeader>
                <CardTitle className="flex items-center gap-2"><Settings className="h-5 w-5 text-primary" />Informações Básicas</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="name">Nome *</Label>
                    <Input id="name" placeholder="Ex: Exportar Vendas Mensais" value={name} onChange={(e) => setName(e.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="description">Descrição</Label>
                    <Input id="description" placeholder="O que faz essa automação" value={description} onChange={(e) => setDescription(e.target.value)} />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="border-l-4 border-l-accent">
              <CardHeader>
                <CardTitle className="flex items-center gap-2"><Globe className="h-5 w-5 text-accent" />URL do Sistema</CardTitle>
                <CardDescription>URL do sistema/ERP e credenciais de acesso</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="erpUrl">URL do sistema</Label>
                  <Input id="erpUrl" placeholder="https://seu-sistema.com.br" value={erpUrl} onChange={(e) => setErpUrl(e.target.value)} />
                </div>

                <div className="flex items-center space-x-2">
                  <Checkbox id="requiresLogin" checked={requiresLogin} onCheckedChange={(v) => setRequiresLogin(v === true)} />
                  <Label htmlFor="requiresLogin" className="cursor-pointer">Este sistema requer login</Label>
                </div>

                {requiresLogin && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pl-6 border-l-2 border-muted">
                    <div className="space-y-2">
                      <Label htmlFor="username">Usuário</Label>
                      <Input id="username" placeholder="seu.usuario" value={username} onChange={(e) => setUsername(e.target.value)} />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="password">Senha</Label>
                      <Input id="password" type="password" placeholder="••••••••" value={password} onChange={(e) => setPassword(e.target.value)} />
                    </div>
                    <p className="col-span-full text-xs text-muted-foreground">
                      Use <code>{"{{username}}"}</code> e <code>{"{{password}}"}</code> nos passos de digitação.
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* ── Steps ── */}
          <TabsContent value="steps" className="space-y-6">
            {/* Browser Recorder */}
            <Card className="border-l-4 border-l-primary">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <MonitorPlay className="h-5 w-5 text-primary" />
                  Gravar no Navegador
                </CardTitle>
                <CardDescription>
                  Abre uma janela externa do navegador remoto. Você usa essa janela normalmente e os passos aparecem aqui em tempo real.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Button
                  className="w-full gap-2"
                  onClick={() => setRecorderOpen(true)}
                >
                  <MonitorPlay className="h-4 w-4" />
                  Abrir Janela Externa e Gravar
                </Button>
              </CardContent>
            </Card>

            <Card className="border-l-4 border-l-accent">
              <CardHeader>
                <CardTitle className="flex items-center gap-2"><Sparkles className="h-5 w-5 text-accent" />Gerar com IA</CardTitle>
                <CardDescription>Descreva (ou grave por áudio) o que fazer e a IA gera os passos automaticamente</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="relative">
                  <Textarea
                    placeholder="Ex: Logar com usuário e senha, ir em Relatórios, clicar em Vendas Mensal, selecionar o mês atual, exportar planilha Excel."
                    value={instructions}
                    onChange={(e) => setInstructions(e.target.value)}
                    className="min-h-[120px] pr-12"
                  />
                  <Button
                    type="button"
                    size="icon"
                    variant={isRecording ? "destructive" : "outline"}
                    className="absolute right-2 top-2 h-8 w-8"
                    onClick={handleMicToggle}
                    disabled={isTranscribing}
                    title={isRecording ? "Parar gravação" : "Gravar instrução por áudio"}
                  >
                    {isTranscribing ? <Loader2 className="h-4 w-4 animate-spin" /> : isRecording ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
                  </Button>
                </div>
                {isRecording && (
                  <p className="text-xs text-red-400 flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                    Gravando... clique no microfone para parar
                  </p>
                )}
                <Button
                  onClick={handleGenerateSteps}
                  disabled={isGenerating || !instructions.trim()}
                  className="w-full gap-2"
                >
                  {isGenerating ? <><Loader2 className="h-4 w-4 animate-spin" />Gerando...</> : <><Sparkles className="h-4 w-4" />Gerar Passos com IA</>}
                </Button>
                {notes && (
                  <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg text-sm">
                    <strong className="text-blue-400">Observações da IA:</strong>
                    <p className="mt-1 text-muted-foreground">{notes}</p>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card className="border-l-4 border-l-orange-500">
              <CardHeader>
                <CardTitle className="flex items-center gap-2"><Upload className="h-5 w-5 text-orange-500" />Importar do Selenium IDE</CardTitle>
                <CardDescription>
                  Grave no Selenium IDE → Exportar → CSV → importe aqui. Captura selects, datepickers e tudo mais.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <label className="cursor-pointer">
                  <input
                    type="file"
                    accept=".csv,.txt"
                    className="hidden"
                    onChange={handleImportSelenium}
                    disabled={isImporting}
                  />
                  <div className="flex items-center gap-3 border-2 border-dashed border-orange-500/40 rounded-lg p-4 hover:border-orange-500/70 hover:bg-orange-500/5 transition-colors">
                    {isImporting ? (
                      <Loader2 className="h-5 w-5 animate-spin text-orange-500" />
                    ) : (
                      <Upload className="h-5 w-5 text-orange-500" />
                    )}
                    <div>
                      <p className="text-sm font-medium">{isImporting ? "Importando..." : "Clique para selecionar o arquivo CSV"}</p>
                      <p className="text-xs text-muted-foreground">Exportado pelo Selenium IDE (File → Export → CSV)</p>
                    </div>
                  </div>
                </label>
              </CardContent>
            </Card>

            <Card className="border-l-4 border-l-blue-500">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Globe className="h-5 w-5 text-blue-500" />
                  Importar do Chrome DevTools Recorder
                </CardTitle>
                <CardDescription>
                  A forma mais confiável de gravar qualquer site, incluindo dropdowns customizados, ERPs e formulários complexos.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="rounded-lg bg-muted/50 border border-border p-3 text-xs text-muted-foreground space-y-1">
                  <p className="font-semibold text-foreground">Como usar:</p>
                  <p>1. No Chrome, abra o site que deseja gravar</p>
                  <p>2. Pressione <kbd className="bg-muted border border-border rounded px-1">F12</kbd> → aba <strong>Recorder</strong></p>
                  <p>3. Clique em <strong>+</strong> para criar uma gravação e execute os passos desejados</p>
                  <p>4. Ao terminar, clique no ícone de exportar (⬇) → escolha <strong>JSON</strong></p>
                  <p>5. Cole o conteúdo do arquivo abaixo e clique em Importar</p>
                </div>
                <textarea
                  className="w-full min-h-[100px] rounded-md border border-input bg-background px-3 py-2 text-sm font-mono resize-y focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder='Cole aqui o JSON exportado pelo Chrome DevTools Recorder...'
                  value={chromeJsonText}
                  onChange={(e) => setChromeJsonText(e.target.value)}
                  disabled={isChromeImporting}
                />
                <Button
                  className="w-full gap-2 bg-blue-600 hover:bg-blue-700"
                  onClick={handleImportChrome}
                  disabled={isChromeImporting || !chromeJsonText.trim()}
                >
                  {isChromeImporting
                    ? <><Loader2 className="h-4 w-4 animate-spin" />Importando...</>
                    : <><Globe className="h-4 w-4" />Importar Gravação do Chrome</>
                  }
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2"><Bot className="h-5 w-5 text-primary" />Passos ({steps.length})</CardTitle>
                <CardDescription>Revise e ajuste os passos</CardDescription>
              </CardHeader>
              <CardContent>
                <StepsList steps={steps} onStepsChange={setSteps} />
              </CardContent>
            </Card>
          </TabsContent>

          {/* ── Outputs ── */}
          <TabsContent value="outputs" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Onde enviar os resultados?</CardTitle>
                <CardDescription>
                  Configure uma ou mais saídas. Após cada execução os dados extraídos são entregues automaticamente.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" size="sm" className="gap-1.5" onClick={() => addOutput("webhook")}>
                    <Webhook className="h-4 w-4 text-blue-400" /> Webhook
                  </Button>
                  <Button variant="outline" size="sm" className="gap-1.5" onClick={() => addOutput("whatsapp")}>
                    <MessageCircle className="h-4 w-4 text-green-400" /> WhatsApp
                  </Button>
                  <Button variant="outline" size="sm" className="gap-1.5" onClick={() => addOutput("sheets")}>
                    <FileSpreadsheet className="h-4 w-4 text-emerald-400" /> Google Sheets
                  </Button>
                </div>

                {outputs.length === 0 && (
                  <p className="text-sm text-muted-foreground py-4 text-center">
                    Nenhuma saída configurada. Adicione pelo menos um destino acima.
                  </p>
                )}

                <div className="space-y-3">
                  {outputs.map((output, i) => (
                    <OutputEditor
                      key={i}
                      output={output}
                      index={i}
                      onChange={(o) => updateOutput(i, o)}
                      onRemove={() => removeOutput(i)}
                    />
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* ── Schedule ── */}
          <TabsContent value="schedule" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2"><Clock className="h-5 w-5 text-primary" />Agendamentos</CardTitle>
                <CardDescription>Programe execuções automáticas em horários fixos</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {schedules.length > 0 && (
                  <div className="space-y-2">
                    {schedules.map((s) => (
                      <ScheduleRow
                        key={s.id}
                        schedule={s}
                        onToggle={() => handleToggleSchedule(s.id)}
                        onDelete={() => handleDeleteSchedule(s.id)}
                      />
                    ))}
                  </div>
                )}

                <div className="border rounded-lg p-4 space-y-4 bg-muted/30">
                  <p className="text-sm font-medium">Novo agendamento</p>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <Label className="text-xs">Tipo</Label>
                      <Select value={newScheduleType} onValueChange={(v) => setNewScheduleType(v as ScheduleType)}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="daily">Diário</SelectItem>
                          <SelectItem value="weekly">Semanal</SelectItem>
                          <SelectItem value="monthly">Mensal</SelectItem>
                          <SelectItem value="interval">Intervalo (minutos)</SelectItem>
                          <SelectItem value="cron">Cron Expression</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    {newScheduleType === "cron" ? (
                      <div className="space-y-1">
                        <Label className="text-xs">Expressão Cron</Label>
                        <Input placeholder="0 8 * * 1-5" value={newScheduleCron} onChange={(e) => setNewScheduleCron(e.target.value)} />
                      </div>
                    ) : newScheduleType === "interval" ? (
                      <div className="space-y-1">
                        <Label className="text-xs">A cada (minutos)</Label>
                        <Input type="number" min="1" value={newScheduleInterval} onChange={(e) => setNewScheduleInterval(e.target.value)} />
                      </div>
                    ) : (
                      <div className="space-y-1">
                        <Label className="text-xs">Horário</Label>
                        <Input type="time" value={newScheduleTime} onChange={(e) => setNewScheduleTime(e.target.value)} />
                      </div>
                    )}
                  </div>

                  {newScheduleType === "weekly" && (
                    <div className="space-y-1">
                      <Label className="text-xs">Dias da semana</Label>
                      <div className="flex gap-1.5 flex-wrap">
                        {(['Seg','Ter','Qua','Qui','Sex','Sáb','Dom'] as const).map((label, idx) => {
                          const active = newScheduleDays.includes(idx);
                          return (
                            <button
                              key={idx}
                              type="button"
                              onClick={() => setNewScheduleDays(prev =>
                                active ? prev.filter(d => d !== idx) : [...prev, idx].sort()
                              )}
                              className={cn(
                                "px-2.5 py-1 rounded-md text-xs font-medium border transition-colors",
                                active
                                  ? "bg-primary text-primary-foreground border-primary"
                                  : "bg-background text-muted-foreground border-input hover:border-primary/50"
                              )}
                            >
                              {label}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  <Button onClick={handleAddSchedule} disabled={isAddingSchedule} size="sm" className="gap-2">
                    {isAddingSchedule ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
                    Adicionar agendamento
                  </Button>
                </div>

                <p className="text-xs text-muted-foreground">
                  Agendamentos são verificados a cada minuto pelo worker. Fuso horário: America/Sao_Paulo.
                </p>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>

      <ExtensionRecorder
        isOpen={recorderOpen}
        onClose={() => setRecorderOpen(false)}
        initialUrl={erpUrl}
        onStepsReady={(recorded) => {
          setSteps(recorded);
          setRecorderOpen(false);
          toast.success(`${recorded.length} passos gravados!`);
        }}
      />

      {/* ── Agente IA Modal ── */}
      <Dialog open={agentModalOpen} onOpenChange={setAgentModalOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Zap className="h-5 w-5 text-purple-400" />
              Executar com Agente IA
            </DialogTitle>
            <DialogDescription>
              Descreva o que o agente deve fazer. Ele vai ver a tela, tomar decisões e executar sozinho.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 pt-2">
            {erpUrl && (
              <div className="text-xs text-muted-foreground bg-muted/50 rounded px-3 py-2">
                O agente vai acessar: <strong>{erpUrl}</strong>
              </div>
            )}
            <Textarea
              placeholder={`Ex: Entra no sistema, vai em Relatórios → Inadimplência, seleciona o mês atual, exporta em Excel e confirma o download.`}
              value={agentPrompt}
              onChange={(e) => setAgentPrompt(e.target.value)}
              className="min-h-[140px]"
              disabled={isAgentRunning}
              onKeyDown={(e) => { if (e.key === "Enter" && e.ctrlKey) handleRunAgent(); }}
            />
            <p className="text-xs text-muted-foreground">Dica: quanto mais detalhado o comando, melhor o resultado.</p>
            <div className="flex gap-2">
              <Button variant="outline" className="flex-1" onClick={() => setAgentModalOpen(false)} disabled={isAgentRunning}>
                Cancelar
              </Button>
              <Button
                className="flex-1 gap-2 bg-purple-600 hover:bg-purple-700"
                onClick={handleRunAgent}
                disabled={isAgentRunning || !agentPrompt.trim()}
              >
                {isAgentRunning
                  ? <><Loader2 className="h-4 w-4 animate-spin" /> Iniciando...</>
                  : <><Zap className="h-4 w-4" /> Executar Agora</>
                }
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
