import { useEffect, useState, useCallback, useRef } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { Loader2, Save, Key, Wifi, WifiOff, Bot, MessageCircle, RefreshCw } from "lucide-react";
import { Header } from "@/components/layout/Header";
import { ALLOWED_OPENAI_MODELS, MINI_TIER_MODELS, coerceOpenAIModel } from "@/lib/openaiModels";

type SettingsMap = {
  browserless_url: string;
  browserless_token: string;
  workspace_root: string;
  openai_api_key: string;
  openai_model: string;
  evolution_api_url: string;
  evolution_api_key: string;
  evolution_instance: string;
};

const EMPTY: SettingsMap = {
  browserless_url: "",
  browserless_token: "",
  workspace_root: "/root",
  openai_api_key: "",
  openai_model: coerceOpenAIModel(),
  evolution_api_url: "",
  evolution_api_key: "",
  evolution_instance: "",
};

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export default function Settings() {
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isFetchingModels, setIsFetchingModels] = useState(false);
  const [models, setModels] = useState<string[]>([...ALLOWED_OPENAI_MODELS]);
  const [settings, setSettings] = useState<SettingsMap>(EMPTY);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchModels = useCallback(async (key: string) => {
    if (!key.trim()) {
      setModels([...ALLOWED_OPENAI_MODELS]);
      return;
    }

    setIsFetchingModels(true);
    try {
      const params = new URLSearchParams({ key });
      const data = await apiFetch<{ models: string[] }>(`/api/ai/models?${params}`);
      setModels(data.models.length > 0 ? data.models : [...ALLOWED_OPENAI_MODELS]);
    } catch {
      toast.error("Não foi possível buscar modelos. Verifique a API Key da OpenAI.");
      setModels([...ALLOWED_OPENAI_MODELS]);
    } finally {
      setIsFetchingModels(false);
    }
  }, []);

  useEffect(() => {
    apiFetch<SettingsMap>("/api/settings")
      .then((data) => {
        setSettings({ ...EMPTY, ...data, openai_model: coerceOpenAIModel(data.openai_model) });
        if (data.openai_api_key) fetchModels(data.openai_api_key);
      })
      .catch(() => toast.error("Erro ao carregar configurações"))
      .finally(() => setIsLoading(false));
  }, [fetchModels]);

  const set = (key: keyof SettingsMap, value: string) => {
    setSettings((prev) => ({
      ...prev,
      [key]: key === "openai_model" ? coerceOpenAIModel(value) : value,
    }));

    if (key === "openai_api_key") {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => fetchModels(value), 800);
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await apiFetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...settings, openai_model: coerceOpenAIModel(settings.openai_model) }),
      });
      toast.success("Configurações salvas!");
    } catch {
      toast.error("Erro ao salvar configurações");
    } finally {
      setIsSaving(false);
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

  const currentModel = coerceOpenAIModel(settings.openai_model) || "gpt-5.4-mini";
  const modelOptions = [...new Set([currentModel, ...models])]
    .filter((m): m is string => !!m && (ALLOWED_OPENAI_MODELS as readonly string[]).includes(m));

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="container py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold">Configurações</h1>
          <p className="text-muted-foreground mt-1">
            Configure as credenciais e integrações do sistema
          </p>
        </div>

        <div className="max-w-2xl space-y-6">

          {/* ── Browserless ── */}
          <Card className="border-l-4 border-l-sky-500">
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-sky-500/10">
                  <Wifi className="h-5 w-5 text-sky-500" />
                </div>
                <div>
                  <CardTitle>Browserless</CardTitle>
                  <CardDescription>
                    Endpoint usado para executar as automações no navegador.
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="browserless_url">URL do Browserless</Label>
                <Input
                  id="browserless_url"
                  placeholder="http://autopilot_browser:3000"
                  value={settings.browserless_url}
                  onChange={(e) => set("browserless_url", e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="browserless_token">Token do Browserless</Label>
                <Input
                  id="browserless_token"
                  type="password"
                  placeholder="••••••••••••"
                  value={settings.browserless_token}
                  onChange={(e) => set("browserless_token", e.target.value)}
                />
              </div>
            </CardContent>
          </Card>

          {/* ── OpenAI ── */}
          <Card className="border-l-4 border-l-violet-500">
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-violet-500/10">
                  <Bot className="h-5 w-5 text-violet-500" />
                </div>
                <div>
                  <CardTitle>OpenAI</CardTitle>
                  <CardDescription>
                    Usado para gerar passos a partir de texto e preencher formulários com IA.
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="workspace_root">Workspace principal</Label>
                <Input
                  id="workspace_root"
                  placeholder="/root"
                  value={settings.workspace_root}
                  onChange={(e) => set("workspace_root", e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="oai_key" className="flex items-center gap-2">
                  <Key className="h-4 w-4 text-muted-foreground" /> API Key
                </Label>
                <div className="relative">
                  <Input
                    id="oai_key"
                    type="password"
                    placeholder="sk-••••••••••••••••••••••••••••••••••••••••••••"
                    value={settings.openai_api_key}
                    onChange={(e) => set("openai_api_key", e.target.value)}
                    className="pr-10"
                  />
                  {isFetchingModels && (
                    <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 animate-spin text-muted-foreground" />
                  )}
                </div>
                <p className="text-xs text-muted-foreground">
                  Ao digitar a chave, validamos apenas os modelos permitidos: `gpt-5.4-mini` e `gpt-5.4`.
                </p>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="oai_model">Modelo padrão</Label>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-7 gap-1.5 text-xs text-muted-foreground"
                    disabled={isFetchingModels || !settings.openai_api_key}
                    onClick={() => fetchModels(settings.openai_api_key)}
                  >
                    {isFetchingModels
                      ? <Loader2 className="h-3 w-3 animate-spin" />
                      : <RefreshCw className="h-3 w-3" />}
                    {isFetchingModels ? "Buscando..." : "Atualizar lista"}
                  </Button>
                </div>

                {models.length === 0 && !settings.openai_api_key && (
                  <div className="flex items-center gap-2 rounded-lg border border-dashed p-3 text-sm text-muted-foreground">
                    <WifiOff className="h-4 w-4 shrink-0" />
                    Informe a API Key acima para validar os modelos permitidos na sua conta OpenAI.
                  </div>
                )}

                {models.length === 0 && settings.openai_api_key && !isFetchingModels && (
                  <div className="flex items-center gap-2 rounded-lg border border-dashed p-3 text-sm text-muted-foreground">
                    <RefreshCw className="h-4 w-4 shrink-0" />
                    Clique em "Atualizar lista" para verificar quais modelos estão disponíveis na sua conta.
                  </div>
                )}

                <Select
                  value={currentModel}
                  onValueChange={(value) => set("openai_model", value)}
                >
                  <SelectTrigger id="oai_model">
                    <SelectValue placeholder="Selecione um modelo..." />
                  </SelectTrigger>
                  <SelectContent className="max-h-72">
                    <SelectGroup>
                      <SelectLabel>2,5 M tokens/dia (recomendado)</SelectLabel>
                      {modelOptions
                        .filter((m) => (MINI_TIER_MODELS as readonly string[]).includes(m))
                        .map((model) => (
                          <SelectItem key={model} value={model}>{model}</SelectItem>
                        ))}
                    </SelectGroup>
                    <SelectGroup>
                      <SelectLabel>250 K tokens/dia</SelectLabel>
                      {modelOptions
                        .filter((m) => !(MINI_TIER_MODELS as readonly string[]).includes(m))
                        .map((model) => (
                          <SelectItem key={model} value={model}>{model}</SelectItem>
                        ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>

                <p className="text-xs text-muted-foreground">
                  Snapshots com data (ex: <code>gpt-5.4-mini-2026-03-17</code>) são normalizados automaticamente para o alias base do plano gratuito.
                </p>
              </div>
            </CardContent>
          </Card>

          {/* ── Evolution / WhatsApp ── */}
          <Card className="border-l-4 border-l-green-500">
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-500/10">
                  <MessageCircle className="h-5 w-5 text-green-500" />
                </div>
                <div>
                  <CardTitle>WhatsApp (Evolution API)</CardTitle>
                  <CardDescription>
                    Envio de resultados e arquivos via WhatsApp.
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="evo_url" className="flex items-center gap-2">
                  <Wifi className="h-4 w-4 text-muted-foreground" /> URL da Evolution API
                </Label>
                <Input
                  id="evo_url"
                  placeholder="https://evolution.suavps.com"
                  value={settings.evolution_api_url}
                  onChange={(e) => set("evolution_api_url", e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="evo_key" className="flex items-center gap-2">
                  <Key className="h-4 w-4 text-muted-foreground" /> API Key
                </Label>
                <Input
                  id="evo_key"
                  type="password"
                  placeholder="••••••••••••"
                  value={settings.evolution_api_key}
                  onChange={(e) => set("evolution_api_key", e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="evo_instance">Nome da Instância</Label>
                <Input
                  id="evo_instance"
                  placeholder="minha-instancia"
                  value={settings.evolution_instance}
                  onChange={(e) => set("evolution_instance", e.target.value)}
                />
              </div>
            </CardContent>
          </Card>

          <div className="flex justify-end">
            <Button onClick={handleSave} disabled={isSaving} size="lg" className="gap-2">
              {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              {isSaving ? "Salvando..." : "Salvar configurações"}
            </Button>
          </div>
        </div>
      </main>
    </div>
  );
}
