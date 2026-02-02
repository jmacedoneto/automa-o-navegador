import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { 
  getBrowserlessSettings, 
  saveBrowserlessSettings, 
  testBrowserlessConnection,
  BrowserlessSettings 
} from "@/services/settingsService";
import { 
  Loader2, 
  Save, 
  Server, 
  Key, 
  CheckCircle2, 
  XCircle,
  Wifi,
  ExternalLink
} from "lucide-react";
import { Header } from "@/components/layout/Header";

export default function Settings() {
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<boolean | null>(null);

  const [settings, setSettings] = useState<BrowserlessSettings>({
    url: "",
    token: "",
  });

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const data = await getBrowserlessSettings();
      setSettings(data);
    } catch (error) {
      console.error("Error loading settings:", error);
      toast.error("Erro ao carregar configurações");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await saveBrowserlessSettings(settings);
      toast.success("Configurações salvas com sucesso!");
    } catch (error) {
      console.error("Error saving settings:", error);
      toast.error("Erro ao salvar configurações");
    } finally {
      setIsSaving(false);
    }
  };

  const handleTestConnection = async () => {
    if (!settings.url) {
      toast.error("Por favor, insira a URL do Browserless");
      return;
    }

    setIsTesting(true);
    setTestResult(null);
    try {
      const result = await testBrowserlessConnection(settings.url, settings.token);
      setTestResult(result);
      if (result) {
        toast.success("Conexão bem-sucedida!");
      } else {
        toast.error("Não foi possível conectar ao Browserless");
      }
    } catch (error) {
      console.error("Error testing connection:", error);
      setTestResult(false);
      toast.error("Erro ao testar conexão");
    } finally {
      setIsTesting(false);
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

  return (
    <div className="min-h-screen bg-background">
      <Header />

      <main className="container py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold">Configurações</h1>
          <p className="text-muted-foreground mt-1">
            Configure as credenciais globais do sistema
          </p>
        </div>

        <div className="max-w-2xl space-y-6">
          {/* Browserless Config */}
          <Card className="border-l-4 border-l-primary">
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                  <Server className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <CardTitle>Browserless</CardTitle>
                  <CardDescription>
                    Configure a conexão com sua instância do Browserless
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="browserlessUrl" className="flex items-center gap-2">
                  <Wifi className="h-4 w-4 text-muted-foreground" />
                  URL do Browserless
                </Label>
                <Input
                  id="browserlessUrl"
                  placeholder="https://browserless.sua-vps.com"
                  value={settings.url}
                  onChange={(e) => setSettings({ ...settings, url: e.target.value })}
                />
                <p className="text-xs text-muted-foreground">
                  URL da sua instância Browserless hospedada na VPS
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="browserlessToken" className="flex items-center gap-2">
                  <Key className="h-4 w-4 text-muted-foreground" />
                  Token de Autenticação
                </Label>
                <Input
                  id="browserlessToken"
                  type="password"
                  placeholder="••••••••••••"
                  value={settings.token}
                  onChange={(e) => setSettings({ ...settings, token: e.target.value })}
                />
                <p className="text-xs text-muted-foreground">
                  Token configurado no Browserless (opcional, mas recomendado)
                </p>
              </div>

              {/* Test Result */}
              {testResult !== null && (
                <div
                  className={`flex items-center gap-2 rounded-lg p-3 ${
                    testResult
                      ? "bg-success/10 text-success"
                      : "bg-destructive/10 text-destructive"
                  }`}
                >
                  {testResult ? (
                    <>
                      <CheckCircle2 className="h-5 w-5" />
                      <span>Conexão estabelecida com sucesso!</span>
                    </>
                  ) : (
                    <>
                      <XCircle className="h-5 w-5" />
                      <span>Falha na conexão. Verifique a URL e o token.</span>
                    </>
                  )}
                </div>
              )}

              {/* Actions */}
              <div className="flex flex-wrap gap-3 pt-2">
                <Button
                  variant="outline"
                  onClick={handleTestConnection}
                  disabled={isTesting || !settings.url}
                >
                  {isTesting ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Testando...
                    </>
                  ) : (
                    <>
                      <Wifi className="h-4 w-4 mr-2" />
                      Testar Conexão
                    </>
                  )}
                </Button>
                <Button onClick={handleSave} disabled={isSaving}>
                  {isSaving ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Salvando...
                    </>
                  ) : (
                    <>
                      <Save className="h-4 w-4 mr-2" />
                      Salvar Configurações
                    </>
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Help Card */}
          <Card className="bg-muted/50">
            <CardContent className="pt-6">
              <div className="flex items-start gap-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-info/10">
                  <ExternalLink className="h-5 w-5 text-info" />
                </div>
                <div className="space-y-1">
                  <h4 className="font-medium">Precisa de ajuda?</h4>
                  <p className="text-sm text-muted-foreground">
                    O Browserless deve estar hospedado em uma VPS acessível externamente.
                    Certifique-se de que a porta está liberada e o serviço está rodando.
                  </p>
                  <a
                    href="https://www.browserless.io/docs"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
                  >
                    Ver documentação do Browserless
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}
