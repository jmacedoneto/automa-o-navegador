import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { StepsList } from "./StepsList";
import { AutomationStep } from "@/types/automation";
import { supabase } from "@/integrations/supabase/client";
import { toast } from "sonner";
import { Loader2, Sparkles, Save, Bot } from "lucide-react";

export function AutomationForm() {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [erpUrl, setErpUrl] = useState("");
  const [browserlessUrl, setBrowserlessUrl] = useState("");
  const [sheetsUrl, setSheetsUrl] = useState("");
  const [instructions, setInstructions] = useState("");
  const [steps, setSteps] = useState<AutomationStep[]>([]);
  const [notes, setNotes] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const handleGenerateSteps = async () => {
    if (!instructions.trim()) {
      toast.error("Por favor, descreva o que você quer automatizar");
      return;
    }

    setIsGenerating(true);
    try {
      const { data, error } = await supabase.functions.invoke('generate-steps', {
        body: { instructions, erpUrl }
      });

      if (error) {
        throw error;
      }

      if (data.error) {
        throw new Error(data.error);
      }

      setSteps(data.steps || []);
      setNotes(data.notes || "");
      toast.success("Passos gerados com sucesso!");
    } catch (error) {
      console.error("Error generating steps:", error);
      toast.error("Erro ao gerar passos. Tente novamente.");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSave = async () => {
    if (!name.trim()) {
      toast.error("Por favor, dê um nome para a automação");
      return;
    }

    if (steps.length === 0) {
      toast.error("Por favor, gere ou adicione os passos da automação");
      return;
    }

    setIsSaving(true);
    try {
      const { error } = await supabase.from('automations').insert([{
        name,
        description: description || null,
        erp_url: erpUrl,
        browserless_url: browserlessUrl,
        sheets_url: sheetsUrl,
        instructions,
        steps: JSON.parse(JSON.stringify(steps)),
      }]);

      if (error) throw error;

      toast.success("Automação salva com sucesso!");
      
      // Reset form
      setName("");
      setDescription("");
      setErpUrl("");
      setBrowserlessUrl("");
      setSheetsUrl("");
      setInstructions("");
      setSteps([]);
      setNotes("");
    } catch (error) {
      console.error("Error saving automation:", error);
      toast.error("Erro ao salvar automação");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Configuration Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bot className="h-5 w-5" />
            Nova Automação
          </CardTitle>
          <CardDescription>
            Configure a automação do seu ERP. Descreva o que você quer fazer e a IA vai gerar os passos automaticamente.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="name">Nome da Automação *</Label>
              <Input
                id="name"
                placeholder="Ex: Exportar Vendas Mensais"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Descrição</Label>
              <Input
                id="description"
                placeholder="Breve descrição do que a automação faz"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="erpUrl">URL do ERP</Label>
              <Input
                id="erpUrl"
                placeholder="https://seu-erp.com.br"
                value={erpUrl}
                onChange={(e) => setErpUrl(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="browserlessUrl">URL do Browserless</Label>
              <Input
                id="browserlessUrl"
                placeholder="http://seu-vps:3000"
                value={browserlessUrl}
                onChange={(e) => setBrowserlessUrl(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="sheetsUrl">URL do Google Sheets</Label>
              <Input
                id="sheetsUrl"
                placeholder="https://docs.google.com/spreadsheets/d/..."
                value={sheetsUrl}
                onChange={(e) => setSheetsUrl(e.target.value)}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Instructions Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            Descreva a Automação
          </CardTitle>
          <CardDescription>
            Explique em português o que você quer fazer no ERP. A IA vai interpretar e gerar os passos automaticamente.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Textarea
            placeholder="Exemplo: Logar no sistema com meu usuário e senha, ir no menu Relatórios, clicar em Vendas Mensal, selecionar o mês atual, e exportar a planilha Excel com os dados."
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
            className="min-h-[120px]"
          />
          
          <Button 
            onClick={handleGenerateSteps} 
            disabled={isGenerating || !instructions.trim()}
            className="w-full"
          >
            {isGenerating ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Gerando passos...
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4 mr-2" />
                Gerar Passos com IA
              </>
            )}
          </Button>

          {notes && (
            <div className="p-3 bg-muted rounded-lg text-sm">
              <strong>Observações da IA:</strong> {notes}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Steps Card */}
      <Card>
        <CardHeader>
          <CardTitle>Passos da Automação</CardTitle>
          <CardDescription>
            Revise e ajuste os passos gerados. Você pode editar seletores, adicionar ou remover passos.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <StepsList steps={steps} onStepsChange={setSteps} />
        </CardContent>
      </Card>

      {/* Save Button */}
      {steps.length > 0 && (
        <Button 
          onClick={handleSave} 
          disabled={isSaving || !name.trim()}
          size="lg"
          className="w-full"
        >
          {isSaving ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              Salvando...
            </>
          ) : (
            <>
              <Save className="h-4 w-4 mr-2" />
              Salvar Automação
            </>
          )}
        </Button>
      )}
    </div>
  );
}
