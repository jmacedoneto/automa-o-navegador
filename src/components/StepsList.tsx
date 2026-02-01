import { AutomationStep } from "@/types/automation";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Trash2, GripVertical, Plus } from "lucide-react";

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

  if (steps.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <p>Nenhum passo gerado ainda.</p>
        <p className="text-sm mt-2">Descreva o que você quer automatizar e clique em "Gerar Passos"</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {steps.map((step, index) => (
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
      ))}
      
      {isEditable && (
        <Button variant="outline" onClick={addStep} className="w-full">
          <Plus className="h-4 w-4 mr-2" />
          Adicionar Passo
        </Button>
      )}
    </div>
  );
}
