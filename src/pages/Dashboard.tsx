import { useEffect, useState } from "react";
import { Automation, Schedule } from "@/types/automation";
import { AutomationList } from "@/components/automation/AutomationList";
import { LivePreviewModal } from "@/components/automation/LivePreviewModal";
import {
  fetchAutomations,
  fetchAllSchedules,
  deleteAutomation,
  toggleAutomationStatus,
  cloneAutomation,
} from "@/services/automationService";
import { executeAutomation } from "@/services/executionService";
import { toast } from "sonner";
import { Header } from "@/components/layout/Header";
import { Link } from "react-router-dom";
import { CheckCircle2, XCircle, Loader2, RefreshCw, Key, Globe, Cpu, Bot } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

// ── Health Panel ──────────────────────────────────────────────────────────────

type HealthStatus = {
  api: boolean;
  browserless: boolean;
  openai_key: boolean;
  celery: boolean;
} | null;

function HealthPanel() {
  const [status, setStatus] = useState<HealthStatus>(null);
  const [loading, setLoading] = useState(true);

  const check = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/health/status");
      if (res.ok) setStatus(await res.json());
    } catch {
      setStatus(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    check();
    const interval = setInterval(check, 30000);
    return () => clearInterval(interval);
  }, []);

  const Item = ({ ok, label, hint }: { ok: boolean; label: string; hint?: string }) => (
    <div className="flex items-center gap-2 text-sm" title={hint}>
      {ok
        ? <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0" />
        : <XCircle className="h-4 w-4 text-destructive shrink-0" />}
      <span className={ok ? "text-foreground" : "text-destructive"}>{label}</span>
    </div>
  );

  if (loading) {
    return (
      <div className="mb-6 flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Verificando sistema...
      </div>
    );
  }

  if (!status) return null;

  const allOk = status.api && status.browserless && status.openai_key && status.celery;

  return (
    <div className={`mb-6 rounded-lg border px-4 py-3 ${allOk ? "border-green-500/20 bg-green-500/5" : "border-destructive/20 bg-destructive/5"}`}>
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-6 flex-wrap">
          <Item ok={status.api} label="API" hint="Backend FastAPI" />
          <Item ok={status.celery} label="Workers" hint="Celery task queue" />
          <Item ok={status.browserless} label="Browserless" hint="Chrome headless" />
          <Item
            ok={status.openai_key}
            label={status.openai_key ? "OpenAI configurada" : "OpenAI sem chave"}
            hint={status.openai_key ? "API Key configurada" : "Configure em Configurações"}
          />
        </div>
        <div className="flex items-center gap-3">
          {!allOk && (
            <Link to="/settings" className="text-xs text-primary underline underline-offset-2">
              Corrigir em Configurações
            </Link>
          )}
          <button onClick={check} className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
            <RefreshCw className="h-3 w-3" /> Atualizar
          </button>
        </div>
      </div>
    </div>
  );
}

interface LivePreviewState {
  isOpen: boolean;
  liveUrl: string | null;
  automationName: string;
  executionId: string | null;
}

export default function Dashboard() {
  const [automations, setAutomations] = useState<Automation[]>([]);
  const [schedulesMap, setSchedulesMap] = useState<Record<string, Schedule[]>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [livePreview, setLivePreview] = useState<LivePreviewState>({
    isOpen: false,
    liveUrl: null,
    automationName: '',
    executionId: null,
  });

  useEffect(() => {
    loadAutomations();
  }, []);

  const loadAutomations = async () => {
    try {
      const [data, allSchedules] = await Promise.all([
        fetchAutomations(),
        fetchAllSchedules().catch(() => [] as Schedule[]),
      ]);
      setAutomations(data);
      const map: Record<string, Schedule[]> = {};
      for (const s of allSchedules) {
        if (!map[s.automation_id]) map[s.automation_id] = [];
        map[s.automation_id].push(s);
      }
      setSchedulesMap(map);
    } catch (error) {
      console.error("Error loading automations:", error);
      toast.error("Erro ao carregar automações");
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    try {
      await deleteAutomation(deleteId);
      setAutomations((prev) => prev.filter((a) => a.id !== deleteId));
      toast.success("Automação excluída com sucesso");
    } catch (error) {
      console.error("Error deleting automation:", error);
      toast.error("Erro ao excluir automação");
    } finally {
      setDeleteId(null);
    }
  };

  const handleToggleStatus = async (id: string, isActive: boolean) => {
    try {
      await toggleAutomationStatus(id, isActive);
      setAutomations((prev) =>
        prev.map((a) => (a.id === id ? { ...a, is_active: isActive } : a))
      );
      toast.success(isActive ? "Automação ativada" : "Automação desativada");
    } catch (error) {
      console.error("Error toggling status:", error);
      toast.error("Erro ao alterar status");
    }
  };

  const handleClone = async (id: string) => {
    try {
      await cloneAutomation(id);
      toast.success("Automação clonada com sucesso!");
      loadAutomations();
    } catch {
      toast.error("Erro ao clonar automação");
    }
  };

  const handleExecute = async (id: string, withLivePreview: boolean = false) => {
    const automation = automations.find(a => a.id === id);

    if (withLivePreview) {
      setLivePreview({
        isOpen: true,
        liveUrl: null,
        automationName: automation?.name || 'Automação',
        executionId: null,
      });
    }

    toast.info(withLivePreview ? "Iniciando com Live Preview..." : "Executando automação...");

    try {
      const result = await executeAutomation(id, { withLivePreview });

      if (!result.success) {
        toast.error(result.error || "Erro ao executar automação");
        if (withLivePreview) setLivePreview(prev => ({ ...prev, isOpen: false }));
        return;
      }

      if (withLivePreview) {
        setLivePreview(prev => ({
          ...prev,
          liveUrl: result.liveUrl || null,
          executionId: result.executionId || null,
        }));
      } else {
        toast.success("Execução iniciada com sucesso!");
      }

      loadAutomations();
    } catch (error) {
      console.error("Error executing automation:", error);
      toast.error("Erro ao executar automação");
      if (withLivePreview) setLivePreview(prev => ({ ...prev, isOpen: false }));
    }
  };

  const handleCloseLivePreview = () => {
    setLivePreview({ isOpen: false, liveUrl: null, automationName: '', executionId: null });
    loadAutomations();
  };

  return (
    <div className="min-h-screen bg-background">
      <Header />

      <main className="container py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold">Dashboard</h1>
          <p className="text-muted-foreground mt-1">
            Gerencie suas automações de extração de dados
          </p>
        </div>

        <HealthPanel />

        <AutomationList
          automations={automations}
          schedulesMap={schedulesMap}
          isLoading={isLoading}
          onDelete={(id) => setDeleteId(id)}
          onClone={handleClone}
          onToggleStatus={handleToggleStatus}
          onExecute={handleExecute}
        />
      </main>

      <AlertDialog open={!!deleteId} onOpenChange={() => setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Excluir automação?</AlertDialogTitle>
            <AlertDialogDescription>
              Esta ação não pode ser desfeita. A automação e todos os seus
              agendamentos e logs serão removidos permanentemente.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Excluir
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <LivePreviewModal
        isOpen={livePreview.isOpen}
        onClose={handleCloseLivePreview}
        liveUrl={livePreview.liveUrl}
        automationName={livePreview.automationName}
        executionId={livePreview.executionId}
      />
    </div>
  );
}
