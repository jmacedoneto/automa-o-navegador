import { useEffect, useState } from "react";
import { Automation } from "@/types/automation";
import { AutomationList } from "@/components/automation/AutomationList";
import { 
  fetchAutomations, 
  deleteAutomation, 
  toggleAutomationStatus 
} from "@/services/automationService";
import { toast } from "sonner";
import { Bot } from "lucide-react";
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

export default function Dashboard() {
  const [automations, setAutomations] = useState<Automation[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [deleteId, setDeleteId] = useState<string | null>(null);

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

  const handleExecute = async (id: string) => {
    toast.info("Funcionalidade de execução em desenvolvimento");
    // TODO: Implementar execução via Edge Function
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-card">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center gap-3">
            <Bot className="h-8 w-8 text-primary" />
            <div>
              <h1 className="text-xl font-bold">Automação ERP</h1>
              <p className="text-sm text-muted-foreground">
                Gerencie suas automações de extração de dados
              </p>
            </div>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="container mx-auto px-4 py-8">
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
    </div>
  );
}
