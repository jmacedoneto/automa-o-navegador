import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { StepsList } from "@/components/StepsList";
import { AutomationStep, Automation } from "@/types/automation";
import { 
  fetchAutomationById, 
  createAutomation, 
  updateAutomation,
  generateSteps
} from "@/services/automationService";
import { toast } from "sonner";
import { 
  Loader2, 
  Sparkles, 
  Save, 
  Bot, 
  ArrowLeft,
  Settings,
  Webhook,
  Key,
  Globe,
  FileSpreadsheet
} from "lucide-react";
import { Header } from "@/components/layout/Header";

export default function AutomationEditor() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isNew = !id || id === 'new';

  const [isLoading, setIsLoading] = useState(!isNew);
  const [isSaving, setIsSaving] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);

  // Form state
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [erpUrl, setErpUrl] = useState("");
  const [sheetsUrl, setSheetsUrl] = useState("");
  const [instructions, setInstructions] = useState("");
  const [steps, setSteps] = useState<AutomationStep[]>([]);
  const [notes, setNotes] = useState("");
  const [webhookUrl, setWebhookUrl] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  useEffect(() => {
    if (!isNew && id) {
      loadAutomation(id);
    }
  }, [id, isNew]);

  const loadAutomation = async (automationId: string) => {
    try {
      const data = await fetchAutomationById(automationId);
      if (!data) {
        toast.error("Automação não encontrada");
        navigate('/');
        return;
      }

      setName(data.name);
      setDescription(data.description || "");
      setErpUrl(data.erp_url);
      setSheetsUrl(data.sheets_url);
      setInstructions(data.instructions);
      setSteps(data.steps || []);
      setWebhookUrl(data.webhook_url || "");
      setUsername(data.credentials?.username || "");
      setPassword(data.credentials?.password || "");
    } catch (error) {
      console.error("Error loading automation:", error);
      toast.error("Erro ao carregar automação");
      navigate('/');
    } finally {
      setIsLoading(false);
    }
  };

  const handleGenerateSteps = async () => {
    if (!instructions.trim()) {
      toast.error("Por favor, descreva o que você quer automatizar");
      return;
    }

    setIsGenerating(true);
    try {
      const result = await generateSteps(instructions, erpUrl);
      setSteps(result.steps);
      setNotes(result.notes);
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
      const automationData: Omit<Automation, 'id' | 'created_at' | 'updated_at'> = {
        name,
        description: description || null,
        erp_url: erpUrl,
        browserless_url: "", // Agora vem das configurações globais
        sheets_url: sheetsUrl,
        instructions,
        steps,
        is_active: true,
        webhook_url: webhookUrl || undefined,
        credentials: (username || password) ? { username, password } : undefined,
      };

      if (isNew) {
        await createAutomation(automationData);
        toast.success("Automação criada com sucesso!");
      } else if (id) {
        await updateAutomation(id, automationData);
        toast.success("Automação atualizada com sucesso!");
      }
      
      navigate('/');
    } catch (error) {
      console.error("Error saving automation:", error);
      toast.error("Erro ao salvar automação");
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

  return (
    <div className="min-h-screen bg-background">
      <Header />

      {/* Sub-header */}
      <div className="border-b bg-card/50">
        <div className="container py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="icon" onClick={() => navigate('/')}>
                <ArrowLeft className="h-5 w-5" />
              </Button>
              <div>
                <h1 className="text-xl font-bold">
                  {isNew ? 'Nova Automação' : 'Editar Automação'}
                </h1>
                <p className="text-sm text-muted-foreground">
                  Configure os detalhes da automação
                </p>
              </div>
            </div>
            <Button 
              onClick={handleSave} 
              disabled={isSaving || !name.trim()}
              className="gap-2 gradient-primary text-primary-foreground"
            >
              {isSaving ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Salvando...
                </>
              ) : (
                <>
                  <Save className="h-4 w-4" />
                  Salvar
                </>
              )}
            </Button>
          </div>
        </div>
      </div>

      {/* Main content */}
      <main className="container py-6">
        <Tabs defaultValue="config" className="space-y-6">
          <TabsList className="grid w-full grid-cols-4 max-w-2xl bg-muted/50">
            <TabsTrigger value="config" className="gap-2 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
              <Settings className="h-4 w-4" />
              <span className="hidden sm:inline">Configuração</span>
            </TabsTrigger>
            <TabsTrigger value="steps" className="gap-2 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
              <Bot className="h-4 w-4" />
              <span className="hidden sm:inline">Passos</span>
            </TabsTrigger>
            <TabsTrigger value="credentials" className="gap-2 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
              <Key className="h-4 w-4" />
              <span className="hidden sm:inline">Credenciais</span>
            </TabsTrigger>
            <TabsTrigger value="webhook" className="gap-2 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
              <Webhook className="h-4 w-4" />
              <span className="hidden sm:inline">Webhook</span>
            </TabsTrigger>
          </TabsList>

          {/* Config Tab */}
          <TabsContent value="config" className="space-y-6">
            <Card className="border-l-4 border-l-primary">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Settings className="h-5 w-5 text-primary" />
                  Informações Básicas
                </CardTitle>
                <CardDescription>
                  Defina o nome e as URLs necessárias para a automação
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="erpUrl" className="flex items-center gap-2">
                      <Globe className="h-4 w-4 text-muted-foreground" />
                      URL do ERP
                    </Label>
                    <Input
                      id="erpUrl"
                      placeholder="https://seu-erp.com.br"
                      value={erpUrl}
                      onChange={(e) => setErpUrl(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="sheetsUrl" className="flex items-center gap-2">
                      <FileSpreadsheet className="h-4 w-4 text-muted-foreground" />
                      URL do Google Sheets
                    </Label>
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
          </TabsContent>

          {/* Steps Tab */}
          <TabsContent value="steps" className="space-y-6">
            <Card className="border-l-4 border-l-accent">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Sparkles className="h-5 w-5 text-accent" />
                  Descreva a Automação
                </CardTitle>
                <CardDescription>
                  Explique em português o que você quer fazer no ERP
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
                  className="w-full gap-2 gradient-primary text-primary-foreground"
                >
                  {isGenerating ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Gerando passos...
                    </>
                  ) : (
                    <>
                      <Sparkles className="h-4 w-4" />
                      Gerar Passos com IA
                    </>
                  )}
                </Button>

                {notes && (
                  <div className="p-4 bg-info/10 border border-info/20 rounded-lg text-sm">
                    <strong className="text-info">Observações da IA:</strong>
                    <p className="mt-1 text-muted-foreground">{notes}</p>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Bot className="h-5 w-5 text-primary" />
                  Passos da Automação
                </CardTitle>
                <CardDescription>
                  Revise e ajuste os passos gerados
                </CardDescription>
              </CardHeader>
              <CardContent>
                <StepsList steps={steps} onStepsChange={setSteps} />
              </CardContent>
            </Card>
          </TabsContent>

          {/* Credentials Tab */}
          <TabsContent value="credentials" className="space-y-6">
            <Card className="border-l-4 border-l-warning">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Key className="h-5 w-5 text-warning" />
                  Credenciais do ERP
                </CardTitle>
                <CardDescription>
                  Configure usuário e senha para login automático. 
                  Use {"{{username}}"} e {"{{password}}"} nos passos de digitação.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-xl">
                  <div className="space-y-2">
                    <Label htmlFor="username">Usuário</Label>
                    <Input
                      id="username"
                      placeholder="seu.usuario"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="password">Senha</Label>
                    <Input
                      id="password"
                      type="password"
                      placeholder="••••••••"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                    />
                  </div>
                </div>
                <p className="text-sm text-muted-foreground">
                  As credenciais são armazenadas de forma segura e usadas apenas durante a execução.
                </p>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Webhook Tab */}
          <TabsContent value="webhook" className="space-y-6">
            <Card className="border-l-4 border-l-info">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Webhook className="h-5 w-5 text-info" />
                  Integração Webhook
                </CardTitle>
                <CardDescription>
                  Configure um webhook para receber os dados extraídos no N8N ou outra ferramenta
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="webhookUrl">URL do Webhook (N8N)</Label>
                  <Input
                    id="webhookUrl"
                    placeholder="https://seu-n8n.com/webhook/..."
                    value={webhookUrl}
                    onChange={(e) => setWebhookUrl(e.target.value)}
                  />
                </div>
                <p className="text-sm text-muted-foreground">
                  Após cada execução bem-sucedida, os dados extraídos serão enviados para este webhook.
                </p>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}
