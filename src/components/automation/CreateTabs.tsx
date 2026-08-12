import { useState } from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Sparkles, MousePointerClick, PencilLine, Save, Loader2 } from "lucide-react";
import { AIPlannerCard } from "./AIPlannerCard";
import { ExtensionRecorder } from "./ExtensionRecorder";
import { AutomationStep } from "@/types/automation";

export interface CreateTabsProps {
  automationName: string;
  onAutomationNameChange: (n: string) => void;
  steps: AutomationStep[];
  onStepsChange: (s: AutomationStep[]) => void;
  onSave: () => Promise<void>;
  saving: boolean;
}

type TabValue = "manual" | "record" | "ai";

/**
 * 3-tab authoring strip — the heart of P9. Each tab writes into the parent's
 * `steps` slot, and a single Save button persists via the parent's
 * `createAutomation` flow.
 *
 * - Manual: edit NavRunner DSL JSON directly.
 * - Record: ExtensionRecorder (Chrome ext) feeds steps via `onStepsReady`.
 * - AI: AIPlannerCard is self-contained (saves internally, fires
 *   `automation-created`). The parent's Save action is independent and acts on
 *   whatever is currently in `steps` (from Manual or Record).
 */
export function CreateTabs({
  automationName,
  onAutomationNameChange,
  steps,
  onStepsChange,
  onSave,
  saving,
}: CreateTabsProps) {
  const [tab, setTab] = useState<TabValue>("manual");

  const canSave =
    !saving && automationName.trim().length > 0 && steps.length > 0;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Nova automação</CardTitle>
          <CardDescription>
            Dá um nome pra ela — pode renomear depois.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          <Label htmlFor="automation-name">Nome</Label>
          <Input
            id="automation-name"
            value={automationName}
            onChange={(e) => onAutomationNameChange(e.target.value)}
            placeholder="Ex: Cotação FIPE - APVS"
          />
        </CardContent>
      </Card>

      <Tabs
        value={tab}
        onValueChange={(v) => setTab(v as TabValue)}
      >
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="manual">
            <PencilLine className="h-4 w-4 mr-2" /> Manual
          </TabsTrigger>
          <TabsTrigger value="record">
            <MousePointerClick className="h-4 w-4 mr-2" /> Gravar
          </TabsTrigger>
          <TabsTrigger value="ai">
            <Sparkles className="h-4 w-4 mr-2" /> AI Planner
          </TabsTrigger>
        </TabsList>

        <TabsContent value="manual">
          <Card>
            <CardHeader>
              <CardTitle>Steps (JSON)</CardTitle>
              <CardDescription>
                Edite o NavRunner DSL à mão, ou cole um draft do AI Planner aqui.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Textarea
                value={JSON.stringify(steps, null, 2)}
                onChange={(e) => {
                  try {
                    const parsed = JSON.parse(e.target.value);
                    if (Array.isArray(parsed)) onStepsChange(parsed as AutomationStep[]);
                  } catch {
                    /* invalid JSON — keep current steps */
                  }
                }}
                rows={20}
                className="font-mono text-xs"
              />
              <p className="text-xs text-muted-foreground mt-2">
                {steps.length} step{steps.length === 1 ? "" : "s"} carregados.
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="record">
          <Card>
            <CardHeader>
              <CardTitle>Gravar do navegador</CardTitle>
              <CardDescription>
                Usa a extensão Chrome NavRecorder (carregue como unpacked em{" "}
                <code>chrome://extensions</code>). Ela grava a sessão real e
                converte pra NavRunner DSL.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ExtensionRecorder
                isOpen={true}
                onClose={() => setTab("manual")}
                onStepsReady={(s) => onStepsChange(s)}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="ai">
          <AIPlannerCard />
          <p className="text-xs text-muted-foreground mt-2">
            O AI Planner salva a automação por conta própria. O botão
            <strong> Salvar </strong> abaixo só é necessário quando você
            montou os steps pelas abas Manual ou Gravar.
          </p>
        </TabsContent>
      </Tabs>

      <div className="flex items-center gap-3">
        <Button onClick={onSave} disabled={!canSave}>
          {saving ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : (
            <Save className="h-4 w-4 mr-2" />
          )}
          {saving ? "Salvando..." : "Salvar automação"}
        </Button>
        <span className="text-xs text-muted-foreground">
          {steps.length} step{steps.length === 1 ? "" : "s"} prontos
        </span>
      </div>
    </div>
  );
}