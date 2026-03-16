import { AutomationStep } from "@/types/automation";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Trash2, GripVertical, Plus, Upload } from "lucide-react";
import { useRef } from "react";
import { toast } from "sonner";

interface StepsListProps {
  steps: AutomationStep[];
  onStepsChange: (steps: AutomationStep[]) => void;
  isEditable?: boolean;
}

const actionOptions = [
  { value: 'navigate', label: 'Navegar' },
  { value: 'click', label: 'Clicar' },
  { value: 'type', label: 'Digitar' },
  { value: 'wait', label: 'Aguardar' },
  { value: 'waitForSelector', label: 'Aguardar Elemento' },
  { value: 'screenshot', label: 'Screenshot' },
  { value: 'extractTable', label: 'Extrair Tabela' },
];

export function StepsList({ steps, onStepsChange, isEditable = true }: StepsListProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const updateStep = (index: number, field: keyof AutomationStep, value: string | number) => {
    const newSteps = [...steps];
    newSteps[index] = { ...newSteps[index], [field]: value };
    onStepsChange(newSteps);
  };

  const removeStep = (index: number) => {
    const newSteps = steps.filter((_, i) => i !== index);
    // Reorder the remaining steps
    const reorderedSteps = newSteps.map((step, i) => ({ ...step, order: i + 1 }));
    onStepsChange(reorderedSteps);
  };

  const addStep = () => {
    const newStep: AutomationStep = {
      order: steps.length + 1,
      action: 'click',
      selector: '',
      value: '',
      description: '',
      waitTime: 1000,
    };
    onStepsChange([...steps, newStep]);
  };

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const content = e.target?.result as string;
        const jsonSteps = JSON.parse(content);
        
        if (!Array.isArray(jsonSteps)) {
            throw new Error("O arquivo JSON não contém um array válido de passos.");
        }

        // Sanitize and format the imported steps
        const importedSteps: AutomationStep[] = jsonSteps.map((step: any, index: number) => ({
            order: (steps.length || 0) + index + 1,
            action: step.action || 'click',
            selector: step.selector || '',
            value: step.value || '',
            description: step.description || '',
            waitTime: step.waitTime || 1000
        }));

        // Append to existing steps or replace if empty
        onStepsChange([...steps, ...importedSteps]);
        toast.success(`${importedSteps.length} passos importados com sucesso!`);
        
      } catch (error) {
        console.error("Erro ao importar JSON:", error);
        toast.error("Erro ao importar o arquivo. Verifique se é um arquivo de automação válido.");
      }
      
      // Reset file input
      if (fileInputRef.current) {
         fileInputRef.current.value = "";
      }
    };
    reader.readAsText(file);
  };

  return (
    <div className="space-y-3">
      {steps.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">
          <p>Nenhum passo gerado ainda.</p>
          <p className="text-sm mt-2">Descreva o que você quer automatizar e clique em "Gerar Passos" ou grave com a Extensão</p>
        </div>
      ) : (
        steps.map((step, index) => (
          <Card key={index} className="border-border/50">
            <CardContent className="p-4">
              <div className="flex items-start gap-3">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <GripVertical className="h-4 w-4" />
                  <span className="font-mono text-sm font-medium w-6">{step.order}</span>
                </div>
                
                <div className="flex-1 grid gap-3">
                  <div className="grid grid-cols-2 gap-3">
                    <Select
                      value={step.action}
                      onValueChange={(value) => updateStep(index, 'action', value)}
                      disabled={!isEditable}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {actionOptions.map((option) => (
                          <SelectItem key={option.value} value={option.value}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    
                    <Input
                      placeholder="Seletor CSS/XPath"
                      value={step.selector || ''}
                      onChange={(e) => updateStep(index, 'selector', e.target.value)}
                      disabled={!isEditable}
                      className="font-mono text-sm"
                    />
                  </div>
                  
                  <Input
                    placeholder="Descrição do passo"
                    value={step.description}
                    onChange={(e) => updateStep(index, 'description', e.target.value)}
                    disabled={!isEditable}
                  />
                  
                  {(step.action === 'type' || step.action === 'navigate') && (
                    <Input
                      placeholder={step.action === 'navigate' ? 'URL' : 'Valor a digitar'}
                      value={step.value || ''}
                      onChange={(e) => updateStep(index, 'value', e.target.value)}
                      disabled={!isEditable}
                    />
                  )}
                  
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">Espera:</span>
                    <Input
                      type="number"
                      placeholder="1000"
                      value={step.waitTime || 1000}
                      onChange={(e) => updateStep(index, 'waitTime', parseInt(e.target.value) || 1000)}
                      disabled={!isEditable}
                      className="w-24"
                    />
                    <span className="text-sm text-muted-foreground">ms</span>
                  </div>
                </div>
                
                {isEditable && (
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => removeStep(index)}
                    className="text-destructive hover:text-destructive hover:bg-destructive/10"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        ))
      )}
      
      {isEditable && (
        <div className="flex gap-2 w-full mt-4">
          <Button variant="outline" onClick={addStep} className="flex-1">
            <Plus className="h-4 w-4 mr-2" />
            Adicionar Passo Manualmente
          </Button>
          
          <Input 
             type="file" 
             accept=".json" 
             className="hidden" 
             ref={fileInputRef}
             onChange={handleFileUpload}
          />
          <Button 
             variant="secondary" 
             onClick={() => fileInputRef.current?.click()} 
             className="flex-1 border border-border"
          >
            <Upload className="h-4 w-4 mr-2 text-primary" />
            Importar JSON (Extensão)
          </Button>
        </div>
      )}
    </div>
  );
}
