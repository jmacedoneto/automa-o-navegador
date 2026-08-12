import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { CreateTabs } from "@/components/automation/CreateTabs";
import { AutomationStep } from "@/types/automation";
import { createAutomation } from "@/services/automationService";

/**
 * Single-pane authoring page (P9). Three authoring modes — Manual JSON,
 * Record (Chrome extension), and AI Planner — share a name field and a
 * single save action. Combines what used to be the inline AIPlannerCard
 * inside AutomationList with the manual editor and the recorder embed.
 */
export function CreateAutomationPage() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [steps, setSteps] = useState<AutomationStep[]>([]);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!name.trim()) {
      toast.error("Dá um nome pra automação");
      return;
    }
    if (steps.length === 0) {
      toast.error("Adiciona pelo menos 1 step (Manual, Gravar ou AI Planner)");
      return;
    }
    setSaving(true);
    try {
      const created = await createAutomation({
        name,
        description: "Created via unified authoring (P9)",
        erp_url: "",
        instructions: "",
        steps,
        credentials: {},
        outputs: [],
        is_active: false,
      } as never);
      toast.success("Automação criada!");
      window.dispatchEvent(new CustomEvent("automation-created"));
      navigate(`/automation/${created.id}`);
    } catch (err) {
      toast.error(
        `Erro ao salvar: ${err instanceof Error ? err.message : String(err)}`
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="container mx-auto p-6 max-w-4xl">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">
          Criar automação
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Escolhe como você quer começar — manual, gravando no Chrome, ou
          descrevendo em uma frase pro AI Planner gerar o rascunho.
        </p>
      </div>

      <CreateTabs
        automationName={name}
        onAutomationNameChange={setName}
        steps={steps}
        onStepsChange={setSteps}
        onSave={handleSave}
        saving={saving}
      />
    </div>
  );
}

export default CreateAutomationPage;