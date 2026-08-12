import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Sparkles, Loader2, Save, X } from "lucide-react";
import { toast } from "sonner";
import { fetchPlan, draftToAutomation, PlannerDraft } from "@/services/plannerService";
import { createAutomation } from "@/services/automationService";

export function AIPlannerCard() {
  const [description, setDescription] = useState("");
  const [siteUrl, setSiteUrl] = useState("");
  const [authHint, setAuthHint] = useState("");
  const [draft, setDraft] = useState<PlannerDraft | null>(null);
  const [busy, setBusy] = useState(false);

  const handleGenerate = async () => {
    if (!description.trim()) {
      toast.error("Descreva o que você quer automatizar");
      return;
    }
    setBusy(true);
    try {
      const d = await fetchPlan({ description, site_url: siteUrl, auth_hint: authHint });
      setDraft(d);
      toast.success("Draft gerado — revise e ajuste antes de salvar");
    } catch (err) {
      toast.error(`Erro ao gerar: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setBusy(false);
    }
  };

  const handleSave = async () => {
    if (!draft) return;
    try {
      await createAutomation(draftToAutomation(draft) as never);
      toast.success("Automação criada a partir do draft");
      setDraft(null);
      setDescription("");
      setSiteUrl("");
      setAuthHint("");
      window.dispatchEvent(new CustomEvent("automation-created"));
    } catch (err) {
      toast.error(`Erro ao salvar: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  return (
    <Card className="border-dashed border-primary/40 bg-gradient-to-br from-background to-primary/5">
      <CardHeader>
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-primary" />
          <CardTitle>AI Planner</CardTitle>
          <Badge variant="secondary" className="ml-auto">P6</Badge>
        </div>
        <CardDescription>
          Descreva em uma frase o que você quer automatizar. Eu gero um rascunho
          em NavRunner DSL pra você revisar e salvar.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div>
          <Label htmlFor="planner-description">Descrição</Label>
          <Textarea
            id="planner-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder='Ex: "Automatize cotação de carro: abre app.apvs.vc, faz login, preenche código FIPE, retorna o menor plano"'
            rows={3}
          />
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <Label htmlFor="planner-url">URL base (opcional)</Label>
            <Input
              id="planner-url"
              value={siteUrl}
              onChange={(e) => setSiteUrl(e.target.value)}
              placeholder="https://app.apvs.vc"
            />
          </div>
          <div>
            <Label htmlFor="planner-auth">Auth hint (opcional)</Label>
            <Input
              id="planner-auth"
              value={authHint}
              onChange={(e) => setAuthHint(e.target.value)}
              placeholder='"login com CNPJ + senha" ou "no auth"'
            />
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button onClick={handleGenerate} disabled={busy || !description.trim()}>
            {busy ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Sparkles className="h-4 w-4 mr-2" />}
            Gerar rascunho
          </Button>
          {draft && (
            <Button variant="ghost" onClick={() => setDraft(null)}>
              <X className="h-4 w-4 mr-1" /> Descartar
            </Button>
          )}
        </div>

        {draft && (
          <div className="rounded-md border bg-muted/40 p-3 space-y-2">
            <div className="flex items-center gap-2 text-sm font-medium">
              <Sparkles className="h-3 w-3" />
              {draft.automation_name}
              <Badge variant="outline" className="ml-auto">{draft.steps.length} steps</Badge>
            </div>
            {draft.steps[0]?.auth && (
              <div className="text-xs text-muted-foreground">
                🔐 auth: {String(((draft.steps[0].auth as Record<string, unknown>) || {}).type || "unknown")}
              </div>
            )}
            <pre className="text-xs overflow-x-auto bg-background p-2 rounded border max-h-48">
{JSON.stringify(draft, null, 2)}
            </pre>
            {draft.notes && draft.notes.length > 0 && (
              <div className="text-xs space-y-1">
                <div className="font-medium">⚠️ Notas do planner:</div>
                <ul className="list-disc list-inside text-muted-foreground">
                  {draft.notes.map((n, i) => (<li key={i}>{n}</li>))}
                </ul>
              </div>
            )}
            <Button onClick={handleSave} className="w-full">
              <Save className="h-4 w-4 mr-2" /> Salvar como automação
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
