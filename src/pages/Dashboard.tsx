import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Automation, AutomationStep } from "@/types/automation";
import { AutomationList } from "@/components/automation/AutomationList";
import { LivePreviewModal } from "@/components/automation/LivePreviewModal";
import { RecordingModal } from "@/components/automation/RecordingModal";
import { 
  fetchAutomations, 
  deleteAutomation, 
  toggleAutomationStatus 
} from "@/services/automationService";
import { executeAutomation } from "@/services/executionService";
import { toast } from "sonner";
import { Header } from "@/components/layout/Header";
import { Button } from "@/components/ui/button";
import { Plus, Video } from "lucide-react";
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

interface LivePreviewState {
  isOpen: boolean;
  liveUrl: string | null;
  automationName: string;
  executionId: string | null;
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [automations, setAutomations] = useState<Automation[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [isRecordingModalOpen, setIsRecordingModalOpen] = useState(false);
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
      const data = await fetchAutomations();
      setAutomations(data);
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

  const handleExecute = async (id: string, withLivePreview: boolean = false) => {
    const automation = automations.find(a => a.id === id);
    
    if (withLivePreview) {
      // Open modal immediately with loading state
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
        if (withLivePreview) {
          setLivePreview(prev => ({ ...prev, isOpen: false }));
        }
        return;
      }

      if (withLivePreview && result.liveUrl) {
        setLivePreview(prev => ({
          ...prev,
          liveUrl: result.liveUrl || null,
          executionId: result.executionId || null,
        }));
      } else if (!withLivePreview) {
        toast.success("Execução iniciada com sucesso!");
      }

      // Reload automations to update status
      loadAutomations();
    } catch (error) {
      console.error("Error executing automation:", error);
      toast.error("Erro ao executar automação");
      if (withLivePreview) {
        setLivePreview(prev => ({ ...prev, isOpen: false }));
      }
    }
  };

  const handleCloseLivePreview = () => {
    setLivePreview({
      isOpen: false,
      liveUrl: null,
      automationName: '',
      executionId: null,
    });
    // Reload to get updated execution status
    loadAutomations();
  };

  const handleStepsGenerated = (steps: AutomationStep[], erpUrl: string, notes?: string) => {
    // Navigate to the automation editor with pre-populated steps
    navigate('/automation/new', {
      state: {
        prePopulatedSteps: steps,
        prePopulatedErpUrl: erpUrl,
        prePopulatedNotes: notes,
        fromRecording: true,
      },
    });
  };

  return (
    <div className="min-h-screen bg-background">
      <Header />

      {/* Main content */}
      <main className="container py-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold">Dashboard</h1>
            <p className="text-muted-foreground mt-1">
              Gerencie suas automações de extração de dados
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => setIsRecordingModalOpen(true)}
              className="gap-2"
            >
              <Video className="h-4 w-4" />
              Gravar Automação
            </Button>
            <Button
              onClick={() => navigate('/automation/new')}
              className="gap-2"
            >
              <Plus className="h-4 w-4" />
              Nova Automação
            </Button>
          </div>
        </div>

        <AutomationList
          automations={automations}
          isLoading={isLoading}
          onDelete={(id) => setDeleteId(id)}
          onToggleStatus={handleToggleStatus}
          onExecute={handleExecute}
        />
      </main>

      {/* Delete confirmation dialog */}
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

      {/* Live Preview Modal */}
      <LivePreviewModal
        isOpen={livePreview.isOpen}
        onClose={handleCloseLivePreview}
        liveUrl={livePreview.liveUrl}
        automationName={livePreview.automationName}
        executionId={livePreview.executionId}
      />

      {/* Recording Modal */}
      <RecordingModal
        isOpen={isRecordingModalOpen}
        onClose={() => setIsRecordingModalOpen(false)}
        onStepsGenerated={handleStepsGenerated}
      />
    </div>
  );
}
