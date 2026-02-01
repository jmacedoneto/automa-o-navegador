import { AutomationForm } from "@/components/AutomationForm";

const Index = () => {
  return (
    <div className="min-h-screen bg-background py-8 px-4">
      <div className="max-w-4xl mx-auto">
        <header className="text-center mb-8">
          <h1 className="text-3xl font-bold tracking-tight mb-2">
            Automação ERP
          </h1>
          <p className="text-muted-foreground">
            Configure automações para extrair dados do seu ERP e enviar para o Google Sheets
          </p>
        </header>

        <AutomationForm />
      </div>
    </div>
  );
};

export default Index;
